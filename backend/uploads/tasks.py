"""Celery tasks for the uploads app."""

import logging

from celery import shared_task

from uploads.models import UploadedFile
from uploads.services import get_file_columns

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="uploads.tasks.warm_upload_columns",
    max_retries=5,
    default_retry_delay=10,
    ignore_result=True,
)
def warm_upload_columns(self, record_id: str) -> None:
    """Prime the Redis column cache once an upload has been saved to disk.

    Web and worker share the media Docker volume, so the worker can read any
    file the web container writes.  Warming the cache here means the first
    frontend status-poll returns column names immediately rather than reading
    the file on every request.
    """
    try:
        record = UploadedFile.objects.get(id=record_id)
    except UploadedFile.DoesNotExist:
        logger.warning("warm_upload_columns: record %s not found", record_id)
        return

    if not record.file_path:
        logger.warning("warm_upload_columns: record %s has no file_path yet, retrying", record_id)
        raise self.retry(countdown=5)

    try:
        get_file_columns(record.file_path, record_id)
        logger.info("warm_upload_columns: columns warmed for record %s", record_id)
    except FileNotFoundError as exc:
        logger.warning("warm_upload_columns: file not found for record %s, retrying", record_id)
        raise self.retry(exc=exc, countdown=10)
    except Exception as exc:
        logger.exception("warm_upload_columns: failed for record %s", record_id)
        raise self.retry(exc=exc, countdown=30)
