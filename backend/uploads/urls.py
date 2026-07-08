"""Upload app URL routes."""

from django.urls import path

from . import views
from .health import health_view
from .metrics import metrics_view

urlpatterns = [
    path("health", health_view),
    path("metrics", metrics_view),
    path("test", views.test),
    path("upload", views.instant_id_upload_view),
    path("uploads", views.list_uploads_view),
    path("uploads/<uuid:uploaded_file_id>/status", views.uploaded_file_status_view),
    path("uploads/<uuid:uploaded_file_id>/data", views.uploaded_file_data_view),
    path("jobs/<uuid:job_id>/results", views.job_results_view),
]
