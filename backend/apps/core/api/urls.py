from django.urls import path

from apps.core.api import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("app/version", views.app_version, name="app-version"),
]
