"""Sync job progress to PostgreSQL, Redis, and Celery task state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.cache import cache

from nltoregex.cache_utils import invalidate_job_status_cache
from uploads.models import Job

if TYPE_CHECKING:
    from celery import Task

JOB_PROGRESS_CACHE_PREFIX = "job:progress:"
JOB_PROGRESS_CACHE_TIMEOUT = 60 * 60


def _progress_cache_key(job_id: str) -> str:
    return f"{JOB_PROGRESS_CACHE_PREFIX}{job_id}"


def build_progress_meta(
    job_id: str,
    *,
    progress: int,
    status: str,
    total_rows: int | None = None,
    rows_processed: int | None = None,
    error_message: str = "",
    task_name: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "job_id": job_id,
        "progress": max(0, min(progress, 100)),
        "status": status,
        "error_message": error_message,
    }
    if total_rows is not None:
        meta["total_rows"] = total_rows
    if rows_processed is not None:
        meta["rows_processed"] = rows_processed
    if task_name is not None:
        meta["task_name"] = task_name
    if task_id is not None:
        meta["task_id"] = task_id
    return meta


def get_cached_progress_meta(job_id: str) -> dict[str, Any] | None:
    cached = cache.get(_progress_cache_key(job_id))
    if isinstance(cached, dict):
        return cached
    return None


def update_job_progress(
    job_id: str,
    *,
    progress: int,
    status: str | None = None,
    total_rows: int | None = None,
    rows_processed: int | None = None,
    error_message: str = "",
    task: Task | None = None,
) -> None:
    """Persist progress and mirror it to Celery/Redis for polling and Flower."""
    updates: dict[str, Any] = {
        "progress": max(0, min(progress, 100)),
        "error_message": error_message,
    }
    if status is not None:
        updates["status"] = status
    if total_rows is not None:
        updates["total_rows"] = total_rows
    if rows_processed is not None:
        updates["rows_processed"] = rows_processed

    Job.objects.filter(pk=job_id).update(**updates)
    invalidate_job_status_cache(job_id)

    job = Job.objects.filter(pk=job_id).values(
        "status",
        "progress",
        "total_rows",
        "rows_processed",
        "error_message",
    ).first()
    if job is None:
        return

    task_name = task.name if task is not None else None
    task_id = task.request.id if task is not None else None
    meta = build_progress_meta(
        job_id,
        progress=job["progress"],
        status=job["status"],
        total_rows=job["total_rows"],
        rows_processed=job["rows_processed"],
        error_message=job["error_message"],
        task_name=task_name,
        task_id=task_id,
    )
    cache.set(_progress_cache_key(job_id), meta, JOB_PROGRESS_CACHE_TIMEOUT)

    if task is not None and task.request.id:
        task.update_state(state="PROGRESS", meta=meta)
