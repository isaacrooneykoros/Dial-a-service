"""Factories for core models. Call inside tenant_context()."""

from datetime import timedelta

import factory
from django.utils import timezone

from apps.core.models import AuditLog, IdempotencyKey, OutboxEvent, Upload
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


class IdempotencyKeyFactory(factory.django.DjangoModelFactory[IdempotencyKey]):
    class Meta:
        model = IdempotencyKey

    scope = "ip:127.0.0.1"
    key = factory.Sequence(lambda n: f"key-{n:08d}")
    method = "POST"
    path = "/api/v1/x"
    body_hash = "0" * 64
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=24))


class UploadFactory(factory.django.DjangoModelFactory[Upload]):
    class Meta:
        model = Upload

    key = factory.Sequence(lambda n: f"test/uploads/{n:08d}.jpg")
    content_type = "image/jpeg"
    size = 4
