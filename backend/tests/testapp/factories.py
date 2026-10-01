"""Factories for the test app. Tenant factories must run inside tenant_context()."""

import factory

from tests.testapp.models import Widget


class WidgetFactory(factory.django.DjangoModelFactory[Widget]):
    class Meta:
        model = Widget

    name = factory.Sequence(lambda n: f"widget-{n}")
