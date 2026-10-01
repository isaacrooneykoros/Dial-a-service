"""Forgot password (X-11 to X-13) and change password (ADR-0002 section 5).

After a reset, every session is signed out and the person is signed in afresh
(X-13). After a change, every *other* session is signed out (C-47).
"""

from dataclasses import dataclass

from django.http import HttpRequest

from apps.accounts.models import PhoneOTP, User, UserSession
from apps.accounts.services import otp
from apps.accounts.services.auth import SignedIn, _start_session, revoke_all_sessions
from apps.core import audit


def request_reset(phone: str) -> otp.SendResult:
    """Send a reset code if ``phone`` has an active account here.

    Unknown phones get the same answer and count towards the same limits
    (X-11: "If this number has an account, we've sent a code").
    """
    user = User.objects.filter(phone=phone, status=User.Status.ACTIVE).first()
    return otp.send_code(
        phone,
        PhoneOTP.Purpose.PASSWORD_RESET,
        deliver=user is not None,
        language=user.language if user else "en",
        recipient=user,
    )


def verify_reset_code(phone: str, code: str) -> otp.VerifyResult:
    return otp.verify_code(phone, PhoneOTP.Purpose.PASSWORD_RESET, code)


class InvalidResetError(Exception):
    """The reset token is unknown, used, expired, or its account is gone."""


@dataclass(frozen=True)
class ResetDone:
    signed_in: SignedIn


def confirm_reset(request: HttpRequest | None, *, reset_token: str, password: str) -> ResetDone:
    """Set the new password, sign out everywhere, sign in here.

    The password must already be validated (the serializer does it, so a weak
    password never spends the token). Raises InvalidResetError for a bad token.
    """
    code = otp.spend_grant(reset_token, PhoneOTP.Purpose.PASSWORD_RESET)
    user = (
        User.objects.filter(phone=code.phone, status=User.Status.ACTIVE).first() if code else None
    )
    if user is None:
        raise InvalidResetError
    user.set_password(password)
    user.save(update_fields=["password", "updated_at"])
    revoke_all_sessions(user, reason="password_reset", request=request)
    signed_in = _start_session(user, request, UserSession.Kind.PASSWORD)
    audit.record("auth.password_reset", obj=user, actor=user, request=request)
    return ResetDone(signed_in=signed_in)


class WrongCurrentPasswordError(Exception):
    pass


def change_password(
    request: HttpRequest | None,
    *,
    user: User,
    session: UserSession,
    current_password: str,
    new_password: str,
) -> None:
    if not user.check_password(current_password):
        raise WrongCurrentPasswordError
    user.set_password(new_password)  # validated by the serializer
    user.save(update_fields=["password", "updated_at"])
    revoke_all_sessions(user, reason="password_changed", keep=session, request=request)
    audit.record("auth.password_changed", obj=user, actor=user, request=request)
