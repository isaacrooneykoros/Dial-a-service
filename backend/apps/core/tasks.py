"""Outbox dispatch (ADR-0001 section 6).

dispatch_outbox runs one event's handler, queued after the emitting transaction
commits. The every-minute sweep that picks up missed and retried events walks
every business, so it lives in apps.tenancy.tasks (core never imports tenancy).
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.models import OutboxEvent
from apps.core.outbox import HANDLERS
from apps.core.task_helpers import tenant_task

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 10
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 3600


def retry_delay(attempts: int) -> timedelta:
    """30 s, 60 s, 120 s and so on, capped at an hour."""
    seconds = min(BACKOFF_BASE_SECONDS * 2 ** (attempts - 1), BACKOFF_MAX_SECONDS)
    return timedelta(seconds=seconds)


@tenant_task
def dispatch_outbox(business_id: str, event_id: str) -> None:
    event = (
        OutboxEvent.objects.select_for_update(skip_locked=True)
        .filter(pk=event_id, processed_at__isnull=True, failed_at__isnull=True)
        .first()
    )
    if event is None:
        return  # already done, given up on, or being handled by another worker
    handle(event)


def handle(event: OutboxEvent) -> None:
    now = timezone.now()
    handler = HANDLERS.get(event.type)
    try:
        if handler is None:
            raise LookupError(f"No handler registered for outbox event type {event.type!r}")
        # A savepoint: a handler that fails halfway leaves none of its writes behind.
        with transaction.atomic():
            handler(event)
    except Exception as exc:
        event.attempts += 1
        event.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        if event.attempts >= MAX_ATTEMPTS:
            event.failed_at = now
            logger.exception("Outbox event gave up", extra={"event_id": str(event.pk)})
        else:
            event.available_at = now + retry_delay(event.attempts)
            logger.warning(
                "Outbox event failed; will retry",
                extra={"event_id": str(event.pk), "attempts": event.attempts},
            )
        event.save(update_fields=["attempts", "last_error", "failed_at", "available_at"])
        return
    event.processed_at = now
    event.save(update_fields=["processed_at"])


def handle_due_events(limit: int) -> int:
    """Handle up to ``limit`` due events for the current business; returns how many."""
    due = (
        OutboxEvent.objects.select_for_update(skip_locked=True)
        .filter(processed_at__isnull=True, failed_at__isnull=True, available_at__lte=timezone.now())
        .order_by("available_at")[:limit]
    )
    handled = 0
    for event in due:
        handle(event)
        handled += 1
    return handled


def purge_expired_idempotency_keys() -> int:
    """Delete the current business's idempotency keys older than 24 hours."""
    from apps.core.models import IdempotencyKey

    deleted, _ = IdempotencyKey.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
