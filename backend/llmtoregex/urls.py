"""LLM and job control API routes."""

from django.urls import path

from . import views

urlpatterns = [
    path("invoke", views.invoke_llm),
    path("check_status_view/<str:job_id>", views.check_status_view),
    path("jobs/<uuid:job_id>/cancel", views.cancel_job_view),
]
