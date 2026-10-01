"""The audit log: written with the change, secrets redacted, never edited (M1 T07a)."""

from types import SimpleNamespace

import pytest
from django.db import DatabaseError, transaction
from django.test import RequestFactory

from apps.accounts.tests.factories import UserFactory
from apps.core.audit import client_ip, record
from apps.core.logging import REDACTED
from apps.core.models import AuditLog
from apps.core.request_id import request_id_var
from apps.core.tenant_context import TenantContextMissing, tenant_context
from apps.tenancy.tests.factories import BusinessFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def business_id() -> object:
    return BusinessFactory().id


def test_record_writes_a_row_for_the_current_business(business_id: object) -> None:
    request = RequestFactory().post("/x", REMOTE_ADDR="196.201.214.10")
    token = request_id_var.set("req-audit-123")
    try:
        with tenant_context(business_id):  # type: ignore[arg-type]
            user = UserFactory()
            entry = record(
                "user.update",
                obj=user,
                before={"first_name": "Wanjiru", "password": "old-secret"},
                after={"first_name": "Wanjiku", "phone": "+254712345678", "pin": "1234"},
                actor=user,
                request=request,
            )
    finally:
        request_id_var.reset(token)
    assert entry.business_id == business_id
    assert (entry.action, entry.object_type, entry.object_id) == (
        "user.update",
        "accounts.user",
        str(user.pk),
    )
    assert entry.before == {"first_name": "Wanjiru", "password": REDACTED}
    assert entry.after == {"first_name": "Wanjiku", "phone": "+254712345678", "pin": REDACTED}
    assert entry.actor_id == user.pk
    assert entry.ip == "196.201.214.10"
    assert entry.request_id == "req-audit-123"
    assert str(entry) == f"user.update accounts.user:{user.pk}"


def test_actor_comes_from_the_signed_in_request_user(business_id: object) -> None:
    with tenant_context(business_id):  # type: ignore[arg-type]
        user = UserFactory()
        request = RequestFactory().get("/")
        request.user = user
        assert record("thing.view", request=request).actor_id == user.pk
        request.user = SimpleNamespace(is_authenticated=False)  # type: ignore[assignment]
        assert record("thing.view", request=request).actor_id is None


def test_client_ip_without_a_request() -> None:
    assert client_ip(None) is None


def record_then_fail() -> None:
    with transaction.atomic():
        record("thing.delete")
        raise RuntimeError("the action failed")


def test_rows_roll_back_with_the_action(business_id: object) -> None:
    with tenant_context(business_id):  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="action failed"):
            record_then_fail()
        assert not AuditLog.objects.exists()


def test_the_database_refuses_edits_and_deletes(business_id: object) -> None:
    with tenant_context(business_id):  # type: ignore[arg-type]
        record("thing.create")
        with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
            AuditLog.objects.update(action="tampered")
        with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
            AuditLog.objects.all().delete()
        assert AuditLog.objects.get().action == "thing.create"


def test_reading_needs_a_business() -> None:
    with pytest.raises(TenantContextMissing):
        AuditLog.objects.count()
