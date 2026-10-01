"""Sending notifications (CLAUDE.md section 6.4: never inline in a request).

    send_sms("phone_code", to="+254712345678", context={"code": "123456", ...})

writes a Notification and an outbox event in the caller's transaction. Nothing
is sent until that transaction commits; then the worker renders and sends it
(apps/notifications/handlers.py).
"""

from typing import Any

from apps.core.outbox import emit
from apps.notifications.catalogue import FALLBACK_LANGUAGE, SMS, get_event
from apps.notifications.models import Notification, NotificationTemplate

NOTIFICATION_SEND = "notification.send"
MASK = "••••"


def template_text(event_key: str, language: str, channel: str = SMS) -> str:
    """The business's own template, else the catalogue default; English if missing."""
    event = get_event(event_key)
    for lang in dict.fromkeys([language, FALLBACK_LANGUAGE]):
        custom = (
            NotificationTemplate.objects.filter(event=event_key, channel=channel, language=lang)
            .values_list("body", flat=True)
            .first()
        )
        if custom is not None:
            return str(custom)
        if lang in event.defaults:
            return event.defaults[lang]
    raise LookupError(f"No {channel} text for {event_key!r}.")


def render(event_key: str, language: str, context: dict[str, Any], *, masked: bool = False) -> str:
    event = get_event(event_key)
    missing = event.placeholders - set(context)
    if missing:
        raise KeyError(f"Missing values for {event_key!r}: {sorted(missing)}")
    values = {
        name: (MASK if masked and name in event.sensitive else str(context[name]))
        for name in event.placeholders
    }
    return template_text(event_key, language).format_map(values)


def send_sms(
    event_key: str,
    *,
    to: str,
    context: dict[str, Any],
    language: str = FALLBACK_LANGUAGE,
    recipient: Any = None,
) -> Notification:
    """Queue an SMS for the current business. It is sent after the transaction commits."""
    render(event_key, language, context)  # fail now, in the caller, if a value is missing
    notification: Notification = Notification.objects.create(
        recipient_phone=to,
        recipient=recipient,
        event=event_key,
        channel=SMS,
        language=language,
        context=context,
    )
    emit(NOTIFICATION_SEND, {"notification_id": str(notification.pk)})
    return notification
