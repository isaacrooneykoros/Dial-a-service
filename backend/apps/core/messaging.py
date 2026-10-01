"""Ask for a message to be sent, from any app (CLAUDE.md section 6.4).

Apps earlier in the dependency order (accounts, branches...) can't import the
notifications app, which depends on them. They call ``request_sms()``, which only
writes an outbox event in the current transaction; the notifications app handles
it after commit (creates the Notification, removes codes from the event, sends).
"""

from typing import Any

from apps.core.outbox import emit

NOTIFICATION_REQUEST = "notification.request"


def request_sms(
    event: str,
    *,
    to: str,
    context: dict[str, Any],
    language: str = "en",
    recipient_id: Any = None,
) -> None:
    emit(
        NOTIFICATION_REQUEST,
        {
            "event": event,
            "to": to,
            "context": context,
            "language": language,
            "recipient_id": str(recipient_id) if recipient_id else None,
        },
    )
