"""GET /business/config: X-01 start-up data for this business (ADR-0003 section 2)."""

from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenant_context import get_current_business_id
from apps.tenancy.config_sections import SECTIONS
from apps.tenancy.selectors import business_config


class ConfigBusinessSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    slug = serializers.CharField()
    country = serializers.CharField()
    currency = serializers.CharField()
    timezone = serializers.CharField()
    language = serializers.CharField()


class ConfigBrandingSerializer(serializers.Serializer[Any]):
    app_name = serializers.CharField()
    logo_url = serializers.CharField(allow_blank=True)
    primary_color = serializers.CharField()
    accent_color = serializers.CharField()
    support_phone = serializers.CharField(allow_blank=True)
    whatsapp_phone = serializers.CharField(allow_blank=True)
    terms_url = serializers.CharField(allow_blank=True)
    privacy_url = serializers.CharField(allow_blank=True)


class MaintenanceSerializer(serializers.Serializer[Any]):
    active = serializers.BooleanField()
    expected_return = serializers.CharField(allow_blank=True)


class BaseConfigSerializer(serializers.Serializer[Any]):
    business = ConfigBusinessSerializer()
    branding = ConfigBrandingSerializer()
    maintenance = MaintenanceSerializer()


def config_serializer() -> type[serializers.Serializer[Any]]:
    """The base sections plus every registered one (apps/tenancy/config_sections.py).
    Sections register in AppConfig.ready(), which runs before URLs load."""
    fields = {name: section.serializer() for name, section in sorted(SECTIONS.items())}
    return type("BusinessConfigSerializer", (BaseConfigSerializer,), fields)


BusinessConfigSerializer = config_serializer()


class BusinessConfigView(APIView):
    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="business_config",
        summary="X-01 Branding, basics, maintenance and the price list for this business",
        responses={200: BusinessConfigSerializer},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        config = business_config(get_current_business_id())
        config["maintenance"] = {
            "active": settings.MAINTENANCE_MODE,
            "expected_return": settings.MAINTENANCE_EXPECTED_RETURN,
        }
        for name, section in SECTIONS.items():
            config[name] = section.build()
        return Response(BusinessConfigSerializer(config).data)
