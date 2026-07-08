"""Redis cache helpers for LLM output, file metadata, job status, and result pages."""

import hashlib
import json
from typing import Any

from django.core.cache import cache

LLM_REGEX_TIMEOUT = 60 * 60 * 24
FILE_COLUMNS_TIMEOUT = 60 * 60
RESULT_PAGE_TIMEOUT = 60 * 60 * 6
JOB_STATUS_RUNNING_TIMEOUT = 2
JOB_STATUS_TERMINAL_TIMEOUT = 60

LLM_REGEX_PREFIX = "llm:regex:"
LLM_LITERAL_PREFIX = "llm:literal:"
FILE_COLUMNS_PREFIX = "file:columns:"
RESULT_PAGE_PREFIX = "result:page:"
JOB_STATUS_PREFIX = "job:status:"


def normalize_prompt(prompt: str) -> str:
    """Normalize prompts so equivalent wording hits the same cache key."""
    return " ".join(prompt.strip().lower().split())


def llm_regex_cache_key(prompt: str) -> str:
    digest = hashlib.sha256(normalize_prompt(prompt).encode()).hexdigest()
    return f"{LLM_REGEX_PREFIX}{digest}"


def get_cached_llm_regex(prompt: str) -> str | None:
    return cache.get(llm_regex_cache_key(prompt))


def set_cached_llm_regex(prompt: str, regex_pattern: str) -> None:
    cache.set(llm_regex_cache_key(prompt), regex_pattern, LLM_REGEX_TIMEOUT)


def llm_literal_cache_key(prompt: str) -> str:
    digest = hashlib.sha256(normalize_prompt(prompt).encode()).hexdigest()
    return f"{LLM_LITERAL_PREFIX}{digest}"


def get_cached_llm_literal(prompt: str) -> dict[str, str] | None:
    return cache.get(llm_literal_cache_key(prompt))


def set_cached_llm_literal(prompt: str, find_value: str, replacement_value: str) -> None:
    cache.set(
        llm_literal_cache_key(prompt),
        {"find": find_value, "replace": replacement_value},
        LLM_REGEX_TIMEOUT,
    )


def file_columns_cache_key(uploaded_file_id: str, file_mtime: float) -> str:
    # Include mtime so column cache invalidates when the file changes on disk.
    return f"{FILE_COLUMNS_PREFIX}{uploaded_file_id}:{int(file_mtime)}"


def get_cached_file_columns(uploaded_file_id: str, file_mtime: float) -> list[str] | None:
    return cache.get(file_columns_cache_key(uploaded_file_id, file_mtime))


def set_cached_file_columns(
    uploaded_file_id: str,
    file_mtime: float,
    columns: list[str],
) -> None:
    cache.set(
        file_columns_cache_key(uploaded_file_id, file_mtime),
        columns,
        FILE_COLUMNS_TIMEOUT,
    )


def result_page_cache_key(job_id: str, page: int, page_size: int) -> str:
    return f"{RESULT_PAGE_PREFIX}{job_id}:{page}:{page_size}"


def get_cached_result_page(job_id: str, page: int, page_size: int) -> dict[str, Any] | None:
    return cache.get(result_page_cache_key(job_id, page, page_size))


def set_cached_result_page(
    job_id: str,
    page: int,
    page_size: int,
    page_data: dict[str, Any],
) -> None:
    cache.set(
        result_page_cache_key(job_id, page, page_size),
        page_data,
        RESULT_PAGE_TIMEOUT,
    )


def job_status_cache_key(job_id: str) -> str:
    return f"{JOB_STATUS_PREFIX}{job_id}"


def get_cached_job_status(job_id: str) -> dict[str, Any] | None:
    cached = cache.get(job_status_cache_key(job_id))
    if cached is None:
        return None
    if isinstance(cached, str):
        return json.loads(cached)
    return cached


def set_cached_job_status(job_id: str, payload: dict[str, Any], *, running: bool) -> None:
    # Pollers hit running jobs frequently, so keep that cache short-lived.
    timeout = JOB_STATUS_RUNNING_TIMEOUT if running else JOB_STATUS_TERMINAL_TIMEOUT
    cache.set(job_status_cache_key(job_id), payload, timeout)


def invalidate_job_status_cache(job_id: str) -> None:
    cache.delete(job_status_cache_key(job_id))
