"""Outbox handlers for the catalogue (registered in CatalogConfig.ready)."""

from apps.catalog.services import install_template
from apps.core.models import OutboxEvent
from apps.core.outbox import register_handler
from apps.tenancy.services import BUSINESS_CREATED


@register_handler(BUSINESS_CREATED)
def give_new_business_the_template(event: OutboxEvent) -> None:
    """A new business starts with the template price list (D-57). Runs inside the
    business's context; safe to repeat (at-least-once delivery)."""
    install_template()
