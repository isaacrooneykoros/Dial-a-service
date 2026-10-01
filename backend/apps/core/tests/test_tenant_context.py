"""tenant_context() sets the contextvar and the transaction-local RLS setting (M1 T04a)."""

import uuid

import pytest
from django.db import connection, transaction

from apps.core.tenant_context import (
    TenantContextConflict,
    TenantContextMissing,
    get_current_business_id,
    peek_current_business_id,
    tenant_context,
)

pytestmark = pytest.mark.django_db

A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")


def db_setting() -> str | None:
    """What the RLS policies see: '' is treated as no business."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT NULLIF(current_setting('app.business_id', true), '')")
        row = cursor.fetchone()
    assert row is not None
    value: str | None = row[0]
    return value


def test_no_business_by_default() -> None:
    assert peek_current_business_id() is None
    with pytest.raises(TenantContextMissing):
        get_current_business_id()


def test_sets_contextvar_and_database_setting() -> None:
    with tenant_context(A) as business_id:
        assert business_id == A
        assert get_current_business_id() == A
        assert db_setting() == str(A)
    assert peek_current_business_id() is None


def test_setting_does_not_outlive_the_block_inside_an_outer_transaction() -> None:
    # pytest-django wraps each test in a transaction, as an outer caller would.
    assert connection.in_atomic_block
    with tenant_context(A):
        pass
    assert db_setting() is None


def test_accepts_string_ids() -> None:
    with tenant_context(str(A)) as business_id:
        assert business_id == A


def test_rejects_invalid_ids() -> None:
    with pytest.raises(ValueError, match="badly formed"), tenant_context("not-a-uuid"):
        pass


def test_reentering_the_same_business_is_allowed() -> None:
    with tenant_context(A), tenant_context(A):
        assert get_current_business_id() == A
    assert peek_current_business_id() is None


def test_switching_business_inside_a_context_is_refused() -> None:
    with tenant_context(A), pytest.raises(TenantContextConflict), tenant_context(B):
        pass


def test_an_error_inside_resets_everything() -> None:
    class BoomError(Exception):
        pass

    with pytest.raises(BoomError), tenant_context(A):
        raise BoomError
    assert peek_current_business_id() is None
    assert db_setting() is None


def test_runs_inside_a_transaction() -> None:
    with tenant_context(A):
        assert connection.in_atomic_block


@pytest.mark.django_db(transaction=True)
def test_setting_is_transaction_local_without_an_outer_transaction() -> None:
    assert not connection.in_atomic_block
    with tenant_context(A):
        assert db_setting() == str(A)
    # The transaction committed; a transaction-local setting is gone, so a
    # pooled connection reused by the next request starts with no business.
    with transaction.atomic():
        assert db_setting() is None


@pytest.mark.django_db(transaction=True)
def test_same_business_after_commit_gets_a_fresh_transaction() -> None:
    """On-commit callbacks run while the business is still current but its
    transaction has ended; re-entering must not run with no transaction."""
    seen: list[tuple[bool, str | None]] = []

    def callback() -> None:
        with tenant_context(A):
            seen.append((connection.in_atomic_block, db_setting()))

    with tenant_context(A):
        transaction.on_commit(callback)
    assert seen == [(True, str(A))]
