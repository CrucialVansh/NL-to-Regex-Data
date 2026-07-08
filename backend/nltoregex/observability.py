"""Celery task instrumentation and lightweight runtime metrics."""

from __future__ import annotations

import logging
import time
from typing import Any

from celery.signals import task_postrun, task_prerun
from django.core.cache import cache

logger = logging.getLogger("nltoregex.observability")

METRICS_PREFIX = "metrics:"
METRICS_TIMEOUT = 60 * 60 * 24


def _metric_key(name: str) -> str:
    return f"{METRICS_PREFIX}{name}"


def increment_metric(name: str, amount: int = 1) -> None:
    try:
        cache.add(_metric_key(name), 0, METRICS_TIMEOUT)
        cache.incr(_metric_key(name), amount)
    except Exception:
        logger.exception("Failed to increment metric %s", name)


def get_task_metrics() -> dict[str, int]:
    names = (
        "tasks_started",
        "tasks_succeeded",
        "tasks_failed",
        "tasks_total_runtime_ms",
    )
    metrics: dict[str, int] = {}
    for name in names:
        value = cache.get(_metric_key(name))
        metrics[name] = int(value or 0)
    return metrics


def register_celery_observability() -> None:
    """Attach Celery signal handlers once at worker/web startup."""

    @task_prerun.connect
    def _on_task_prerun(sender=None, task_id=None, task=None, **kwargs):
        increment_metric("tasks_started")
        if task is not None:
            task.request.observability_start_time = time.monotonic()
        logger.info(
            "task_started task=%s id=%s",
            getattr(sender, "name", sender),
            task_id,
        )

    @task_postrun.connect
    def _on_task_postrun(sender=None, task_id=None, task=None, state=None, **kwargs):
        if state == "SUCCESS":
            increment_metric("tasks_succeeded")
        elif state == "FAILURE":
            increment_metric("tasks_failed")
        if task is not None and hasattr(task.request, "observability_start_time"):
            elapsed_ms = int(
                (time.monotonic() - task.request.observability_start_time) * 1000
            )
            increment_metric("tasks_total_runtime_ms", elapsed_ms)
        logger.info(
            "task_finished task=%s id=%s state=%s",
            getattr(sender, "name", sender),
            task_id,
            state,
        )


def get_job_metrics() -> dict[str, Any]:
    from uploads.models import Job

    status_counts = {
        status.value: Job.objects.filter(status=status.value).count()
        for status in Job.Status
    }
    return {
        "total": sum(status_counts.values()),
        "by_status": status_counts,
    }
