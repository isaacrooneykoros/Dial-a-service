"""Top-level URLs. Every API route lives under /api/v1 (CLAUDE.md section 6.5)."""

from django.conf import settings
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1: list[URLPattern | URLResolver] = [
    path("", include("apps.core.api.urls")),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/", include(api_v1)),
    # OpenAPI schema (design doc "API contract"); the committed copy is backend/openapi.yaml.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]

if settings.DEBUG:
    # Browsable docs for local development only (loads assets from a CDN).
    urlpatterns.append(
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs")
    )

handler404 = "apps.core.api.views.not_found"
handler500 = "apps.core.api.views.server_error"
