"""SMS codes for password reset and invitations (ADR-0002 section 4; X-11, X-12).

- 6 digits from ``secrets``, stored as HMAC-SHA256 with OTP_HASH_KEY.
- Valid for 10 minutes; 5 wrong tries kill it; a new code cancels the old one.
- At most 3 sends per phone per hour, at least 60 seconds apart (per business).
- A correct code yields a single-use grant valid for 10 minutes, spent by the
  next step (setting a password).

Functions return results instead of raising, so callers can return an error
response *and* keep what changed (an attempt counted, a send recorded).
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import PhoneOTP
from apps.core.messaging import request_sms
from apps.core.tenant_context import get_current_business_id
from apps.tenancy.selectors import support_contact

CODE_LIFETIME = timedelta(minutes=10)  # X-12
GRANT_LIFETIME = timedelta(minutes=10)  # ADR-0002 section 5
MAX_ATTEMPTS = 5  # X-12
SENDS_PER_HOUR = 3  # X-11
MIN_SEND_INTERVAL = timedelta(seconds=60)  # X-12 resend countdown


def _hash(value: str) -> str:
    return hmac.new(settings.OTP_HASH_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    retry_after: int | None = None  # seconds, when refused


def send_code(
    phone: str,
    purpose: str,
    *,
    deliver: bool = True,
    language: str = "en",
    recipient: Any = None,
) -> SendResult:
    """Issue a code for ``phone`` and queue the SMS.

    With ``deliver=False`` (no account for this phone) nothing usable is created
    or sent, but the attempt still counts towards the limits, so responses and
    limits look the same whether or not the phone has an account.
    """
    now = timezone.now()
    recent = list(
        PhoneOTP.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1))
        .order_by("-created_at")
        .values_list("created_at", flat=True)
    )
    if recent and now - recent[0] < MIN_SEND_INTERVAL:
        wait = MIN_SEND_INTERVAL - (now - recent[0])
        return SendResult(ok=False, retry_after=max(1, int(wait.total_seconds())))
    if len(recent) >= SENDS_PER_HOUR:
        oldest = recent[SENDS_PER_HOUR - 1]
        wait = oldest + timedelta(hours=1) - now
        return SendResult(ok=False, retry_after=max(1, int(wait.total_seconds())))

    PhoneOTP.objects.filter(
        phone=phone, purpose=purpose, used_at__isnull=True, invalidated_at__isnull=True
    ).update(invalidated_at=now)

    code = _new_code()
    PhoneOTP.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=_hash(code),
        expires_at=now + CODE_LIFETIME,
        # Without an account the row only counts towards the limits.
        used_at=None if deliver else now,
    )
    if deliver:
        business_name, _ = support_contact(get_current_business_id())
        request_sms(
            "phone_code",
            to=phone,
            context={"code": code, "business": business_name},
            language=language,
            recipient_id=getattr(recipient, "pk", None),
        )
    return SendResult(ok=True)


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    reason: str = ""  # invalid_code, code_expired, code_locked
    attempts_left: int | None = None
    grant: str = ""  # raw grant token on success


def verify_code(phone: str, purpose: str, code: str) -> VerifyResult:
    otp = (
        PhoneOTP.objects.select_for_update()
        .filter(phone=phone, purpose=purpose, used_at__isnull=True, invalidated_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        return VerifyResult(ok=False, reason="invalid_code")
    now = timezone.now()
    if otp.expires_at <= now:
        return VerifyResult(ok=False, reason="code_expired")
    if otp.attempts >= MAX_ATTEMPTS:
        return VerifyResult(ok=False, reason="code_locked", attempts_left=0)

    if not hmac.compare_digest(otp.code_hash, _hash(code.strip())):
        otp.attempts += 1
        otp.save(update_fields=["attempts", "updated_at"])
        left = MAX_ATTEMPTS - otp.attempts
        return VerifyResult(
            ok=False, reason="code_locked" if left == 0 else "invalid_code", attempts_left=left
        )

    grant = secrets.token_urlsafe(32)
    otp.used_at = now
    otp.grant_hash = _hash(grant)
    otp.grant_expires_at = now + GRANT_LIFETIME
    otp.save(update_fields=["used_at", "grant_hash", "grant_expires_at", "updated_at"])
    return VerifyResult(ok=True, grant=grant)


def spend_grant(grant: str, purpose: str) -> PhoneOTP | None:
    """The verified code behind ``grant`` if it is unused and unexpired; marks it spent."""
    if not grant:
        return None
    otp: PhoneOTP | None = (
        PhoneOTP.objects.select_for_update()
        .filter(grant_hash=_hash(grant), purpose=purpose, grant_used_at__isnull=True)
        .first()
    )
    if otp is None or otp.grant_expires_at is None or otp.grant_expires_at <= timezone.now():
        return None
    otp.grant_used_at = timezone.now()
    otp.save(update_fields=["grant_used_at", "updated_at"])
    return otp
