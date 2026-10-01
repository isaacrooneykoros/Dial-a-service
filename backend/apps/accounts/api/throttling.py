"""Sign-in and code throttles, keyed by business plus phone or IP (ADR-0002 section 9)."""

import hashlib

from rest_framework.request import Request

from apps.accounts.phones import InvalidPhoneError, normalize_ke_phone
from apps.core.api.throttling import BusinessIPThrottle, BusinessThrottle


class PhoneThrottle(BusinessThrottle):
    """Per phone number in the request body, normalised when possible."""

    def subject(self, request: Request) -> str | None:
        raw = str(request.data.get("phone", "")) if hasattr(request, "data") else ""
        if not raw:
            return None
        try:
            return normalize_ke_phone(raw)
        except InvalidPhoneError:
            # Never put what the user typed into a cache key; hash it.
            return "raw-" + hashlib.sha256(raw.strip().encode()).hexdigest()[:32]


class LoginPhoneThrottle(PhoneThrottle):
    scope = "login_phone"


class LoginIPThrottle(BusinessIPThrottle):
    scope = "login_ip"


class CodeSendIPThrottle(BusinessIPThrottle):
    scope = "code_ip"


class CodeCheckIPThrottle(BusinessIPThrottle):
    scope = "code_check_ip"
