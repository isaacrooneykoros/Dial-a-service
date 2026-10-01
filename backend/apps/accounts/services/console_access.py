"""A-42 in the console: signed-in sessions and registered devices (ADR-0002 sections 3 and 7).

Owners see and manage everything. Managers see devices of their own branches
and sessions of everyone except owners ("Team, devices: Yes, except owners").
"""

from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.services.auth import revoke_session
from apps.branches.selectors import member_branch_ids
from apps.core import audit


def visible_sessions(viewer: User) -> QuerySet[UserSession]:
    sessions = UserSession.objects.select_related("user", "device").filter(
        revoked_at__isnull=True, expires_at__gt=timezone.now()
    )
    if viewer.role != Role.OWNER:
        sessions = sessions.exclude(user__role=Role.OWNER)
    return sessions.order_by("-last_seen_at")


def visible_devices(viewer: User) -> QuerySet[Device]:
    devices = Device.objects.select_related("branch", "registered_by").exclude(
        status=Device.Status.REMOVED
    )
    if viewer.role != Role.OWNER:
        devices = devices.filter(branch_id__in=member_branch_ids(viewer.pk))
    return devices.order_by("branch__name", "name")


def sign_out_session(session: UserSession, *, viewer: User, request: Any = None) -> None:
    revoke_session(session, reason="signed_out_by_console", request=request)


def remove_device(device: Device, *, viewer: User, request: Any = None) -> int:
    """Remove a device; every session on it ends at once (A-42). Returns how many ended."""
    device.status = Device.Status.REMOVED
    device.save(update_fields=["status", "updated_at"])
    ended = 0
    for session in UserSession.objects.filter(
        device=device, revoked_at__isnull=True
    ).select_for_update():
        revoke_session(session, reason="device_removed", request=request)
        ended += 1
    audit.record("device.remove", obj=device, actor=viewer, request=request, device_id=device.pk)
    return ended
