"""Tests for Celery progress mirroring helpers."""

from django.test import SimpleTestCase, TestCase

from nltoregex.task_progress import build_progress_meta, get_cached_progress_meta, update_job_progress
from uploads.models import Job, UploadedFile


class TaskProgressTests(SimpleTestCase):
    def test_build_progress_meta_clamps_progress(self):
        meta = build_progress_meta(
            "job-1",
            progress=150,
            status="RUNNING",
            total_rows=100,
            rows_processed=50,
            task_name="llmtoregex.tasks.regextransform",
        )
        self.assertEqual(meta["progress"], 100)
        self.assertEqual(meta["total_rows"], 100)
        self.assertEqual(meta["rows_processed"], 50)


class UpdateJobProgressTests(TestCase):
    def test_update_job_progress_writes_redis_cache_meta(self):
        uploaded_file = UploadedFile.objects.create(
            original_filename="data.csv",
            file_path="/tmp/data.csv",
            saved_filename="data.csv",
        )
        job = Job.objects.create(
            uploaded_file=uploaded_file,
            natural_language_prompt="test",
            replacement_value="x",
            target_columns=["Email"],
            status=Job.Status.RUNNING,
            progress=0,
        )

        update_job_progress(
            str(job.id),
            progress=42,
            status=Job.Status.RUNNING,
            total_rows=1000,
            rows_processed=420,
        )

        job.refresh_from_db()
        self.assertEqual(job.progress, 42)
        self.assertEqual(job.total_rows, 1000)
        self.assertEqual(job.rows_processed, 420)

        cached = get_cached_progress_meta(str(job.id))
        self.assertIsNotNone(cached)
        self.assertEqual(cached["progress"], 42)
        self.assertEqual(cached["total_rows"], 1000)
        self.assertEqual(cached["rows_processed"], 420)
