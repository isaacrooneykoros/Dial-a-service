"""The transactional outbox and its dispatcher (M1 T07a, ADR-0001 section 6)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.db import transaction
from django.utils import timezone

from apps.core import outbox, tasks
from apps.core.models import OutboxEvent
from apps.core.outbox import emit, register_handler
from apps.core.task_helpers import tenant_task
from apps.core.tenant_context import get_current_business_id, tenant_context
from apps.tenancy.models import Business
from apps.tenancy.tasks import sweep_outbox
from apps.tenancy.tests.factories import BusinessFactory
from tests.testapp.models import Widget

pytestmark = pytest.mark.django_db

Calls = list[tuple[str, object]]


@pytest.fixture
def calls() -> Iterator[Calls]:
    """Registers handlers for test.* event types and records each call."""
    seen: Calls = []

    def ok(event: OutboxEvent) -> None:
        seen.append((event.type, get_current_business_id()))

    def boom(event: OutboxEvent) -> None:
        Widget.objects.create(name="half-written")
        raise RuntimeError("gateway down")

    saved = dict(outbox.HANDLERS)
    register_handler("test.ok")(ok)
    register_handler("test.boom")(boom)
    yield seen
    outbox.HANDLERS.clear()
    outbox.HANDLERS.update(saved)


@pytest.fixture
def business() -> Business:
    return BusinessFactory()


def test_event_is_dispatched_only_after_commit(
    business: Business, calls: Calls, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    with tenant_context(business.id):
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            event = emit("test.ok", {"n": 1})
            assert calls == []  # nothing happens inside the transaction
        assert len(callbacks) == 1
        event.refresh_from_db()
    assert calls == [("test.ok", business.id)]
    assert event.processed_at is not None
    assert event.payload == {"n": 1}


def emit_then_fail() -> None:
    with transaction.atomic():
        emit("test.ok")
        raise RuntimeError("the change failed")


def test_rolled_back_events_never_dispatch(
    business: Business, calls: Calls, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    with tenant_context(business.id):
        with (
            django_capture_on_commit_callbacks(execute=True) as callbacks,
            pytest.raises(RuntimeError, match="change failed"),
        ):
            emit_then_fail()
        assert callbacks == []
        assert not OutboxEvent.objects.exists()
    assert calls == []


def test_a_failing_handler_is_retried_later_and_its_writes_undone(
    business: Business, calls: Calls
) -> None:
    with tenant_context(business.id):
        event = OutboxEvent.objects.create(type="test.boom")
        before = timezone.now()
        tasks.handle(event)
        event.refresh_from_db()
        assert event.attempts == 1
        assert event.processed_at is None
        assert event.failed_at is None
        assert "gateway down" in event.last_error
        assert event.available_at >= before + timedelta(seconds=30)
        assert not Widget.objects.exists()


def test_unknown_event_types_are_recorded_as_errors(business: Business) -> None:
    with tenant_context(business.id):
        event = OutboxEvent.objects.create(type="nobody.handles.this")
        tasks.handle(event)
        event.refresh_from_db()
    assert "No handler registered" in event.last_error
    assert event.attempts == 1


def test_gives_up_after_max_attempts(business: Business, calls: Calls) -> None:
    with tenant_context(business.id):
        event = OutboxEvent.objects.create(type="test.boom", attempts=tasks.MAX_ATTEMPTS - 1)
        tasks.handle(event)
        event.refresh_from_db()
    assert event.failed_at is not None
    assert event.attempts == tasks.MAX_ATTEMPTS


@pytest.mark.parametrize(
    ("attempts", "seconds"), [(1, 30), (2, 60), (3, 120), (7, 1920), (8, 3600), (9, 3600)]
)
def test_retry_backoff(attempts: int, seconds: int) -> None:
    assert tasks.retry_delay(attempts) == timedelta(seconds=seconds)


def test_dispatch_skips_events_already_processed(business: Business, calls: Calls) -> None:
    with tenant_context(business.id):
        event = OutboxEvent.objects.create(type="test.ok", processed_at=timezone.now())
    tasks.dispatch_outbox(str(business.id), str(event.pk))
    assert calls == []


def test_dispatch_runs_in_the_events_business(business: Business, calls: Calls) -> None:
    with tenant_context(business.id):
        event = OutboxEvent.objects.create(type="test.ok")
    tasks.dispatch_outbox(str(business.id), str(event.pk))
    assert calls == [("test.ok", business.id)]


def test_sweep_handles_due_events_business_by_business(calls: Calls) -> None:
    a, b = BusinessFactory(), BusinessFactory()
    for business in (a, b):
        with tenant_context(business.id):
            OutboxEvent.objects.create(type="test.ok")
            OutboxEvent.objects.create(
                type="test.ok", available_at=timezone.now() + timedelta(minutes=5)
            )
    assert sweep_outbox() == {"handled": 2}
    assert sorted(str(business_id) for _, business_id in calls) == sorted([str(a.id), str(b.id)])


def test_handlers_register_once_per_type(calls: Calls) -> None:
    handler = outbox.HANDLERS["test.ok"]
    register_handler("test.ok")(handler)  # the same function again is fine
    with pytest.raises(ValueError, match="already registered"):
        register_handler("test.ok")(lambda event: None)


def test_tenant_task_runs_inside_the_business(business: Business) -> None:
    @tenant_task
    def probe(business_id: str) -> str:
        return str(get_current_business_id())

    assert probe.name.endswith(".probe")
    assert probe(str(business.id)) == str(business.id)


@pytest.mark.django_db(transaction=True)
def test_eager_dispatch_after_a_real_commit(calls: Calls) -> None:
    """Without Redis, tasks run eagerly right after commit, still inside the request's
    business context. They must get a fresh transaction with the RLS setting."""
    business = BusinessFactory()
    with tenant_context(business.id):
        event = emit("test.ok")
    assert calls == [("test.ok", business.id)]
    with tenant_context(business.id):
        event.refresh_from_db()
    assert event.processed_at is not None
