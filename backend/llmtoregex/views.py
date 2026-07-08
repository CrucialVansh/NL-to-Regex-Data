"""HTTP views for starting jobs, polling status, and cancelling work."""

import json
import uuid

from celery import chain
from celery.result import AsyncResult
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from nltoregex.cache_utils import (
    get_cached_job_status,
    invalidate_job_status_cache,
    set_cached_job_status,
)
from nltoregex.task_progress import get_cached_progress_meta
from uploads.models import Job, UploadedFile
from uploads.services import ColumnValidationError, get_file_columns, validate_target_columns
from .input_validation import InputValidationError, validate_natural_language_prompt, validate_replacement_value
from .tasks import nltoliteral, nltoregex, regextransform

CANCELLABLE_STATUSES = {Job.Status.QUEUED, Job.Status.RUNNING}


def _parse_transform_type(raw_value) -> str | None:
    if raw_value in (None, ""):
        return Job.TransformType.REGEX_REPLACE
    if raw_value not in Job.TransformType.values:
        return None
    return raw_value


def _job_status_payload(job: Job) -> dict:
    """Build the JSON body returned by the status endpoint."""
    payload = {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "transform_type": job.transform_type,
    }
    if job.total_rows is not None:
        payload["total_rows"] = job.total_rows
        payload["rows_processed"] = job.rows_processed
    if job.error_message and job.status == Job.Status.RUNNING:
        payload["retry_message"] = job.error_message
    if job.status == Job.Status.FAILED:
        payload["error"] = job.error_message
    elif job.status == Job.Status.CANCELLED:
        payload["message"] = job.error_message or "Job cancelled"
    elif job.status == Job.Status.SUCCESS:
        payload["result_path"] = job.result_path
        if job.transform_type == Job.TransformType.LITERAL_REPLACE:
            payload["find_value"] = job.find_value
            payload["replacement_value"] = job.replacement_value
        else:
            payload["generated_regex"] = job.generated_regex
            payload["replacement_value"] = job.replacement_value
    return payload


@csrf_exempt
def invoke_llm(request):
    """Create a job and enqueue a natural-language transform pipeline."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    transform_type = _parse_transform_type(data.get("transform_type"))
    if transform_type is None:
        return JsonResponse(
            {
                "error": (
                    "transform_type must be one of: "
                    f"{', '.join(Job.TransformType.values)}"
                )
            },
            status=400,
        )

    try:
        uploaded_file_id = uuid.UUID(data.get("uploaded_file_id", ""))
    except (ValueError, TypeError):
        return JsonResponse({"error": "A valid uploaded_file_id is required"}, status=400)

    target_columns = data.get("target_columns")
    if not isinstance(target_columns, list) or not target_columns:
        return JsonResponse(
            {"error": "target_columns must be a non-empty list of column names"},
            status=400,
        )

    try:
        natural_language_prompt = validate_natural_language_prompt(
            data.get("natural_language_prompt") or data.get("text") or ""
        )
    except InputValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    replacement_value = ""
    if transform_type == Job.TransformType.REGEX_REPLACE:
        try:
            replacement_value = validate_replacement_value(data.get("replacement_value") or "")
        except InputValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    try:
        uploaded_file = UploadedFile.objects.get(pk=uploaded_file_id)
    except UploadedFile.DoesNotExist:
        return JsonResponse({"error": "Uploaded file not found"}, status=404)

    file_path = uploaded_file.file_path
    if not file_path:
        return JsonResponse(
            {"error": "Upload not ready; wait for file save to complete"},
            status=409,
        )

    try:
        available_columns = get_file_columns(file_path, str(uploaded_file.id))
        normalized_columns = validate_target_columns(target_columns, available_columns)
    except ColumnValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except FileNotFoundError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    job = Job.objects.create(
        uploaded_file=uploaded_file,
        natural_language_prompt=natural_language_prompt,
        replacement_value=replacement_value,
        target_columns=normalized_columns,
        transform_type=transform_type,
        status=Job.Status.QUEUED,
        progress=0,
    )

    if transform_type == Job.TransformType.LITERAL_REPLACE:
        pipeline = chain(
            nltoliteral.s(
                natural_language_prompt,
                str(job.id),
                normalized_columns,
            ),
            regextransform.s(file_path, str(job.id)),
        )
    else:
        pipeline = chain(
            nltoregex.s(
                natural_language_prompt,
                str(job.id),
                normalized_columns,
                replacement_value,
            ),
            regextransform.s(file_path, str(job.id)),
        )

    async_result = pipeline.apply_async()
    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id", "updated_at"])
    invalidate_job_status_cache(str(job.id))

    return JsonResponse(
        {
            "job_id": str(job.id),
            "uploaded_file_id": str(uploaded_file.id),
            "status": job.status,
            "transform_type": job.transform_type,
            "target_columns": normalized_columns,
        },
        status=202,
    )


def _merge_celery_progress(job: Job, payload: dict) -> dict:
    """Overlay live Celery PROGRESS meta when the job is still running."""
    if job.status not in {Job.Status.QUEUED, Job.Status.RUNNING}:
        return payload

    progress_meta = get_cached_progress_meta(str(job.id))
    if progress_meta is None and job.celery_task_id:
        async_result = AsyncResult(job.celery_task_id)
        if async_result.state == "PROGRESS" and isinstance(async_result.info, dict):
            progress_meta = async_result.info

    if not progress_meta:
        return payload

    merged = {**payload}
    for field in ("progress", "total_rows", "rows_processed", "status"):
        if field in progress_meta and progress_meta[field] is not None:
            merged[field] = progress_meta[field]
    if progress_meta.get("task_name"):
        merged["celery_task"] = progress_meta["task_name"]
    if progress_meta.get("task_id"):
        merged["celery_task_id"] = progress_meta["task_id"]
    if progress_meta.get("error_message") and job.status == Job.Status.RUNNING:
        merged["retry_message"] = progress_meta["error_message"]
    return merged


def check_status_view(request, job_id):
    """Return cached job progress when available to reduce database reads."""
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    cached_status = get_cached_job_status(str(job.id))
    if cached_status is not None:
        return JsonResponse(_merge_celery_progress(job, cached_status))

    response_data = _merge_celery_progress(job, _job_status_payload(job))
    set_cached_job_status(
        str(job.id),
        response_data,
        running=job.status in {Job.Status.QUEUED, Job.Status.RUNNING},
    )
    return JsonResponse(response_data)


@csrf_exempt
def cancel_job_view(request, job_id):
    """Revoke the Celery chain and mark the job as cancelled."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    if job.status == Job.Status.CANCELLED:
        return JsonResponse(
            {
                "job_id": str(job.id),
                "status": job.status,
                "message": "Job already cancelled",
            }
        )

    if job.status not in CANCELLABLE_STATUSES:
        return JsonResponse(
            {
                "error": f"Cannot cancel job with status {job.status}",
                "status": job.status,
            },
            status=409,
        )

    if job.celery_task_id:
        AsyncResult(job.celery_task_id).revoke(terminate=True)

    job.status = Job.Status.CANCELLED
    job.error_message = "Cancelled by user"
    job.save(update_fields=["status", "error_message", "updated_at"])
    invalidate_job_status_cache(str(job.id))

    return JsonResponse(
        {
            "job_id": str(job.id),
            "status": job.status,
            "message": "Job cancelled",
        }
    )
