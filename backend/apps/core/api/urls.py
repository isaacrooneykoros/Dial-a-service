from django.urls import path

from apps.core.api import upload_views, views

urlpatterns = [
    path("health", views.health, name="health"),
    path("app/version", views.app_version, name="app-version"),
    path("uploads", upload_views.StartUploadView.as_view(), name="uploads-start"),
    path(
        "uploads/<uuid:pk>/complete",
        upload_views.CompleteUploadView.as_view(),
        name="uploads-complete",
    ),
    path(
        "uploads/<uuid:pk>/content",
        upload_views.local_upload_content,
        name="uploads-local-content",
    ),
]
