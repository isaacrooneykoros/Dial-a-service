"""Factories for the catalogue. Tenant factories: call inside tenant_context()."""

from datetime import UTC, datetime
from decimal import Decimal

import factory

from apps.catalog.models import (
    PriceModifier,
    PriceModifierService,
    Service,
    ServiceCategory,
    ServicePrice,
)


class ServiceCategoryFactory(factory.django.DjangoModelFactory[ServiceCategory]):
    class Meta:
        model = ServiceCategory

    name_en = factory.Sequence(lambda n: f"Category {n}")


class ServiceFactory(factory.django.DjangoModelFactory[Service]):
    class Meta:
        model = Service

    category = factory.SubFactory(ServiceCategoryFactory)
    code = factory.Sequence(lambda n: f"service-{n}")
    name_en = factory.Sequence(lambda n: f"Service {n}")
    pricing_model = Service.PricingModel.PER_KG
    unit = Service.Unit.KG
    is_active = True


class ServicePriceFactory(factory.django.DjangoModelFactory[ServicePrice]):
    class Meta:
        model = ServicePrice

    service = factory.SubFactory(ServiceFactory)
    unit_price = Decimal("120.00")
    minimum_charge = Decimal("0.00")
    effective_from = factory.LazyFunction(lambda: datetime(2026, 1, 1, tzinfo=UTC))


class PriceModifierFactory(factory.django.DjangoModelFactory[PriceModifier]):
    class Meta:
        model = PriceModifier

    name_en = factory.Sequence(lambda n: f"Modifier {n}")
    kind = PriceModifier.Kind.EXPRESS
    percent = Decimal("50.00")


class PriceModifierServiceFactory(factory.django.DjangoModelFactory[PriceModifierService]):
    class Meta:
        model = PriceModifierService

    modifier = factory.SubFactory(PriceModifierFactory, applies_to_all=False)
    service = factory.SubFactory(ServiceFactory)
