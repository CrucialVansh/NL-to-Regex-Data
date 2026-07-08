"""Database models for uploaded files and processing jobs."""

from django.db import models

from .identifiers import new_job_id, new_upload_id


class UploadedFile(models.Model):
    id = models.UUIDField(primary_key=True, default=new_upload_id, editable=False)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    # Actual name on disk after Django storage de-duplication.
    saved_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.original_filename} ({self.id})"


class Job(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class TransformType(models.TextChoices):
        REGEX_REPLACE = "REGEX_REPLACE", "Regex replace"
        LITERAL_REPLACE = "LITERAL_REPLACE", "Literal replace"

    id = models.UUIDField(primary_key=True, default=new_job_id, editable=False)
    uploaded_file = models.ForeignKey(
        UploadedFile, on_delete=models.CASCADE, related_name="jobs"
    )
    target_columns = models.JSONField(default=list)
    transform_type = models.CharField(
        max_length=32,
        choices=TransformType.choices,
        default=TransformType.REGEX_REPLACE,
    )
    natural_language_prompt = models.TextField()
    generated_regex = models.TextField(blank=True)
    find_value = models.CharField(max_length=1024, blank=True)
    replacement_value = models.CharField(max_length=1024, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    progress = models.PositiveSmallIntegerField(default=0)  # 0-100
    total_rows = models.PositiveIntegerField(null=True, blank=True)
    rows_processed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    celery_task_id = models.CharField(max_length=255, blank=True)
    result_path = models.CharField(max_length=1024, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job {self.id} [{self.status}]"
