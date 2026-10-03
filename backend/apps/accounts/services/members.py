"""People added directly, without an invitation: a new business's owner
(create_business) and development seed data (seed_dev). Everyone else joins
through an invitation (services/invitations.py)."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.accounts.phones import normalize_ke_phone
from apps.accounts.services.pins import PIN_ROLES, PinError, check_pin_format
from apps.branches.models import Branch
from apps.branches.services import add_member
from apps.core import audit


@dataclass(frozen=True)
class MemberDetails:
    phone: str
    first_name: str
    last_name: str
    role: Role
    password: str
    branches: Iterable[Branch] = field(default_factory=tuple)
    pin: str | None = None


def _apply_pin(user: User, pin: str | None) -> None:
    if pin is None:
        return
    if user.role not in PIN_ROLES:
        raise PinError("pin_not_for_role")
    check_pin_format(pin)
    user.pin_hash = make_password(pin)
    user.pin_set_at = timezone.now()


def create_member(details: MemberDetails) -> User:
    """A verified person in the current business, with password, branches and PIN.

    Raises ValidationError for a weak password or a bad phone number, PinError
    for a bad PIN.
    """
    user = User(
        phone=normalize_ke_phone(details.phone),
        first_name=details.first_name,
        last_name=details.last_name,
        role=details.role,
        is_phone_verified=True,
    )
    validate_password(details.password, user)
    user.set_password(details.password)
    _apply_pin(user, details.pin)
    user.save()
    add_member(user.pk, details.branches)
    audit.record("user.create", obj=user, after={"role": user.role})
    return user


def ensure_member(details: MemberDetails) -> User:
    """For seed data: the person with this phone, created if missing. An existing
    person gets the given password and PIN again, so the printed logins always work."""
    existing = User.objects.filter(phone=normalize_ke_phone(details.phone)).first()
    if existing is None:
        return create_member(details)
    validate_password(details.password, existing)
    existing.set_password(details.password)
    _apply_pin(existing, details.pin)
    existing.save()
    add_member(existing.pk, details.branches)
    return existing
