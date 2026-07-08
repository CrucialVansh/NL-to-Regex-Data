"""Project-level URL routing."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("uploads.urls")),
    path("llm/", include("llmtoregex.urls")),
]
