"""Factories for tenancy models. Global models, so no business context is needed."""

import factory

from apps.tenancy.models import Business, BusinessBranding, BusinessDomain, BusinessSetting


class BusinessFactory(factory.django.DjangoModelFactory[Business]):
    class Meta:
        model = Business

    name = factory.Sequence(lambda n: f"Laundry {n}")
    slug = factory.Sequence(lambda n: f"laundry-{n}")


class BusinessDomainFactory(factory.django.DjangoModelFactory[BusinessDomain]):
    class Meta:
        model = BusinessDomain

    business = factory.SubFactory(BusinessFactory)
    host = factory.LazyAttribute(lambda o: f"{o.business.slug}.localhost")
    is_primary = True


class BusinessBrandingFactory(factory.django.DjangoModelFactory[BusinessBranding]):
    """Tenant factory: call inside tenant_context()."""

    class Meta:
        model = BusinessBranding

    app_name = factory.Sequence(lambda n: f"Laundry {n}")


class BusinessSettingFactory(factory.django.DjangoModelFactory[BusinessSetting]):
    """Tenant factory: call inside tenant_context()."""

    class Meta:
        model = BusinessSetting

    key = factory.Sequence(lambda n: f"test.key{n}")
    value = True
