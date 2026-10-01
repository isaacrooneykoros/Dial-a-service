"""Inviting people (A-41) and accepting an invitation (X-14 -> X-12 -> X-13).

ADR-0002 section 6; owner decisions D-19, D-26 and D-28 (no plan limits in M1).
"""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import (
    INVITABLE_ROLES,
    ROLE_LABELS,
    Invitation,
    InvitationBranch,
    PhoneOTP,
    Role,
    User,
    UserSession,
)
from apps.accounts.services import otp
from apps.accounts.services.auth import SignedIn, _start_session
from apps.branches.selectors import branches_by_ids, member_branch_ids
from apps.branches.services import add_member
from apps.core import audit
from apps.core.messaging import request_sms
from apps.core.tenant_context import get_current_business_id
from apps.tenancy.selectors import primary_host, support_contact

INVITATION_LIFETIME = timedelta(days=7)  # X-14
ROLES_NEEDING_A_BRANCH = (Role.MANAGER, Role.STAFF)


class InvitationError(Exception):
    """A rule refused the invitation. ``code`` and ``field`` go into the error envelope."""

    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


@dataclass
class InvitationDetails:
    phone: str
    first_name: str
    last_name: str
    role: str
    branch_ids: list[Any] = field(default_factory=list)
    can_accept_cash: bool = False
    can_give_discounts: bool = False
    can_correct_prices: bool = False


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def invite_link(token: str) -> str:
    host = primary_host(get_current_business_id())
    return f"{settings.APP_LINK_SCHEME}://{host}{settings.APP_LINK_PORT}/invite/{token}"


def _send(invitation: Invitation, token: str) -> None:
    business_name, _ = support_contact(get_current_business_id())
    request_sms(
        "invitation",
        to=invitation.phone,
        context={
            "business": business_name,
            "role": ROLE_LABELS[invitation.role],
            "link": invite_link(token),
        },
    )


def _new_token(invitation: Invitation) -> str:
    token = secrets.token_urlsafe(32)
    invitation.token_hash = _hash(token)
    invitation.expires_at = timezone.now() + INVITATION_LIFETIME
    return token


def _check(inviter: User, details: InvitationDetails) -> list[Any]:
    if details.role not in INVITABLE_ROLES:
        raise InvitationError("role_not_allowed", "role")
    if User.objects.filter(phone=details.phone).exists():
        raise InvitationError("already_registered", "phone")
    branches = branches_by_ids(details.branch_ids)
    if len(branches) != len(set(details.branch_ids)):
        raise InvitationError("unknown_branch", "branch_ids")
    if details.role in ROLES_NEEDING_A_BRANCH and not branches:
        raise InvitationError("branch_required", "branch_ids")
    if inviter.role == Role.MANAGER:
        mine = member_branch_ids(inviter.pk)
        if any(branch.pk not in mine for branch in branches):
            raise InvitationError("not_your_branch", "branch_ids")
    return branches


def invite(inviter: User, details: InvitationDetails, *, request: Any = None) -> Invitation:
    """Create an invitation and text it. A second invitation to the same phone
    updates and resends the open one instead (ADR-0002 section 6)."""
    branches = _check(inviter, details)
    invitation = (
        Invitation.objects.select_for_update()
        .filter(phone=details.phone, accepted_at__isnull=True, cancelled_at__isnull=True)
        .first()
    )
    is_new = invitation is None
    if invitation is None:
        invitation = Invitation(phone=details.phone, invited_by=inviter, sent_count=0)
    for name in (
        "first_name",
        "last_name",
        "role",
        "can_accept_cash",
        "can_give_discounts",
        "can_correct_prices",
    ):
        setattr(invitation, name, getattr(details, name))
    token = _new_token(invitation)
    invitation.sent_count += 1
    invitation.save()
    InvitationBranch.objects.filter(invitation=invitation).delete()
    InvitationBranch.objects.bulk_create(
        [InvitationBranch(invitation=invitation, branch=branch) for branch in branches]
    )
    _send(invitation, token)
    audit.record(
        "invitation.create" if is_new else "invitation.resend",
        obj=invitation,
        after={"phone": invitation.phone, "role": invitation.role},
        actor=inviter,
        request=request,
    )
    return invitation


def resend(invitation: Invitation, *, actor: User, request: Any = None) -> Invitation:
    """A new link (the old one stops working) and another 7 days."""
    if invitation.accepted_at or invitation.cancelled_at:
        raise InvitationError("invitation_closed")
    token = _new_token(invitation)
    invitation.sent_count += 1
    invitation.save(update_fields=["token_hash", "expires_at", "sent_count", "updated_at"])
    _send(invitation, token)
    audit.record("invitation.resend", obj=invitation, actor=actor, request=request)
    return invitation


def cancel(invitation: Invitation, *, actor: User, request: Any = None) -> None:
    if invitation.accepted_at or invitation.cancelled_at:
        raise InvitationError("invitation_closed")
    invitation.cancelled_at = timezone.now()
    invitation.save(update_fields=["cancelled_at", "updated_at"])
    audit.record("invitation.cancel", obj=invitation, actor=actor, request=request)


def open_invitation(token: str) -> tuple[Invitation | None, str]:
    """The invitation behind a link, and why it can't be used ('' if it can)."""
    invitation = Invitation.objects.filter(token_hash=_hash(token)).first() if token else None
    if invitation is None:
        return None, "not_found"
    if invitation.accepted_at or invitation.cancelled_at or invitation.expires_at <= timezone.now():
        return invitation, "invitation_expired"
    return invitation, ""


def send_code(invitation: Invitation) -> otp.SendResult:
    return otp.send_code(invitation.phone, PhoneOTP.Purpose.INVITATION)


def verify_code(invitation: Invitation, code: str) -> otp.VerifyResult:
    return otp.verify_code(invitation.phone, PhoneOTP.Purpose.INVITATION, code)


def branch_ids_of(invitation: Invitation) -> list[Any]:
    return list(
        InvitationBranch.objects.filter(invitation=invitation).values_list("branch_id", flat=True)
    )


def accept(request: HttpRequest | None, *, setup_token: str, password: str) -> SignedIn:
    """Create the account from the invitation, add branches, sign in (X-13 in the X-14 flow).

    The password must already be validated by the serializer.
    """
    code = otp.spend_grant(setup_token, PhoneOTP.Purpose.INVITATION)
    invitation = (
        Invitation.objects.select_for_update()
        .filter(phone=code.phone, accepted_at__isnull=True, cancelled_at__isnull=True)
        .first()
        if code
        else None
    )
    if invitation is None or not invitation.is_open:
        raise InvitationError("invitation_expired")
    if User.objects.filter(phone=invitation.phone).exists():
        raise InvitationError("already_registered")

    user = User(
        phone=invitation.phone,
        first_name=invitation.first_name,
        last_name=invitation.last_name,
        role=invitation.role,
        is_phone_verified=True,
        can_accept_cash=invitation.can_accept_cash,
        can_give_discounts=invitation.can_give_discounts,
        can_correct_prices=invitation.can_correct_prices,
    )
    user.set_password(password)
    user.save()
    add_member(user.pk, branches_by_ids(branch_ids_of(invitation)))
    invitation.accepted_at = timezone.now()
    invitation.accepted_user = user
    invitation.save(update_fields=["accepted_at", "accepted_user", "updated_at"])
    audit.record("invitation.accept", obj=invitation, actor=user, request=request)
    return _start_session(user, request, UserSession.Kind.PASSWORD)
