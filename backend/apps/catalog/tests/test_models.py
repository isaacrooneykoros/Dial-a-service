"""Catalogue rules the database enforces (M2 T01).

Isolation (RLS on every table) is covered by tests/test_tenancy_contract.py and
tests/test_rls_isolation.py, which pick these models up automatically.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.branches.tests.factories import BranchFactory
from apps.catalog.models import PriceModifier, Service
from apps.catalog.tests.factories import (
    PriceModifierFactory,
    PriceModifierServiceFactory,
    ServiceCategoryFactory,
    ServiceFactory,
    ServicePriceFactory,
)
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

JAN = datetime(2026, 1, 1, tzinfo=UTC)
FEB = datetime(2026, 2, 1, tzinfo=UTC)
MAR = datetime(2026, 3, 1, tzinfo=UTC)


def refused(create: object) -> None:
    """The database refuses the row (inside a savepoint, so the test goes on)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        create()  # type: ignore[operator]


class TestServices:
    def test_code_is_unique_per_business(self, business_a: Business, business_b: Business) -> None:
        with tenant_context(business_a.id):
            ServiceFactory(code="wash-fold")
            refused(lambda: ServiceFactory(code="wash-fold"))
        with tenant_context(business_b.id):
            ServiceFactory(code="wash-fold")  # another business may use it

    @pytest.mark.parametrize(
        ("model", "unit", "ok"),
        [
            (Service.PricingModel.PER_KG, Service.Unit.KG, True),
            (Service.PricingModel.PER_KG, Service.Unit.ITEM, False),
            (Service.PricingModel.PER_ITEM, Service.Unit.ITEM, True),
            (Service.PricingModel.PER_ITEM, Service.Unit.PAIR, True),
            (Service.PricingModel.PER_ITEM, Service.Unit.SET, True),
            (Service.PricingModel.PER_ITEM, Service.Unit.KG, False),
            (Service.PricingModel.FLAT, Service.Unit.ITEM, True),
            (Service.PricingModel.FLAT, Service.Unit.KG, False),
        ],
    )
    def test_unit_matches_the_pricing_model(
        self, business_a: Business, model: str, unit: str, ok: bool
    ) -> None:
        with tenant_context(business_a.id):
            if ok:
                ServiceFactory(pricing_model=model, unit=unit)
            else:
                refused(lambda: ServiceFactory(pricing_model=model, unit=unit))

    def test_new_services_start_switched_off(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            category = ServiceCategoryFactory()
            service = Service.objects.create(
                category=category,
                code="duvet",
                name_en="Duvets",
                pricing_model=Service.PricingModel.PER_ITEM,
                unit=Service.Unit.ITEM,
            )
            assert service.is_active is False

    def test_a_category_with_services_cannot_be_deleted(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            refused(lambda: service.category.delete())


class TestPriceVersions:
    def test_versions_of_one_service_never_overlap(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            ServicePriceFactory(service=service, effective_from=JAN, effective_to=MAR)
            refused(lambda: ServicePriceFactory(service=service, effective_from=FEB))
            refused(
                lambda: ServicePriceFactory(service=service, effective_from=FEB, effective_to=MAR)
            )

    def test_an_open_version_blocks_any_later_one(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            ServicePriceFactory(service=service, effective_from=JAN)  # no end: until replaced
            refused(lambda: ServicePriceFactory(service=service, effective_from=MAR))

    def test_back_to_back_versions_are_fine(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            ServicePriceFactory(service=service, effective_from=JAN, effective_to=FEB)
            ServicePriceFactory(service=service, effective_from=FEB)  # starts as the other ends

    def test_a_branch_override_has_its_own_versions(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            branch, other = BranchFactory(), BranchFactory()
            ServicePriceFactory(service=service, effective_from=JAN)
            ServicePriceFactory(service=service, branch=branch, effective_from=JAN)
            ServicePriceFactory(service=service, branch=other, effective_from=JAN)
            refused(lambda: ServicePriceFactory(service=service, branch=branch, effective_from=FEB))

    def test_different_services_are_independent(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            ServicePriceFactory(effective_from=JAN)
            ServicePriceFactory(effective_from=JAN)

    @pytest.mark.parametrize(
        "fields",
        [
            {"unit_price": Decimal("0.00")},
            {"unit_price": Decimal("-1.00")},
            {"minimum_charge": Decimal("-0.01")},
            {"effective_from": FEB, "effective_to": FEB},
            {"effective_from": FEB, "effective_to": JAN},
        ],
    )
    def test_bad_values_are_refused(self, business_a: Business, fields: dict[str, object]) -> None:
        with tenant_context(business_a.id):
            service = ServiceFactory()
            refused(lambda: ServicePriceFactory(service=service, **fields))

    def test_amounts_are_exact_decimals(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            price = ServicePriceFactory(unit_price=Decimal("120.55"))
            price.refresh_from_db()
            assert price.unit_price == Decimal("120.55")
            assert isinstance(price.unit_price, Decimal)
            assert price.currency == "KES"


class TestModifiers:
    @pytest.mark.parametrize(
        ("percent", "amount", "ok"),
        [
            (Decimal("50.00"), None, True),
            (None, Decimal("200.00"), True),
            (Decimal("50.00"), Decimal("200.00"), False),  # not both
            (None, None, False),  # one of them
            (Decimal("0.00"), None, False),
            (None, Decimal("0.00"), False),
            (Decimal("-10.00"), None, False),
        ],
    )
    def test_exactly_one_positive_percent_or_amount(
        self, business_a: Business, percent: Decimal | None, amount: Decimal | None, ok: bool
    ) -> None:
        with tenant_context(business_a.id):
            if ok:
                PriceModifierFactory(percent=percent, amount=amount)
            else:
                refused(lambda: PriceModifierFactory(percent=percent, amount=amount))

    def test_new_modifiers_apply_to_all_services(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            modifier = PriceModifier.objects.create(
                name_en="Express", kind=PriceModifier.Kind.EXPRESS, percent=Decimal("50")
            )
            assert modifier.applies_to_all is True

    def test_a_service_is_linked_to_a_modifier_once(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            link = PriceModifierServiceFactory()
            refused(
                lambda: PriceModifierServiceFactory(modifier=link.modifier, service=link.service)
            )

    def test_names_are_unique_per_business(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            PriceModifierFactory(name_en="Express")
            refused(lambda: PriceModifierFactory(name_en="Express"))
