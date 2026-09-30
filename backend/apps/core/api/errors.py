"""The one error shape every endpoint returns (CLAUDE.md section 6.5).

    {"code": "...", "message": "...", "fields": {...}, "request_id": "..."}

``message`` is always safe to show to users. ``fields`` maps field names to
lists of messages (empty when the error isn't about particular fields).
Throttled responses (429) also carry ``retry_after`` in seconds.

Raise one of the ``ApiError`` subclasses from services and views for expected
failures (409 conflicts, 410 expired links and so on).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.core.request_id import get_request_id

if TYPE_CHECKING:  # django-stubs-ext is a development-only package
    from django_stubs_ext import StrPromise

# User-facing wording (10-screens-shared.md content rules: plain, "you" and
# "we", say what to do next). X-04 and the throttling text are from the spec.
MESSAGES: dict[str, StrPromise] = {
    "validation_error": _("Some details need fixing. Check the highlighted fields."),
    "malformed_request": _("We couldn't read that request. Please try again."),
    "not_authenticated": _("Please log in to continue."),
    "permission_denied": _("You don't have access to this."),
    "not_found": _("We couldn't find that"),
    "method_not_allowed": _("That action isn't allowed here."),
    "not_acceptable": _("We can't send a response in that format."),
    "unsupported_media_type": _("We can't read data in that format."),
    "conflict": _("That can't be done right now because something changed. Refresh and try again."),
    "gone": _("This link is no longer valid."),
    "server_error": _("Something went wrong on our side. Please try again."),
    "service_unavailable": _("We're having trouble right now. Please try again in a few minutes."),
}


def envelope(
    code: str,
    message: str | StrPromise,
    fields: dict[str, list[str]] | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": str(message),
        "fields": fields or {},
        "request_id": request_id or get_request_id(),
        **extra,
    }


def error_json(
    request: HttpRequest | None,
    status_code: int,
    code: str,
    message: str | StrPromise | None = None,
) -> JsonResponse:
    """An envelope response for code that runs outside DRF (middleware, Django handlers)."""
    request_id = getattr(request, "request_id", None) if request is not None else None
    body = envelope(code, message if message is not None else MESSAGES[code], None, request_id)
    return JsonResponse(body, status=status_code)


class ApiError(APIException):
    """Base for expected failures. ``detail`` must be safe to show to users."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "bad_request"
    default_detail = _("That request can't be completed.")


class ConflictError(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = MESSAGES["conflict"]


class GoneError(ApiError):
    status_code = status.HTTP_410_GONE
    default_code = "gone"
    default_detail = MESSAGES["gone"]
