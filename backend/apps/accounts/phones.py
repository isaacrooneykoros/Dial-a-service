"""Kenyan phone numbers, in one place (kickoff T05; ADR-0002 section 2).

Every phone number entering the system goes through ``normalize_ke_phone``,
which accepts the forms people type (X-10: 07..., 01..., 7..., 1..., plus
+254... and 254..., with spaces, dashes or brackets) and stores E.164:
+2547XXXXXXXX or +2541XXXXXXXX. Only mobile numbers are accepted, because
sign-in codes and M-Pesa prompts go to mobiles.

Display formats follow 10-screens-shared.md: "0712 345 678", masked in lists
as "0712 ••• 678".
"""

import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType

REGION = "KE"
_ALLOWED_CHARACTERS = re.compile(r"^[\d\s\-().+]+$")
_E164_KE_MOBILE = re.compile(r"^\+254[17]\d{8}$")
_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}


class InvalidPhoneError(ValueError):
    """Not a Kenyan mobile number. ``code`` says why, for the API's field errors."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_ke_phone(raw: str) -> str:
    """Return the E.164 form of a Kenyan mobile number, or raise InvalidPhoneError."""
    text = (raw or "").strip()
    if not text or not _ALLOWED_CHARACTERS.fullmatch(text):
        raise InvalidPhoneError("invalid_phone")

    digits = re.sub(r"\D", "", text)
    if text.startswith("+") or (digits.startswith("254") and len(digits) == 12):
        candidate = "+" + digits
    else:
        candidate = digits

    try:
        number = phonenumbers.parse(candidate, REGION)
    except NumberParseException as exc:
        raise InvalidPhoneError("invalid_phone") from exc

    if number.country_code != 254 or not phonenumbers.is_valid_number(number):
        raise InvalidPhoneError("invalid_phone")
    if phonenumbers.number_type(number) not in _MOBILE_TYPES:
        raise InvalidPhoneError("not_mobile")

    e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    if not _E164_KE_MOBILE.fullmatch(e164):
        raise InvalidPhoneError("not_mobile")
    return e164


def format_local(e164: str) -> str:
    """'+254712345678' -> '0712 345 678' (the on-screen format)."""
    national = "0" + e164.removeprefix("+254")
    return f"{national[:4]} {national[4:7]} {national[7:]}"


def mask_phone(e164: str) -> str:
    """'+254712345678' -> '0712 ••• 678' (lists and public pages)."""
    national = "0" + e164.removeprefix("+254")
    return f"{national[:4]} ••• {national[7:]}"
