"""Platform-wide periodic jobs that visit every business in turn."""

from typing import Any

from celery import shared_task

from apps.core.tasks import handle_due_events
from apps.core.tenant_context import tenant_context
from apps.tenancy.selectors import all_business_ids

SWEEP_BATCH = 100


@shared_task(name="apps.tenancy.tasks.sweep_outbox")  # platform-scope: visits every business
def sweep_outbox() -> dict[str, Any]:
    """Every minute: outbox events never queued (worker down, crash) or due a retry.

    Each business is handled inside its own tenant_context, so the worker stays on
    dial_app and row-level security still applies.
    """
    handled = 0
    for business_id in all_business_ids():
        with tenant_context(business_id):
            handled += handle_due_events(SWEEP_BATCH)
    return {"handled": handled}
