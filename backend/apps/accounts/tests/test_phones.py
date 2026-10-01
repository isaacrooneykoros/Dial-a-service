"""Kenyan phone numbers in every form people type (kickoff T05, X-10, ADR-0002 section 2)."""

import pytest

from apps.accounts.phones import InvalidPhoneError, format_local, mask_phone, normalize_ke_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The forms listed in the kickoff: 07..., 01..., 7..., 1..., +254..., 254...
        ("0712345678", "+254712345678"),
        ("0110345678", "+254110345678"),
        ("712345678", "+254712345678"),
        ("110345678", "+254110345678"),
        ("+254712345678", "+254712345678"),
        ("254712345678", "+254712345678"),
        ("+254110345678", "+254110345678"),
        ("254100123456", "+254100123456"),
        # Spacing and punctuation people use
        ("0712 345 678", "+254712345678"),
        ("0712-345-678", "+254712345678"),
        ("+254 (0) 712 345 678", "+254712345678"),
        ("  0712345678  ", "+254712345678"),
        ("+254-712-345-678", "+254712345678"),
    ],
)
def test_accepts_kenyan_mobiles(raw: str, expected: str) -> None:
    assert normalize_ke_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "invalid_phone"),
        ("   ", "invalid_phone"),
        ("phone", "invalid_phone"),
        ("07123x5678", "invalid_phone"),
        ("071234567", "invalid_phone"),  # too short
        ("07123456789", "invalid_phone"),  # too long
        ("0812345678", "invalid_phone"),  # not a Kenyan prefix
        ("+255712345678", "invalid_phone"),  # Tanzania
        ("+14155550123", "invalid_phone"),  # USA
        ("0202345678", "not_mobile"),  # Nairobi landline
    ],
)
def test_refuses_everything_else(raw: str, code: str) -> None:
    with pytest.raises(InvalidPhoneError) as excinfo:
        normalize_ke_phone(raw)
    assert excinfo.value.code == code


def test_none_is_refused() -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_ke_phone(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("e164", "local", "masked"),
    [
        ("+254712345678", "0712 345 678", "0712 ••• 678"),
        ("+254110345678", "0110 345 678", "0110 ••• 678"),
    ],
)
def test_display_formats_from_the_content_rules(e164: str, local: str, masked: str) -> None:
    assert format_local(e164) == local
    assert mask_phone(e164) == masked


@pytest.mark.parametrize("raw", ["+", "---", "()"])
def test_punctuation_without_digits(raw: str) -> None:
    with pytest.raises(InvalidPhoneError) as excinfo:
        normalize_ke_phone(raw)
    assert excinfo.value.code == "invalid_phone"


def test_a_future_mobile_range_outside_07_and_01_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage only accepts +2547/+2541 numbers; a new range needs a deliberate change."""
    import phonenumbers

    monkeypatch.setattr(phonenumbers, "format_number", lambda *args: "+254912345678")
    with pytest.raises(InvalidPhoneError) as excinfo:
        normalize_ke_phone("0712345678")
    assert excinfo.value.code == "not_mobile"
