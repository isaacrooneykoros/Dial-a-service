"""Write audit log rows (CLAUDE.md section 6.7: every mutating action is audited).

    record("auth.login", actor=user, request=request)
    record("invitation.create", obj=invitation, after={"role": "staff"}, actor=user,
           request=request)

Rows are written in the caller's transaction, so an action that rolls back
leaves no audit row. Secrets in before/after values are redacted; phone numbers
stay readable because owners review them on A-63.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from apps.core.logging import redact
from apps.core.models import AuditLog
from apps.core.request_id import get_request_id
from apps.core.tenant_context import peek_current_business_id


def client_ip(request: HttpRequest | None) -> str | None:
    """The caller's IP address.

    Behind Render and Cloudflare this must read the trusted proxy header
    instead; that is configured with the deployment in T12.
    """
    if request is None:
        return None
    ip: str | None = request.META.get("REMOTE_ADDR") or None
    return ip


def record(
    action: str,
    *,
    obj: models.Model | None = None,
    object_type: str = "",
    object_id: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    actor: Any = None,
    request: HttpRequest | None = None,
    device_id: Any = None,
) -> AuditLog:
    if obj is not None:
        object_type = object_type or obj._meta.label_lower
        object_id = object_id or str(obj.pk)
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        actor = user if getattr(user, "is_authenticated", False) else None
    entry = AuditLog(
        action=action,
        object_type=object_type,
        object_id=object_id,
        before=redact(before) if before is not None else None,
        after=redact(after) if after is not None else None,
        actor=actor,
        ip=client_ip(request),
        device_id=device_id,
        request_id=get_request_id() or "",
    )
    entry.business_id = peek_current_business_id()
    entry.save(force_insert=True)
    return entry
