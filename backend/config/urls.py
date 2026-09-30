"""Top-level URLs. Every API route lives under /api/v1 (CLAUDE.md section 6.5)."""

from django.urls import URLPattern, URLResolver, include, path

api_v1: list[URLPattern | URLResolver] = []

urlpatterns = [
    path("api/v1/", include(api_v1)),
]
