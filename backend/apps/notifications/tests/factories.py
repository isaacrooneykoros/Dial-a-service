"""Factories for notifications. Call inside tenant_context()."""

import factory

from apps.notifications.models import Notification, NotificationTemplate


class NotificationTemplateFactory(factory.django.DjangoModelFactory[NotificationTemplate]):
    class Meta:
        model = NotificationTemplate

    event = "phone_code"
    language = factory.Sequence(lambda n: f"x{n % 10}")
    body = "{code} is your {business} code."


class NotificationFactory(factory.django.DjangoModelFactory[Notification]):
    class Meta:
        model = Notification

    recipient_phone = "+254712345678"
    event = "phone_code"
    context = factory.Dict({"code": "123456", "business": "Mama Safi"})
