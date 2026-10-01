"""JSON logs mask phone numbers and redact secrets (M1 task T03a)."""

import json
import logging
import sys

import pytest

from apps.core.logging import (
    REDACTED,
    JsonFormatter,
    is_sensitive_key,
    mask_phones,
    scrub,
)
from apps.core.request_id import request_id_var


class TestMaskPhones:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("+254712345678", "+2547******78"),
            ("254712345678", "2547******78"),
            ("0712345678", "07******78"),
            ("0110345678", "01******78"),
            ("+254110345678", "+2541******78"),
            ("Sent code to +254712345678 at 10:42", "Sent code to +2547******78 at 10:42"),
            ("a 0712345678, b 0722000011", "a 07******78, b 07******11"),
            ("phone=0712345678;", "phone=07******78;"),
        ],
    )
    def test_masks_kenyan_numbers(self, text: str, expected: str) -> None:
        assert mask_phones(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Order MSF-7K3P9Q total KSh 1,250",
            "amount 1250.00",
            "status 200",
            "ref 20261001123456789",  # longer run of digits
            "0812345678",  # not a Kenyan mobile prefix
            "12345678",
        ],
    )
    def test_leaves_other_text_alone(self, text: str) -> None:
        assert mask_phones(text) == text


class TestSensitiveKeys:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "new_password",
            "currentPassword",
            "userpassword",
            "authToken",
            "staffPin",
            "deliveryCode",
            "pin",
            "staff_pin",
            "code",
            "otp",
            "otp_code",
            "access_token",
            "refresh-token",
            "setup_token",
            "reset_token",
            "secret",
            "consumer_secret",
            "passkey",
            "api_key",
            "consumer_key",
            "Authorization",
            "Cookie",
            "HTTP_COOKIE",
            "collection_code",
            "delivery_code",
        ],
    )
    def test_sensitive(self, key: str) -> None:
        assert is_sensitive_key(key)

    @pytest.mark.parametrize(
        "key",
        [
            "status_code",
            "error_code",
            "currency_code",
            "shipping",
            "mapping",
            "reference",
            "business_id",
            "idempotency_key",
        ],
    )
    def test_not_sensitive(self, key: str) -> None:
        assert not is_sensitive_key(key)


class TestScrub:
    def test_nested_values(self) -> None:
        data = {
            "phone": "+254712345678",
            "payload": {"password": "hunter22", "items": [{"pin": "1234", "note": "0712345678"}]},
            "count": 3,
            "ok": True,
            "missing": None,
        }
        assert scrub(data) == {
            "phone": "+2547******78",
            "payload": {"password": REDACTED, "items": [{"pin": REDACTED, "note": "07******78"}]},
            "count": 3,
            "ok": True,
            "missing": None,
        }

    def test_other_objects_become_masked_strings(self) -> None:
        class Thing:
            def __str__(self) -> str:
                return "user 0712345678"

        assert scrub(Thing()) == "user 07******78"


def make_record(msg: str, *args: object, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("apps.test", logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestJsonFormatter:
    def format(self, record: logging.LogRecord) -> dict[str, object]:
        result: dict[str, object] = json.loads(JsonFormatter().format(record))
        return result

    def test_basic_fields(self) -> None:
        entry = self.format(make_record("hello %s", "world"))
        assert entry["message"] == "hello world"
        assert entry["level"] == "INFO"
        assert entry["logger"] == "apps.test"
        assert str(entry["time"]).endswith("+00:00")
        assert "request_id" not in entry

    def test_includes_request_id_when_set(self) -> None:
        token = request_id_var.set("abc123def456")
        try:
            entry = self.format(make_record("x"))
        finally:
            request_id_var.reset(token)
        assert entry["request_id"] == "abc123def456"

    def test_masks_phones_in_message_args(self) -> None:
        entry = self.format(make_record("code sent to %s", "+254712345678"))
        assert entry["message"] == "code sent to +2547******78"

    def test_scrubs_extra_fields(self) -> None:
        entry = self.format(make_record("login", phone="0712345678", password="pw", attempts=2))
        assert entry["phone"] == "07******78"
        assert entry["password"] == REDACTED
        assert entry["attempts"] == 2

    def test_masks_phones_in_exceptions(self) -> None:
        try:
            raise ValueError("no account for 0712345678")
        except ValueError:
            record = make_record("failed")
            record.exc_info = sys.exc_info()
        entry = self.format(record)
        assert "07******78" in str(entry["exception"])
        assert "0712345678" not in str(entry["exception"])

    def test_masks_phones_in_stack_info(self) -> None:
        record = make_record("x")
        record.stack_info = 'File "x.py", line 1, in lookup(0712345678)'
        entry = self.format(record)
        assert "07******78" in str(entry["stack"])

    def test_output_is_one_line(self) -> None:
        assert "\n" not in JsonFormatter().format(make_record("a\nb"))


def test_redact_keeps_phones_but_removes_secrets() -> None:
    from apps.core.logging import redact

    data = {"phone": "+254712345678", "pin": "1234", "nested": [{"token": "t", "n": 1}]}
    assert redact(data) == {
        "phone": "+254712345678",
        "pin": REDACTED,
        "nested": [{"token": REDACTED, "n": 1}],
    }
    assert redact("plain") == "plain"
