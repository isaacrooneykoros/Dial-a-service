"""Personal 4-digit PINs for shared counter devices (X-15; ADR-0002 section 7).

M1 sets the first PIN at the end of the X-14 flow. Changing a PIN (S-30) needs
the current PIN or password and arrives with the staff app in M3.
"""

import re

from django.contrib.auth.hashers import make_password
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.core import audit

PIN_ROLES = (Role.OWNER, Role.MANAGER, Role.STAFF)  # the people who use counter devices
_FOUR_DIGITS = re.compile(r"^\d{4}$")

# PINs too easy to guess: repeated digits, straight runs, and the usual favourites.
COMMON_PINS = frozenset(
    {str(d) * 4 for d in range(10)}
    | {"0123", "1234", "2345", "3456", "4567", "5678", "6789"}
    | {"9876", "8765", "7654", "6543", "5432", "4321", "3210"}
    | {"1212", "1122", "1004", "2000", "2580", "6969", "1313", "0852", "1010", "2020"}
)


class PinError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_pin_format(pin: str) -> None:
    if not _FOUR_DIGITS.fullmatch(pin):
        raise PinError("pin_format")
    if pin in COMMON_PINS:
        raise PinError("pin_too_common")


def set_first_pin(user: User, pin: str, *, request: HttpRequest | None = None) -> None:
    if user.role not in PIN_ROLES:
        raise PinError("pin_not_for_role")
    if user.pin_hash:
        raise PinError("pin_already_set")
    check_pin_format(pin)
    user.pin_hash = make_password(pin)
    user.pin_set_at = timezone.now()
    user.save(update_fields=["pin_hash", "pin_set_at", "updated_at"])
    audit.record("user.pin_set", obj=user, actor=user, request=request)
