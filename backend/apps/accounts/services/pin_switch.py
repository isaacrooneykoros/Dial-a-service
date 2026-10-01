"""X-15 switch user, the 5-wrong-PIN lock and unlocking (ADR-0002 section 7).

Owner decision D-37: a locked device is unlocked by a manager or owner of its
branch signing in on it with phone and password.
"""

from dataclasses import dataclass
from typing import Any

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.services.auth import SignedIn, _start_session, revoke_session
from apps.accounts.services.devices import roster
from apps.branches.selectors import member_branch_ids
from apps.core import audit

MAX_WRONG_PINS = 5  # X-15


@dataclass(frozen=True)
class SwitchResult:
    ok: bool
    reason: str = ""  # wrong_pin, device_locked
    attempts_left: int | None = None
    signed_in: SignedIn | None = None


def switch_user(device: Device, *, user_id: Any, pin: str, request: Any = None) -> SwitchResult:
    """Sign a person in on a registered device with their PIN.

    Returns (doesn't raise) so a wrong PIN still counts towards the lock. An
    unknown person counts as a wrong PIN, so the roster can't be probed.
    """
    device = Device.objects.select_for_update().get(pk=device.pk)
    if device.status == Device.Status.LOCKED:
        return SwitchResult(ok=False, reason="device_locked", attempts_left=0)

    person = next((user for user in roster(device) if str(user.pk) == str(user_id)), None)
    if person is None or not check_password(pin, person.pin_hash):
        device.failed_pin_attempts += 1
        left = max(0, MAX_WRONG_PINS - device.failed_pin_attempts)
        fields = ["failed_pin_attempts", "updated_at"]
        if left == 0:
            device.status = Device.Status.LOCKED
            device.locked_at = timezone.now()
            fields += ["status", "locked_at"]
        device.save(update_fields=fields)
        if left == 0:
            audit.record("device.locked", obj=device, request=request, device_id=device.pk)
            return SwitchResult(ok=False, reason="device_locked", attempts_left=0)
        return SwitchResult(ok=False, reason="wrong_pin", attempts_left=left)

    device.failed_pin_attempts = 0
    device.last_seen_at = timezone.now()
    device.save(update_fields=["failed_pin_attempts", "last_seen_at", "updated_at"])
    for previous in UserSession.objects.filter(
        device=device, kind=UserSession.Kind.PIN, revoked_at__isnull=True
    ).select_for_update():
        revoke_session(previous, reason="pin_switch", request=request)
    signed_in = _start_session(person, request, UserSession.Kind.PIN, device=device)
    audit.record(
        "auth.pin_switch", obj=signed_in.session, actor=person, request=request, device_id=device.pk
    )
    return SwitchResult(ok=True, signed_in=signed_in)


def can_unlock(user: User, device: Device) -> bool:
    if user.role == Role.OWNER:
        return True
    return user.role == Role.MANAGER and device.branch_id in member_branch_ids(user.pk)


def unlock_on_sign_in(device: Device, user: User, *, request: Any = None) -> bool:
    """D-37: a manager or owner signing in on a locked device unlocks it."""
    if device.status != Device.Status.LOCKED or not can_unlock(user, device):
        return False
    device.status = Device.Status.ACTIVE
    device.failed_pin_attempts = 0
    device.locked_at = None
    device.save(update_fields=["status", "failed_pin_attempts", "locked_at", "updated_at"])
    audit.record("device.unlock", obj=device, actor=user, request=request, device_id=device.pk)
    return True
