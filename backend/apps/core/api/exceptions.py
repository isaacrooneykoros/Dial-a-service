"""DRF exception handler producing the error envelope (apps/core/api/errors.py).

Rollback rule: every error response rolls back the request's transaction, so a
request never half-succeeds. Requests run inside the tenant transaction
(ADR-0001 section 2), not Django's ATOMIC_REQUESTS, so DRF's own rollback
doesn't apply; this handler does it for every error.

Consequence: if a failure must leave something behind (for example a wrong
PIN counting towards the device lock), the view must *return* its error
response built with ``envelope()`` instead of raising.
"""

import logging
import math
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import connection, transaction
from django.http import Http404
from django.utils.translation import ngettext
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.api.errors import MESSAGES, ApiError, envelope

logger = logging.getLogger(__name__)

# DRF's built-in exceptions carry developer-oriented text; users get ours.
_BUILTIN_CODES: list[tuple[type[exceptions.APIException], str]] = [
    (exceptions.ValidationError, "validation_error"),
    (exceptions.ParseError, "malformed_request"),
    (exceptions.NotAuthenticated, "not_authenticated"),
    (exceptions.AuthenticationFailed, "not_authenticated"),
    (exceptions.PermissionDenied, "permission_denied"),
    (exceptions.NotFound, "not_found"),
    (exceptions.MethodNotAllowed, "method_not_allowed"),
    (exceptions.NotAcceptable, "not_acceptable"),
    (exceptions.UnsupportedMediaType, "unsupported_media_type"),
]


def flatten_errors(detail: Any, prefix: str = "") -> dict[str, list[str]]:
    """Turn DRF's nested error detail into {"field.sub": ["message", ...]}."""
    if isinstance(detail, dict):
        result: dict[str, list[str]] = {}
        for key, value in detail.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            for field, messages in flatten_errors(value, name).items():
                result.setdefault(field, []).extend(messages)
        return result
    if isinstance(detail, list):
        if all(not isinstance(item, dict | list) for item in detail):
            return {prefix or "non_field_errors": [str(item) for item in detail]}
        result = {}
        for index, item in enumerate(detail):
            name = f"{prefix}.{index}" if prefix else str(index)
            for field, messages in flatten_errors(item, name).items():
                result.setdefault(field, []).extend(messages)
        return result
    return {prefix or "non_field_errors": [str(detail)]}


def _throttled_message(wait: float | None) -> tuple[str, int | None]:
    if wait is None:
        return str(MESSAGES["service_unavailable"]), None
    seconds = max(1, math.ceil(wait))
    minutes = max(1, math.ceil(seconds / 60))
    # Wording from 10-screens-shared.md, "Too many attempts".
    message = ngettext(
        "Too many attempts. Try again in %(n)d minute.",
        "Too many attempts. Try again in %(n)d minutes.",
        minutes,
    ) % {"n": minutes}
    return message, seconds


def _mark_rollback() -> None:
    if connection.in_atomic_block:
        transaction.set_rollback(True)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    request = context.get("request")
    request_id = getattr(request, "request_id", None)

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    _mark_rollback()

    if response is None:
        logger.exception("Unhandled error in API view", exc_info=exc)
        return Response(
            envelope("server_error", MESSAGES["server_error"], None, request_id),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.Throttled):
        message, seconds = _throttled_message(exc.wait)
        response.data = envelope("throttled", message, None, request_id, retry_after=seconds)
        return response

    if isinstance(exc, ApiError):
        structured = isinstance(exc.detail, list | dict)
        code = exc.default_code if structured else exc.detail.code
        fields = flatten_errors(exc.detail) if isinstance(exc.detail, dict) else {}
        message = str(exc.default_detail) if structured else str(exc.detail)
        response.data = envelope(str(code), message, fields, request_id)
        return response

    code = next((c for cls, c in _BUILTIN_CODES if isinstance(exc, cls)), "server_error")
    fields = flatten_errors(exc.detail) if isinstance(exc, exceptions.ValidationError) else {}
    response.data = envelope(code, MESSAGES[code], fields, request_id)
    return response
