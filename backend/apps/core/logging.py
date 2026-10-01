"""Structured JSON logs that never contain phone numbers or secrets (CLAUDE.md section 6.7).

- Kenyan phone numbers anywhere in a message, exception or extra field are
  masked, keeping only enough to recognise them: +2547******78.
- Values under sensitive keys (passwords, PINs, codes, tokens, secrets,
  M-Pesa passkeys, cookies) are replaced with "[redacted]", however deeply
  they are nested.

This masking is a safety net. Code must still never log secrets on purpose.
"""

import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from apps.core.request_id import get_request_id

REDACTED = "[redacted]"

# +2547XXXXXXXX, 2547XXXXXXXX, 07XXXXXXXX, 01XXXXXXXX (and the +2541... range),
# not when part of a longer number.
_PHONE = re.compile(r"(?<![\d+])(?P<prefix>\+?254[17]|0[17])(?P<middle>\d{6})(?P<last>\d{2})(?!\d)")

# A key is sensitive if any of its parts (split on _ - and .) is one of these...
_SENSITIVE_PARTS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "passkey",
        "pin",
        "otp",
        "authorization",
        "cookie",
        "credentials",
        "csrftoken",
        "sessionid",
    }
)
# ...or the whole key is one of these (plain "code" is an SMS or collection code;
# "status_code" and similar are left alone).
_SENSITIVE_KEYS = frozenset(
    {
        "code",
        "otp_code",
        "sms_code",
        "verification_code",
        "collection_code",
        "delivery_code",
        "api_key",
        "access_key",
        "consumer_key",
        "set-cookie",
    }
)
# Words that are sensitive even inside a longer key ("userpassword", "authtoken").
# Short words like "pin" and "otp" only count as whole parts ("shipping" is fine).
_SENSITIVE_SUBSTRINGS = ("password", "passwd", "secret", "token", "passkey", "cookie", "authoriz")
_KEY_SPLIT = re.compile(r"[_\-.]")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Attributes every LogRecord has; anything else was passed with extra={...}.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def mask_phones(text: str) -> str:
    return _PHONE.sub(lambda m: m["prefix"] + "*" * len(m["middle"]) + m["last"], text)


def is_sensitive_key(key: str) -> bool:
    lowered = _CAMEL_BOUNDARY.sub("_", key).lower()
    if lowered in _SENSITIVE_KEYS:
        return True
    if any(word in lowered for word in _SENSITIVE_SUBSTRINGS):
        return True
    return any(part in _SENSITIVE_PARTS for part in _KEY_SPLIT.split(lowered))


def redact(value: Any) -> Any:
    """Redact sensitive keys at any depth, leaving other values as they are.

    For data owners are entitled to see (audit log before/after values), where
    phone numbers stay readable but secrets must never be stored.
    """
    if isinstance(value, Mapping):
        return {
            str(k): REDACTED if is_sensitive_key(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(v) for v in value]
    return value


def scrub(value: Any) -> Any:
    """Redact sensitive keys and mask phone numbers in any JSON-like value."""
    if isinstance(value, Mapping):
        return {
            str(k): REDACTED if is_sensitive_key(str(k)) else scrub(v) for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return mask_phones(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return mask_phones(str(value))


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, request_id, extras."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_phones(record.getMessage()),
        }
        request_id = get_request_id()
        if request_id:
            entry["request_id"] = request_id

        extras = {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}
        entry.update(scrub(extras))

        if record.exc_info:
            entry["exception"] = mask_phones(self.formatException(record.exc_info))
        if record.stack_info:
            entry["stack"] = mask_phones(self.formatStack(record.stack_info))

        return json.dumps(entry, default=str, ensure_ascii=False)
