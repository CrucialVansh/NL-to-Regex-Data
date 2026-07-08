"""Lightweight readiness endpoint for load balancers and monitoring."""

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_view(request):
    checks = {"database": False, "redis": False}
    errors = []

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone()[0] == 1
    except Exception as exc:
        errors.append(f"database: {exc}")

    try:
        probe_key = "health:probe"
        cache.set(probe_key, "ok", timeout=5)
        checks["redis"] = cache.get(probe_key) == "ok"
        cache.delete(probe_key)
    except Exception as exc:
        errors.append(f"redis: {exc}")

    payload = {
        "status": "ok" if all(checks.values()) else "degraded",
        "checks": checks,
    }
    if errors:
        payload["errors"] = errors

    return JsonResponse(payload, status=200 if all(checks.values()) else 503)
