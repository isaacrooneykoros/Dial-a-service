"""Project URLs plus test-only routes. Tests opt in with override_settings(ROOT_URLCONF=...)."""

from django.urls import path

from config.urls import handler404, handler500
from config.urls import urlpatterns as project_urlpatterns
from tests.testapp import views

urlpatterns = [
    *project_urlpatterns,
    path("t/whoami", views.whoami),
    path("t/create-then-raise", views.create_then_raise),
    path("t/create-then-503", views.create_then_503),
    path("t/create-then-400", views.create_then_400),
    path("t/widgets/<uuid:pk>", views.widget_detail),
    path("api/v1/t/create", views.api_create),
    path("api/v1/t/create-then-raise", views.api_create_then_raise),
    path("t/leaky-widgets/<uuid:pk>", views.widget_detail_leaky_cache),
]

__all__ = ["handler404", "handler500", "urlpatterns"]
