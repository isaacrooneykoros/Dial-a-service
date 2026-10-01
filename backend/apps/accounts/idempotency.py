"""Idempotency-Key handling for POSTs (CLAUDE.md section 6.5; ADR-0002 section 8).

- Signed-in POSTs under /api/v1 must carry an ``Idempotency-Key`` header.
- The first response is stored for 24 hours per business, user and key; a repeat
  returns it (header ``Idempotent-Replayed: true``) without running the view.
- The same key with a different method, path or body returns 409.
- The key row is written in the request's transaction, so if the request fails
  with a 5xx (rolled back), the key disappears and a retry runs normally.

Not stored:
- /api/v1/auth/*: its responses carry access tokens (ADR-0002 section 8).
- Responses that set cookies (registering a device sets the device token):
  storing them would store the secret. A retry of those runs again.

Lives in accounts, not core, because it reads the access token to know who is
calling (core can't depend on accounts, CLAUDE.md section 6.6).
"""

import hashlib
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.tokens import InvalidAccessTokenError, read_access_token
from apps.core.api.errors import error_json
from apps.core.audit import client_ip
from apps.core.models import IdempotencyKey

HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"
LIFETIME = timedelta(hours=24)
API_PREFIX = "/api/v1/"
EXCLUDED_PREFIXES = ("/api/v1/auth/",)
_VALID_KEY = re.compile(r"^[A-Za-z0-9_-]{8,100}$")

MESSAGES = {
    "idempotency_key_required": _("Something went wrong sending that. Please try again."),
    "idempotency_key_invalid": _("Something went wrong sending that. Please try again."),
    "idempotency_key_reused": _(
        "That was already sent with different details. Refresh and try again."
    ),
    "idempotency_in_progress": _("We're still working on that. Wait a moment, then refresh."),
}

GetResponse = Callable[[HttpRequest], HttpResponseBase]


def _caller(request: HttpRequest) -> tuple[str | None, bool]:
    """(user ID from a valid token for this business, whether a token was sent at all)."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, bool(header)
    try:
        claims = read_access_token(parts[1])
    except InvalidAccessTokenError:
        return None, True
    business = getattr(request, "business", None)
    if business is None or claims.business_id != business.id:
        return None, True
    return str(claims.user_id), True


def _fail(request: HttpRequest, status: int, code: str) -> HttpResponseBase:
    return error_json(request, status, code, MESSAGES[code])


class IdempotencyMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def applies(self, request: HttpRequest) -> bool:
        path = request.path_info
        return (
            request.method == "POST"
            and path.startswith(API_PREFIX)
            and not path.startswith(EXCLUDED_PREFIXES)
            and getattr(request, "business", None) is not None
        )

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        if not self.applies(request):
            return self.get_response(request)

        key = request.META.get("HTTP_IDEMPOTENCY_KEY", "")
        user_id, sent_token = _caller(request)
        if sent_token and user_id is None:
            return self.get_response(request)  # a bad token: the view answers 401
        if not key:
            if user_id is not None:
                return _fail(request, 400, "idempotency_key_required")
            return self.get_response(request)  # anonymous, no key: nothing to do
        if not _VALID_KEY.fullmatch(key):
            return _fail(request, 400, "idempotency_key_invalid")

        scope = user_id or f"ip:{client_ip(request) or 'unknown'}"
        body_hash = hashlib.sha256(request.body).hexdigest()
        row, replay = self.claim(request, scope, key, body_hash)
        if replay is not None or row is None:
            return replay or self.get_response(request)

        response = self.get_response(request)
        self.remember(row, response)
        return response

    def claim(
        self, request: HttpRequest, scope: str, key: str, body_hash: str
    ) -> tuple[IdempotencyKey | None, HttpResponseBase | None]:
        """Reserve the key, or return the response to give instead."""
        now = timezone.now()
        fields: dict[str, Any] = {
            "scope": scope,
            "key": key,
            "method": request.method or "",
            "path": request.path_info,
            "body_hash": body_hash,
            "expires_at": now + LIFETIME,
        }
        try:
            with transaction.atomic():
                return IdempotencyKey.objects.create(**fields), None
        except IntegrityError:
            pass

        existing = IdempotencyKey.objects.select_for_update().get(scope=scope, key=key)
        if existing.expires_at <= now:
            existing.delete()
            return IdempotencyKey.objects.create(**fields), None
        if (existing.method, existing.path, existing.body_hash) != (
            fields["method"],
            fields["path"],
            body_hash,
        ):
            return None, _fail(request, 409, "idempotency_key_reused")
        if existing.response_status is None:
            return None, _fail(request, 409, "idempotency_in_progress")
        replay = HttpResponse(
            existing.response_body,
            status=existing.response_status,
            content_type=existing.response_content_type or "application/json",
        )
        replay[REPLAYED_HEADER] = "true"
        return None, replay

    def remember(self, row: IdempotencyKey, response: HttpResponseBase) -> None:
        if response.status_code >= 500 or transaction.get_rollback():
            # The request's transaction is rolled back (a crash, or an error the
            # view raised), so the key row goes with it and a retry runs again.
            return
        if response.cookies or response.streaming:
            row.delete()  # never store secrets; let a retry run again
            return
        content = getattr(response, "content", b"")
        row.response_status = response.status_code
        row.response_body = content.decode("utf-8", errors="replace")
        row.response_content_type = response.get("Content-Type", "")
        row.save(
            update_fields=[
                "response_status",
                "response_body",
                "response_content_type",
                "updated_at",
            ]
        )
