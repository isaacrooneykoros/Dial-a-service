"""Factories for core models. Call inside tenant_context()."""

import factory

from apps.core.models import AuditLog, OutboxEvent
from apps.core.tenant_context import peek_current_business_id


class AuditLogFactory(factory.django.DjangoModelFactory[AuditLog]):
    class Meta:
        model = AuditLog

    business_id = factory.LazyFunction(peek_current_business_id)
    action = "test.action"


class OutboxEventFactory(factory.django.DjangoModelFactory[OutboxEvent]):
    class Meta:
        model = OutboxEvent

    type = "test.event"
    payload = factory.Dict({})
