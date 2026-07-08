"""Celery application bootstrap for async task processing."""

import os
import sys

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nltoregex.settings.local")

app = Celery("nltoregex")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["uploads", "llmtoregex"])

from nltoregex.observability import register_celery_observability  # noqa: E402

register_celery_observability()


@worker_process_init.connect
def configure_worker_process(**kwargs):
    # PySpark/JVM + Celery prefork can crash on macOS without this guard.
    if sys.platform == "darwin":
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
