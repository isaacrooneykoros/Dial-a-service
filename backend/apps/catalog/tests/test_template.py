"""The template price list for new businesses (M2 T05, owner decision D-57)."""

from collections.abc import Callable
from typing import Any

import pytest

from apps.catalog import services
from apps.catalog.models import Service, ServiceCategory, ServicePrice
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business
from apps.tenancy.services import BrandingDetails, create_business

pytestmark = pytest.mark.django_db

EXPECTED = {
    # code: (name, category, pricing model, unit) -- D-57
    "wash-fold": ("Wash and fold", "Wash", "per_kg", "kg"),
    "wash-iron": ("Wash and iron", "Wash", "per_kg", "kg"),
    "ironing": ("Ironing only", "Special items", "per_item", "item"),
    "duvet": ("Duvets", "Special items", "per_item", "item"),
    "blanket": ("Blankets", "Special items", "per_item", "item"),
    "suit": ("Suits", "Special items", "per_item", "item"),
    "curtains": ("Curtains", "Special items", "per_item", "item"),
    "shoes": ("Shoes", "Special items", "per_item", "pair"),
}


def catalogue() -> dict[str, tuple[str, str, str, str]]:
    return {
        s.code: (s.name_en, s.category.name_en, s.pricing_model, s.unit)
        for s in Service.objects.select_related("category")
    }


def test_the_template_list(business_a: Business) -> None:
    with tenant_context(business_a.id):
        services.install_template()
        assert catalogue() == EXPECTED
        assert list(ServiceCategory.objects.values_list("name_en", flat=True)) == [
            "Wash",
            "Special items",
        ]
        # Unpriced and switched off until the owner sets prices.
        assert not Service.objects.filter(is_active=True).exists()
        assert not ServicePrice.objects.exists()


def test_running_it_again_adds_only_what_is_missing(business_a: Business) -> None:
    with tenant_context(business_a.id):
        services.install_template()
        duvet = Service.objects.get(code="duvet")
        services.update_service(duvet, name_en="Duvets (any size)")  # the owner's change
        Service.objects.filter(code="shoes").update(code="sneakers")  # renamed away
        created = services.install_template()
        assert [s.code for s in created] == ["shoes"]
        assert Service.objects.get(code="duvet").name_en == "Duvets (any size)"
        assert ServiceCategory.objects.count() == 2


def test_a_new_business_gets_it_after_commit(
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        business = create_business(
            name="Safi Wash",
            slug="safiwash",
            host="safiwash.localhost",
            branding=BrandingDetails(app_name="Safi Wash"),
        )
    with tenant_context(business.id):
        assert catalogue() == EXPECTED


def test_each_business_has_its_own_list(business_a: Business, business_b: Business) -> None:
    with tenant_context(business_a.id):
        services.install_template()
        Service.objects.filter(code="suit").update(name_en="Suits and coats")
    with tenant_context(business_b.id):
        services.install_template()
        assert Service.objects.get(code="suit").name_en == "Suits"
        assert Service.objects.count() == 8
