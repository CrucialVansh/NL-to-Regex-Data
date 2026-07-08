"""Operational metrics endpoint for local monitoring."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from nltoregex.observability import get_job_metrics, get_task_metrics


@require_GET
def metrics_view(request):
    return JsonResponse(
        {
            "jobs": get_job_metrics(),
            "celery_tasks": get_task_metrics(),
        }
    )
