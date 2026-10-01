"""Registered counter devices (S-02, X-15; ADR-0002 section 7)."""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.services.auth import revoke_session
from apps.accounts.services.pins import PIN_ROLES
from apps.branches.selectors import branches_by_ids, member_branch_ids, member_user_ids
from apps.core import audit

REGISTER_ROLES = (Role.OWNER, Role.MANAGER)  # S-02: manager or owner only


def hash_device_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class DeviceError(Exception):
    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


@dataclass(frozen=True)
class Registered:
    device: Device
    token: str  # raw; goes only into the httpOnly das_device cookie


def register_device(
    user: User,
    *,
    branch_id: Any,
    name: str,
    session: UserSession | None,
    request: Any = None,
) -> Registered:
    """Make this phone or tablet a shared counter device for a branch.

    Owners can register for any branch, managers only for their own. As S-02
    says, the person registering is signed out of the device, leaving it on the
    PIN screen.
    """
    if user.role not in REGISTER_ROLES:
        raise DeviceError("not_allowed")
    branches = branches_by_ids([branch_id])
    if not branches:
        raise DeviceError("unknown_branch", "branch_id")
    branch = branches[0]
    if user.role == Role.MANAGER and branch.pk not in member_branch_ids(user.pk):
        raise DeviceError("not_your_branch", "branch_id")

    raw = secrets.token_urlsafe(32)
    device = Device.objects.create(
        branch=branch, name=name, registered_by=user, token_hash=hash_device_token(raw)
    )
    audit.record(
        "device.register",
        obj=device,
        after={"name": name, "branch": str(branch.pk)},
        actor=user,
        request=request,
        device_id=device.pk,
    )
    if session is not None:
        revoke_session(session, reason="device_registered", request=request)
    return Registered(device=device, token=raw)


def device_from_token(raw: str) -> Device | None:
    """The registered device behind a cookie value (removed devices don't count)."""
    if not raw:
        return None
    device: Device | None = (
        Device.objects.select_related("branch")
        .filter(token_hash=hash_device_token(raw))
        .exclude(status=Device.Status.REMOVED)
        .first()
    )
    return device


def touch(device: Device) -> None:
    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at", "updated_at"])


def roster(device: Device) -> list[User]:
    """X-15: who can switch in here. Active owners, managers and staff of the
    device's branch who have set a PIN."""
    return list(
        User.objects.filter(
            pk__in=member_user_ids(device.branch_id),
            role__in=PIN_ROLES,
            status=User.Status.ACTIVE,
        )
        .exclude(pin_hash="")
        .order_by("first_name", "last_name")
    )
