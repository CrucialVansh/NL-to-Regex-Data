"""Celery tasks for the NL-to-regex processing pipeline.

Pipeline:
1. nltoregex / nltoliteral - convert natural language into a transform plan.
2. regextransform - apply the plan with PySpark and write Parquet results.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import List

from celery import Task, shared_task
from celery.exceptions import Ignore
from django.conf import settings
from openai import APITimeoutError, APIConnectionError, InternalServerError, RateLimitError
from pydantic import BaseModel, ValidationError
from pyspark.errors import PySparkRuntimeError
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from nltoregex.cache_utils import (
    get_cached_llm_literal,
    get_cached_llm_regex,
    invalidate_job_status_cache,
    set_cached_llm_literal,
    set_cached_llm_regex,
)
from nltoregex.task_progress import update_job_progress
from uploads.excel_reader import ExcelReadError, export_excel_to_csv
from uploads.models import Job
from .literal_validation import (
    LiteralValidationError,
    escape_spark_literal_pattern,
    escape_spark_replacement,
    validate_literal_pair,
)
from .regex_validation import RegexValidationError, validate_regex_pattern
from .services import get_openai_client

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# Errors that should trigger Celery automatic retries with backoff.
RETRYABLE_LLM_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)
RETRYABLE_REDIS_ERRORS = (
    RedisConnectionError,
    RedisTimeoutError,
    ResponseError,
    RedisError,
)
RETRYABLE_SPARK_ERRORS = (PySparkRuntimeError,)

# Validation and user-input failures should fail the job immediately.
NON_RETRYABLE_ERRORS = (
    ValueError,
    FileNotFoundError,
    TypeError,
    ValidationError,
    RegexValidationError,
    LiteralValidationError,
)

TASK_RETRY_OPTIONS = {
    "retry_kwargs": {"max_retries": MAX_RETRIES},
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
}


class RegexPattern(BaseModel):
    """Structured OpenAI response containing the generated regex."""

    Regex: str


class LiteralReplacement(BaseModel):
    """Structured OpenAI response for exact text replacement."""

    Find: str
    Replace: str


def _job_id_from_task(task: Task, args: tuple, kwargs: dict) -> str | None:
    """Extract job_id from chained task args when kwargs do not include it."""
    if kwargs.get("job_id"):
        return str(kwargs["job_id"])
    if task.name.endswith("nltoregex") and len(args) >= 2:
        return str(args[1])
    if task.name.endswith("nltoliteral") and len(args) >= 2:
        return str(args[1])
    if task.name.endswith("regextransform") and len(args) >= 3:
        return str(args[2])
    return None


def _abort_if_cancelled(job_id: str) -> None:
    """Stop task execution quietly if the user cancelled the job."""
    if Job.objects.filter(pk=job_id, status=Job.Status.CANCELLED).exists():
        raise Ignore()


class JobAwareTask(Task):
    """Base task that mirrors Celery retry/failure state onto the Job model."""

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        job_id = _job_id_from_task(self, args, kwargs)
        if not job_id:
            return
        if Job.objects.filter(pk=job_id, status=Job.Status.CANCELLED).exists():
            return

        attempt = self.request.retries + 1
        update_job_progress(
            job_id,
            progress=Job.objects.filter(pk=job_id).values_list("progress", flat=True).first() or 0,
            status=Job.Status.RUNNING,
            error_message=f"Retrying ({attempt}/{self.max_retries}): {exc}",
            task=self,
        )
        logger.warning(
            "Retrying task %s for job %s (%s/%s): %s",
            self.name,
            job_id,
            attempt,
            self.max_retries,
            exc,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = _job_id_from_task(self, args, kwargs)
        if not job_id:
            return
        if Job.objects.filter(pk=job_id, status=Job.Status.CANCELLED).exists():
            return

        update_job_progress(
            job_id,
            progress=Job.objects.filter(pk=job_id).values_list("progress", flat=True).first() or 0,
            status=Job.Status.FAILED,
            error_message=str(exc),
            task=self,
        )
        logger.error("Task %s failed permanently for job %s: %s", self.name, job_id, exc)


def _build_spark(app_name: str) -> SparkSession:
    """Create a fresh local Spark session for one worker task."""
    active_session = SparkSession.getActiveSession()
    if active_session is not None:
        active_session.stop()

    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        # Avoid reusing Python workers across JVM restarts in Celery.
        .config("spark.python.worker.reuse", "false")
        # Stable binding inside Docker / Celery worker containers.
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.enabled", "false")
    )
    try:
        return builder.getOrCreate()
    except Exception:
        logger.exception(
            "Failed to start Spark session (JAVA_HOME=%s, java=%s)",
            os.environ.get("JAVA_HOME"),
            os.environ.get("PATH"),
        )
        raise


def _stop_spark(spark: SparkSession | None) -> None:
    if spark is None:
        return
    try:
        spark.stop()
    except Exception:
        logger.exception("Failed to stop Spark session")


def _prepare_spark_input(path: str) -> tuple[str, str | None]:
    """Convert Excel uploads to a temporary CSV that Spark can read reliably."""
    if not path.lower().endswith(".xlsx"):
        return path, None

    temp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    temp_file.close()
    try:
        export_excel_to_csv(path, temp_file.name)
    except ExcelReadError as exc:
        os.remove(temp_file.name)
        raise ValueError(str(exc)) from exc
    return temp_file.name, temp_file.name


def _read_dataframe(spark: SparkSession, path: str):
    """Load CSV or Parquet into a Spark DataFrame."""
    path_lower = path.lower()
    if path_lower.endswith(".csv"):
        return (
            spark.read
            .option("header", True)
            .option("inferSchema", False)
            .option("quote", '"')
            .option("escape", '"')
            .option("multiLine", True)
            .csv(path)
        )
    if path_lower.endswith(".xlsx"):
        raise ValueError("Excel inputs must be converted to CSV before Spark processing")
    if path_lower.endswith(".xls"):
        raise ValueError(
            "Legacy .xls files are not supported for Spark processing; convert to .xlsx or CSV."
        )
    return spark.read.parquet(path)


def _resolve_column(df, name: str) -> str:
    """Match a requested column name case-insensitively to the DataFrame schema."""
    lookup = {column.lower(): column for column in df.columns}
    actual = lookup.get(name.lower())
    if actual is None:
        raise ValueError(f"Column '{name}' not found. Available columns: {df.columns}")
    return actual


def _output_path(input_path: str, job_id: str) -> str:
    """Directory where this job's Parquet output will be written."""
    input_stem = Path(input_path).stem
    return os.path.join(settings.MEDIA_ROOT, "results", str(job_id), input_stem)


def _mark_job_running(job_id: str) -> None:
    Job.objects.filter(pk=job_id, status=Job.Status.QUEUED).update(status=Job.Status.RUNNING)
    invalidate_job_status_cache(job_id)


def _apply_transform_to_column(df, response: dict, column_name: str):
    actual_column = _resolve_column(df, column_name)
    if response["TransformType"] == Job.TransformType.LITERAL_REPLACE:
        pattern = escape_spark_literal_pattern(response["Find"])
        replacement = escape_spark_replacement(response["Replacement"])
        return df.withColumn(
            actual_column,
            F.regexp_replace(F.col(actual_column), pattern, replacement),
        )

    return df.withColumn(
        actual_column,
        F.regexp_replace(
            F.col(actual_column),
            response["Regex"],
            response["Replacement"],
        ),
    )


@shared_task(
    bind=True,
    base=JobAwareTask,
    autoretry_for=RETRYABLE_LLM_ERRORS + RETRYABLE_REDIS_ERRORS,
    **TASK_RETRY_OPTIONS,
)
def nltoregex(
    self,
    text_content: str,
    job_id: str,
    target_columns: List[str],
    replacement_value: str,
) -> dict:
    """Generate a validated regex from natural language via OpenAI."""
    _abort_if_cancelled(job_id)
    _mark_job_running(job_id)
    update_job_progress(job_id, progress=5, task=self)

    cached_regex = get_cached_llm_regex(text_content)
    if cached_regex is not None:
        validated_regex = validate_regex_pattern(cached_regex)
        logger.info("Cache hit for LLM regex on job %s", job_id)
        return {
            "TransformType": Job.TransformType.REGEX_REPLACE,
            "Regex": validated_regex,
            "Columns": target_columns,
            "Replacement": replacement_value,
        }

    client = get_openai_client()
    response = client.beta.chat.completions.parse(
        model=settings.OPENAI_MODEL,
        temperature=0.01,
        messages=[
            {
                "role": "user",
                "content": (
                    "Convert this natural language pattern description into a "
                    "Java-compatible regular expression for use in Apache Spark "
                    "regexp_replace. Return only the regex pattern.\n\n"
                    f"Description: {text_content}\n"
                    f"Target columns: {', '.join(target_columns)}"
                ),
            }
        ],
        response_format=RegexPattern,
    )
    parsed = response.choices[0].message.parsed
    validated_regex = validate_regex_pattern(parsed.Regex)
    set_cached_llm_regex(text_content, validated_regex)
    update_job_progress(job_id, progress=10, task=self)
    logger.info("Generated regex for job %s on columns %s", job_id, target_columns)
    return {
        "TransformType": Job.TransformType.REGEX_REPLACE,
        "Regex": validated_regex,
        "Columns": target_columns,
        "Replacement": replacement_value,
    }


@shared_task(
    bind=True,
    base=JobAwareTask,
    autoretry_for=RETRYABLE_LLM_ERRORS + RETRYABLE_REDIS_ERRORS,
    **TASK_RETRY_OPTIONS,
)
def nltoliteral(
    self,
    text_content: str,
    job_id: str,
    target_columns: List[str],
) -> dict:
    """Generate validated literal find/replace values from natural language."""
    _abort_if_cancelled(job_id)
    _mark_job_running(job_id)
    update_job_progress(job_id, progress=5, task=self)

    cached_literal = get_cached_llm_literal(text_content)
    if cached_literal is not None:
        find_value, replacement_value = validate_literal_pair(
            cached_literal["find"],
            cached_literal["replace"],
        )
        logger.info("Cache hit for LLM literal replace on job %s", job_id)
        return {
            "TransformType": Job.TransformType.LITERAL_REPLACE,
            "Find": find_value,
            "Replacement": replacement_value,
            "Columns": target_columns,
        }

    client = get_openai_client()
    response = client.beta.chat.completions.parse(
        model=settings.OPENAI_MODEL,
        temperature=0.01,
        messages=[
            {
                "role": "user",
                "content": (
                    "Convert this natural language description into an exact literal "
                    "find-and-replace operation for spreadsheet columns. Return the exact "
                    "substring to find and the exact replacement text. Do not use regex.\n\n"
                    f"Description: {text_content}\n"
                    f"Target columns: {', '.join(target_columns)}"
                ),
            }
        ],
        response_format=LiteralReplacement,
    )
    parsed = response.choices[0].message.parsed
    find_value, replacement_value = validate_literal_pair(parsed.Find, parsed.Replace)
    set_cached_llm_literal(text_content, find_value, replacement_value)
    update_job_progress(job_id, progress=10, task=self)
    logger.info("Generated literal replace for job %s on columns %s", job_id, target_columns)
    return {
        "TransformType": Job.TransformType.LITERAL_REPLACE,
        "Find": find_value,
        "Replacement": replacement_value,
        "Columns": target_columns,
    }


@shared_task(
    bind=True,
    base=JobAwareTask,
    autoretry_for=RETRYABLE_SPARK_ERRORS + RETRYABLE_REDIS_ERRORS,
    **TASK_RETRY_OPTIONS,
)
def regextransform(self, response, path, job_id):
    """Apply the generated transform plan to target columns and write Parquet output."""
    _abort_if_cancelled(job_id)
    _mark_job_running(job_id)

    spark = None
    temp_csv_path = None
    try:
        spark = _build_spark(f"CeleryTask_{self.request.id}")
        update_job_progress(job_id, progress=12, error_message="", task=self)

        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"Input file not found: {path}")

        spark_input_path, temp_csv_path = _prepare_spark_input(path)
        df = _read_dataframe(spark, spark_input_path)
        if "TransformType" not in response:
            response["TransformType"] = Job.TransformType.REGEX_REPLACE
        total_rows = df.count()
        update_job_progress(
            job_id,
            progress=20,
            total_rows=total_rows,
            rows_processed=0,
            task=self,
        )

        transformed_df = df
        column_count = len(response["Columns"])
        for index, column_name in enumerate(response["Columns"], start=1):
            transformed_df = _apply_transform_to_column(
                transformed_df,
                response,
                column_name,
            )
            # Spread transform progress across 20-75% based on columns completed.
            rows_processed = int(total_rows * index / column_count)
            progress = 20 + int(55 * index / column_count)
            update_job_progress(
                job_id,
                progress=progress,
                rows_processed=rows_processed,
                task=self,
            )

        output_path = _output_path(path, job_id)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        update_job_progress(job_id, progress=80, rows_processed=total_rows, task=self)
        transformed_df.write.mode("overwrite").parquet(output_path)

        job = Job.objects.get(pk=job_id)
        job.status = Job.Status.SUCCESS
        job.progress = 100
        job.rows_processed = total_rows
        job.total_rows = total_rows
        job.result_path = output_path
        job.transform_type = response["TransformType"]
        job.generated_regex = response.get("Regex", "")
        job.find_value = response.get("Find", "")
        job.target_columns = response["Columns"]
        job.replacement_value = response["Replacement"]
        job.error_message = ""
        job.save()
        invalidate_job_status_cache(job_id)
        update_job_progress(
            job_id,
            progress=100,
            status=Job.Status.SUCCESS,
            total_rows=total_rows,
            rows_processed=total_rows,
            task=self,
        )

        return {"status": "Success", "output": output_path, "total_rows": total_rows}

    except NON_RETRYABLE_ERRORS:
        logger.exception("Non-retryable regextransform failure for job %s", job_id)
        raise

    finally:
        if temp_csv_path:
            try:
                os.remove(temp_csv_path)
            except OSError:
                logger.warning("Failed to remove temporary CSV file %s", temp_csv_path)
        _stop_spark(spark)
