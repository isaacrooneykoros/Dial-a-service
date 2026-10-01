"""Core endpoints: health check, and envelope-shaped Django 404 and 500 handlers."""

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.api.errors import error_json
from apps.core.models import AppVersion

logger = logging.getLogger(__name__)

OK, ERROR, NOT_CONFIGURED = "ok", "error", "not_configured"


def check_database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check: database unavailable")
        return ERROR
    return OK


def check_redis() -> str:
    if not settings.REDIS_URL:
        return NOT_CONFIGURED
    try:
        cache.set("health:ping", "pong", timeout=10)
        if cache.get("health:ping") != "pong":
            return ERROR
    except Exception:
        logger.exception("Health check: Redis unavailable")
        return ERROR
    return OK


@extend_schema(
    operation_id="health",
    summary="Service health",
    description="Checks the database and Redis. Returns 503 if either is failing. "
    "Answers on any host (it's exempt from business resolution).",
    responses={
        200: inline_serializer(
            "Health",
            {
                "status": serializers.ChoiceField(choices=["ok", "degraded"]),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
        503: inline_serializer(
            "HealthDegraded",
            {
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
    },
    auth=[],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request: Request) -> Response:
    checks = {"database": check_database(), "redis": check_redis()}
    healthy = all(value != ERROR for value in checks.values())
    return Response(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_json(request, 404, "not_found")


def server_error(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
    return error_json(request, 500, "server_error")


class AppVersionSerializer(serializers.Serializer[Any]):
    app = serializers.CharField()
    platform = serializers.CharField()
    minimum = serializers.CharField()
    latest = serializers.CharField()


@extend_schema(
    operation_id="app_version",
    summary="X-01 / X-02 Minimum and latest version of an app",
    parameters=[
        OpenApiParameter("app", str, default="web"),
        OpenApiParameter("platform", str, default="web"),
    ],
    responses={200: AppVersionSerializer},
    auth=[],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def app_version(request: Request) -> Response:
    """With no row for the app, every version is allowed (minimum "0.0.0")."""
    app = request.query_params.get("app", "web")[:20]
    platform = request.query_params.get("platform", "web")[:20]
    row = AppVersion.objects.filter(app=app, platform=platform).first()
    return Response(
        {
            "app": app,
            "platform": platform,
            "minimum": row.minimum if row else "0.0.0",
            "latest": row.latest if row else "0.0.0",
        }
    )
