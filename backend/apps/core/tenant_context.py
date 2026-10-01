"""Which business the current code is working for (ADR-0001 section 2).

The business ID lives in a contextvar for application code (layer 1) and in
the Postgres setting ``app.business_id`` for row-level security (layer 2).
``tenant_context()`` sets both, inside one transaction, and the setting is
transaction-local (``set_config(..., true)``), so it can never leak to the
next user of a pooled connection. Session-level SET is never used.

Background tasks and scripts use it directly:

    with tenant_context(business_id):
        ...  # queries see only this business

Web requests get it from TenantTransactionMiddleware.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from django.db import connections, transaction

SETTING = "app.business_id"

current_business_id: ContextVar[UUID | None] = ContextVar("current_business_id", default=None)


class TenantContextMissing(RuntimeError):  # noqa: N818 - name fixed by CLAUDE.md section 6.1
    """Tenant data was touched with no business in context."""


class TenantContextConflict(RuntimeError):  # noqa: N818 - reads as a state, like the above
    """Code tried to enter a second, different business while one was active."""


class TenantMismatch(ValueError):  # noqa: N818
    """A tenant row was being saved for a business other than the current one."""


def get_current_business_id() -> UUID:
    business_id = current_business_id.get()
    if business_id is None:
        raise TenantContextMissing(
            "No business in context. Business data must be accessed inside a request "
            "for a business host or inside tenant_context(business_id)."
        )
    return business_id


def peek_current_business_id() -> UUID | None:
    """The current business ID, or None. For code that works with or without one."""
    return current_business_id.get()


def _set_database_setting(value: str, using: str) -> None:
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [SETTING, value])


@contextmanager
def tenant_context(business_id: UUID | str, *, using: str = "default") -> Iterator[UUID]:
    """Run the block for one business: contextvar, transaction and RLS setting.

    Re-entering the same business is a no-op; entering a different one raises
    TenantContextConflict.
    """
    business_uuid = business_id if isinstance(business_id, UUID) else UUID(str(business_id))

    active = current_business_id.get()
    if active is not None:
        if active != business_uuid:
            raise TenantContextConflict(
                f"Business {active} is active; refusing to switch to {business_uuid}."
            )
        yield business_uuid
        return

    connection = connections[using]
    nested = connection.in_atomic_block
    token = current_business_id.set(business_uuid)
    try:
        with transaction.atomic(using=using):
            _set_database_setting(str(business_uuid), using)
            yield business_uuid
        # Inside an outer transaction the local setting would outlive this block
        # (a released savepoint keeps it), so clear it. An empty value means
        # "no business": the RLS policies treat '' as NULL and match no rows.
        if nested and not connection.needs_rollback:
            _set_database_setting("", using)
    finally:
        current_business_id.reset(token)
