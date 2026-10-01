from django.urls import path

from apps.tenancy.api import views

urlpatterns = [
    path("business/config", views.BusinessConfigView.as_view(), name="business-config"),
]
