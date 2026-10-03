"""Write operations for the tenancy app. Other apps call these, never the models directly."""

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.core import audit
from apps.core.outbox import emit
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business, BusinessBranding, BusinessDomain, BusinessSetting
from apps.tenancy.settings_registry import get_spec
from apps.tenancy.validators import normalize_host

# Handled by the apps that set up a new business (apps/catalog/handlers.py).
BUSINESS_CREATED = "business.created"


@dataclass(frozen=True)
class BrandingDetails:
    app_name: str
    primary_color: str = "#0F6B5C"
    accent_color: str = "#F2A900"
    support_phone: str = ""


def create_business(*, name: str, slug: str, host: str, branding: BrandingDetails) -> Business:
    """A new business with its main web address and branding (a platform action).

    Validates everything first (slug and host rules, the brand colour's contrast)
    and raises django.core.exceptions.ValidationError on bad input.
    """
    with transaction.atomic():
        business = Business(name=name, slug=slug)
        business.full_clean()
        business.save()
        domain = BusinessDomain(business=business, host=normalize_host(host), is_primary=True)
        domain.full_clean()
        domain.save()
        with tenant_context(business.pk):
            record = BusinessBranding(
                app_name=branding.app_name,
                primary_color=branding.primary_color,
                accent_color=branding.accent_color,
                support_phone=branding.support_phone,
            )
            record.full_clean(exclude=["business"])
            record.save()
            audit.record("business.create", obj=business, after={"slug": slug, "host": domain.host})
            # Other apps set the new business up after commit (the catalogue adds its
            # template price list). tenancy can't call them: dependencies point one way.
            emit(BUSINESS_CREATED, {"slug": slug})
    return business


def set_setting(key: str, value: Any) -> None:
    """Store a declared setting for the current business, checking its type."""
    get_spec(key).validate(value)
    BusinessSetting.objects.update_or_create(key=key, defaults={"value": value})
