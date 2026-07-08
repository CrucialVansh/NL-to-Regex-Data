"""Spark/Celery integration tests for large CSV processing."""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from django.test import TransactionTestCase, override_settings

from nltoregex.task_progress import get_cached_progress_meta
from llmtoregex.tasks import regextransform
from uploads.models import Job, UploadedFile
from uploads.result_reader import paginate_parquet_result

SPARK_AVAILABLE = shutil.which("java") is not None
DEFAULT_INTEGRATION_ROWS = int(os.environ.get("INTEGRATION_TEST_ROWS", "5000"))


def _write_large_csv(path: Path, rows: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "Name", "Email"])
        for row_id in range(1, rows + 1):
            writer.writerow([row_id, f"User {row_id}", f"user{row_id}@example.com"])


@unittest.skipUnless(SPARK_AVAILABLE, "Java runtime required for Spark integration tests")
class LargeCsvSparkIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp(prefix="spark-integration-")
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def _create_job(self, csv_path: Path) -> Job:
        uploaded_file = UploadedFile.objects.create(
            original_filename=csv_path.name,
            file_path=str(csv_path),
            saved_filename=csv_path.name,
        )
        return Job.objects.create(
            uploaded_file=uploaded_file,
            natural_language_prompt="find email addresses",
            replacement_value="REDACTED",
            target_columns=["Email"],
            status=Job.Status.QUEUED,
            progress=0,
        )

    def test_large_csv_regex_transform_writes_paginated_results(self):
        rows = DEFAULT_INTEGRATION_ROWS
        csv_path = Path(self.temp_media) / "uploads" / "large_integration.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        _write_large_csv(csv_path, rows)

        job = self._create_job(csv_path)
        response = {
            "TransformType": Job.TransformType.REGEX_REPLACE,
            "Regex": r"[^@]+@[^@]+\.[^@]+",
            "Columns": ["Email"],
            "Replacement": "REDACTED",
        }

        result = regextransform.run(response, str(csv_path), str(job.id))

        job.refresh_from_db()
        self.assertEqual(result["total_rows"], rows)
        self.assertEqual(job.status, Job.Status.SUCCESS)
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.total_rows, rows)
        self.assertEqual(job.rows_processed, rows)
        self.assertTrue(job.result_path)
        self.assertTrue(os.path.isdir(job.result_path))

        progress_meta = get_cached_progress_meta(str(job.id))
        self.assertIsNotNone(progress_meta)
        self.assertEqual(progress_meta["progress"], 100)
        self.assertEqual(progress_meta["total_rows"], rows)

        page = paginate_parquet_result(job.result_path, page=1, page_size=50)
        self.assertEqual(page["total_rows"], rows)
        self.assertEqual(page["rows"][0]["Email"], "REDACTED")
        self.assertEqual(page["rows"][-1]["Email"], "REDACTED")

    def test_large_csv_literal_transform(self):
        rows = min(DEFAULT_INTEGRATION_ROWS, 2000)
        csv_path = Path(self.temp_media) / "uploads" / "literal_integration.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        _write_large_csv(csv_path, rows)

        job = self._create_job(csv_path)
        response = {
            "TransformType": Job.TransformType.LITERAL_REPLACE,
            "Find": "@example.com",
            "Replacement": "@company.com",
            "Columns": ["Email"],
        }

        result = regextransform.run(response, str(csv_path), str(job.id))

        job.refresh_from_db()
        self.assertEqual(result["total_rows"], rows)
        self.assertEqual(job.status, Job.Status.SUCCESS)

        page = paginate_parquet_result(job.result_path, page=1, page_size=10)
        self.assertEqual(page["rows"][0]["Email"], "user1@company.com")
