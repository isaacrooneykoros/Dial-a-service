"""Sign-in, refresh and sign-out (ADR-0002 section 3; X-10).

All functions work for the current business (from the request's host).
"""

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import authenticate
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import User, UserSession
from apps.accounts.tokens import (
    REFRESH_TOKEN_LIFETIME,
    hash_refresh_token,
    issue_access_token,
    new_refresh_token,
)
from apps.core import audit
from apps.core.audit import client_ip


@dataclass(frozen=True)
class SignedIn:
    user: User
    session: UserSession
    access: str
    refresh: str  # raw; goes only into the httpOnly cookie


class InvalidCredentialsError(Exception):
    """Wrong phone or password. Never says which (X-10)."""


class AccountSuspendedError(Exception):
    """Correct password, but the account can't be used (X-10)."""

    def __init__(self, user: User) -> None:
        super().__init__(user.status)
        self.user = user


def _start_session(user: User, request: HttpRequest | None, kind: str) -> SignedIn:
    raw, hashed = new_refresh_token()
    now = timezone.now()
    session = UserSession.objects.create(
        user=user,
        kind=kind,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:255],
        ip=client_ip(request),
        last_seen_at=now,
        expires_at=now + REFRESH_TOKEN_LIFETIME,
        refresh_hash=hashed,
    )
    access = issue_access_token(
        user_id=user.pk, business_id=session.business_id, session_id=session.pk
    )
    return SignedIn(user=user, session=session, access=access, refresh=raw)


def login(request: HttpRequest | None, *, phone: str, password: str) -> SignedIn:
    """Phone and password; raises InvalidCredentialsError or AccountSuspendedError."""
    user = authenticate(request, phone=phone, password=password)
    if not isinstance(user, User):
        raise InvalidCredentialsError
    if not user.is_active:
        raise AccountSuspendedError(user)
    signed_in = _start_session(user, request, UserSession.Kind.PASSWORD)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    audit.record("auth.login", obj=signed_in.session, actor=user, request=request)
    return signed_in


@dataclass(frozen=True)
class Refreshed:
    ok: bool
    access: str = ""
    refresh: str = ""
    session: UserSession | None = None


def refresh(raw: str) -> Refreshed:
    """Rotate a refresh token. Returns (never raises) so a theft revocation is kept.

    Callers must return the failure response rather than raise: raising rolls
    back the request, which would undo the revocation.
    """
    if not raw:
        return Refreshed(ok=False)
    hashed = hash_refresh_token(raw)
    session = (
        UserSession.objects.select_for_update()
        .select_related("user")
        .filter(Q(refresh_hash=hashed) | Q(previous_refresh_hash=hashed))
        .first()
    )
    if session is None:
        return Refreshed(ok=False)
    if session.previous_refresh_hash == hashed:
        # An old token came back after rotation: someone else may hold it.
        revoke_session(session, reason="refresh_reuse")
        return Refreshed(ok=False)
    if not session.is_live or not session.user.is_active:
        return Refreshed(ok=False)

    new_raw, new_hash = new_refresh_token()
    session.previous_refresh_hash = session.refresh_hash
    session.refresh_hash = new_hash
    session.last_seen_at = timezone.now()
    session.save(update_fields=["previous_refresh_hash", "refresh_hash", "last_seen_at"])
    access = issue_access_token(
        user_id=session.user_id, business_id=session.business_id, session_id=session.pk
    )
    return Refreshed(ok=True, access=access, refresh=new_raw, session=session)


def revoke_session(session: UserSession, *, reason: str, request: Any = None) -> None:
    if session.revoked_at is not None:
        return
    session.revoked_at = timezone.now()
    session.revoke_reason = reason
    session.save(update_fields=["revoked_at", "revoke_reason"])
    audit.record("auth.session_revoked", obj=session, after={"reason": reason}, request=request)


def revoke_all_sessions(
    user: User, *, reason: str, keep: UserSession | None = None, request: Any = None
) -> int:
    """Sign a person out everywhere (password change or reset, deactivation)."""
    sessions = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if keep is not None:
        sessions = sessions.exclude(pk=keep.pk)
    count = 0
    for session in sessions.select_for_update():
        revoke_session(session, reason=reason, request=request)
        count += 1
    return count


def logout(session: UserSession, *, request: HttpRequest | None = None) -> None:
    revoke_session(session, reason="logout", request=request)
