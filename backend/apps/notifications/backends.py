"""SMS backends: one interface, swappable by the SMS_BACKEND setting.

- ConsoleSmsBackend (development): prints the full message to the terminal so
  you can read sign-in codes. It prints, never logs: logs must not contain codes.
- LocmemSmsBackend (tests): keeps messages in ``LocmemSmsBackend.outbox``.
- The real gateway backend arrives with the gateway decision (OPEN.md D-08, M4).

Only apps/notifications/handlers.py calls a backend (tests/test_code_rules.py).
"""

import itertools
import sys
from dataclasses import dataclass
from typing import ClassVar, Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class SentSms:
    to: str
    text: str
    message_id: str


class SmsBackend(Protocol):
    def send(self, to: str, text: str) -> SentSms: ...


class ConsoleSmsBackend:
    _ids = itertools.count(1)

    def send(self, to: str, text: str) -> SentSms:
        message_id = f"console-{next(self._ids)}"
        sys.stdout.write(f"\n=== SMS to {to} ({message_id}) ===\n{text}\n===\n")
        sys.stdout.flush()
        return SentSms(to=to, text=text, message_id=message_id)


class LocmemSmsBackend:
    outbox: ClassVar[list[SentSms]] = []
    _ids = itertools.count(1)

    def send(self, to: str, text: str) -> SentSms:
        sent = SentSms(to=to, text=text, message_id=f"locmem-{next(self._ids)}")
        self.outbox.append(sent)
        return sent


def get_sms_backend() -> SmsBackend:
    backend: SmsBackend = import_string(settings.SMS_BACKEND)()
    return backend


class DiscardSmsBackend:
    """Staging until the SMS gateway is chosen (OPEN.md D-08): nothing is sent,
    printed or kept, so codes never reach a log. Messages show as sent."""

    _ids = itertools.count(1)

    def send(self, to: str, text: str) -> SentSms:
        return SentSms(to=to, text="", message_id=f"discarded-{next(self._ids)}")
