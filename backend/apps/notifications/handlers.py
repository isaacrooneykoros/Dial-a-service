"""Outbox handlers that send notifications.

- ``notification.request`` (from apps.core.messaging.request_sms): creates the
  Notification, removes sensitive values from the outbox event, then sends.
- ``notification.send`` (from send_sms, and for retries): sends a Notification.

Retries follow the catalogue rule: "A failed SMS is retried 3 times over 15
minutes, then logged ... A failed message never blocks an order." So a failure
schedules the next try 5 minutes later through a new outbox event and never
raises; after the third retry the notification is marked failed.

Safe to run twice (the outbox delivers at least once): a notification that is
no longer pending is left alone, and a request already turned into a
notification isn't turned into another.
"""

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.core.messaging import NOTIFICATION_REQUEST
from apps.core.models import OutboxEvent
from apps.core.outbox import emit, register_handler
from apps.notifications.backends import get_sms_backend
from apps.notifications.catalogue import get_event
from apps.notifications.models import Notification
from apps.notifications.services import NOTIFICATION_SEND, render

logger = logging.getLogger(__name__)

RETRIES = 3
RETRY_INTERVAL = timedelta(minutes=5)  # 3 retries over 15 minutes


def scrub_context(event_key: str, context: dict[str, Any]) -> dict[str, Any]:
    sensitive = get_event(event_key).sensitive
    return {key: value for key, value in context.items() if key not in sensitive}


@register_handler(NOTIFICATION_REQUEST)
def create_requested_notification(event: OutboxEvent) -> None:
    payload = event.payload
    if payload.get("notification_id"):
        return  # already turned into a notification
    render(payload["event"], payload["language"], payload["context"])  # fail on bad requests
    notification = Notification.objects.create(
        recipient_phone=payload["to"],
        recipient_id=payload.get("recipient_id"),
        event=payload["event"],
        language=payload["language"],
        context=payload["context"],
    )
    event.payload = {
        **payload,
        "context": scrub_context(payload["event"], payload["context"]),
        "notification_id": str(notification.pk),
    }
    event.save(update_fields=["payload", "updated_at"])
    deliver(notification)


@register_handler(NOTIFICATION_SEND)
def send_notification(event: OutboxEvent) -> None:
    notification = (
        Notification.objects.select_for_update()
        .filter(pk=event.payload["notification_id"], status=Notification.Status.PENDING)
        .first()
    )
    if notification is not None:
        deliver(notification)


def deliver(notification: Notification) -> None:
    text = render(notification.event, notification.language, notification.context)
    notification.attempts += 1
    try:
        sent = get_sms_backend().send(notification.recipient_phone, text)
    except Exception as exc:
        notification.error = f"{type(exc).__name__}: {exc}"[:1000]
        if notification.attempts > RETRIES:
            finish(notification, Notification.Status.FAILED)
            logger.error(
                "SMS failed after retries",
                extra={"notification_id": str(notification.pk), "event": notification.event},
            )
        else:
            notification.save(update_fields=["attempts", "error", "updated_at"])
            emit(
                NOTIFICATION_SEND,
                {"notification_id": str(notification.pk)},
                available_at=timezone.now() + RETRY_INTERVAL,
            )
        return

    notification.provider_message_id = sent.message_id
    notification.sent_at = timezone.now()
    finish(notification, Notification.Status.SENT)


def finish(notification: Notification, status: str) -> None:
    """Record the outcome and remove codes and links from what's stored."""
    notification.body = render(
        notification.event, notification.language, notification.context, masked=True
    )
    notification.context = scrub_context(notification.event, notification.context)
    notification.status = status
    notification.save()
