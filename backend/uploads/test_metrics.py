"""Tests for the operational metrics endpoint."""

from django.test import Client, TestCase

from uploads.models import Job, UploadedFile


class MetricsEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_metrics_returns_job_counts(self):
        uploaded_file = UploadedFile.objects.create(
            original_filename="data.csv",
            file_path="/tmp/data.csv",
            saved_filename="data.csv",
        )
        Job.objects.create(
            uploaded_file=uploaded_file,
            natural_language_prompt="test",
            replacement_value="x",
            target_columns=["Email"],
            status=Job.Status.SUCCESS,
            progress=100,
        )

        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("jobs", payload)
        self.assertIn("celery_tasks", payload)
        self.assertGreaterEqual(payload["jobs"]["total"], 1)
        self.assertIn("by_status", payload["jobs"])
        self.assertIn("tasks_started", payload["celery_tasks"])
