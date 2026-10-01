"""The transactional outbox (CLAUDE.md section 6.4; ADR-0001 section 6).

Side effects (SMS, email, webhooks) are never performed inside a request.
Code calls ``emit()`` in the same transaction as its change; after commit the
worker runs the handler registered for the event type. If the transaction
rolls back, the event never existed.

Handlers live in the app that owns the effect and register themselves:

    @register_handler("notification.send")
    def send_notification(event: OutboxEvent) -> None: ...

Delivery is at least once: a handler may run again after a crash, so handlers
must be safe to repeat (the notifications app records what it already sent).
"""

from collections.abc import Callable
from typing import Any

from django.db import transaction

from apps.core.models import OutboxEvent
from apps.core.tenant_context import get_current_business_id

Handler = Callable[[OutboxEvent], None]
HANDLERS: dict[str, Handler] = {}


def register_handler(event_type: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        if event_type in HANDLERS and HANDLERS[event_type] is not handler:
            raise ValueError(f"A handler for {event_type!r} is already registered.")
        HANDLERS[event_type] = handler
        return handler

    return decorator


def emit(event_type: str, payload: dict[str, Any] | None = None) -> OutboxEvent:
    """Record an event for the current business; dispatch it once the transaction commits."""
    business_id = get_current_business_id()
    event: OutboxEvent = OutboxEvent.objects.create(type=event_type, payload=payload or {})

    def enqueue() -> None:
        from apps.core.tasks import dispatch_outbox

        dispatch_outbox.delay(str(business_id), str(event.pk))

    transaction.on_commit(enqueue)
    return event
