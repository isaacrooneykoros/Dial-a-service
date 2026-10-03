"""Money settings (M2 T02): VAT and the discount cap, stored as decimal strings."""

from decimal import Decimal

import pytest

from apps.core.tenant_context import tenant_context
from apps.tenancy import selectors, services
from apps.tenancy.models import Business
from apps.tenancy.settings_registry import get_spec
from apps.tenancy.tests.factories import BusinessFactory


@pytest.mark.parametrize("value", ["0", "16", "16.00", "7.5", "100", "100.00", "0.01"])
@pytest.mark.parametrize("key", ["vat.rate", "discounts.max_percent"])
def test_percentages_accept_decimal_strings(key: str, value: str) -> None:
    get_spec(key).validate(value)


@pytest.mark.parametrize("value", ["-1", "100.01", "101", "16.005", "abc", "", " 16", "16,5"])
@pytest.mark.parametrize("key", ["vat.rate", "discounts.max_percent"])
def test_percentages_refuse_anything_else(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="percentage"):
        get_spec(key).validate(value)


@pytest.mark.parametrize("value", [16, 16.0, Decimal("16"), True, None])
def test_percentages_are_never_numbers(value: object) -> None:
    # JSON numbers would become floats; money never uses floats.
    with pytest.raises(TypeError):
        get_spec("vat.rate").validate(value)


@pytest.mark.parametrize("key", ["vat.registered", "vat.prices_include_vat"])
def test_switches_are_booleans(key: str) -> None:
    get_spec(key).validate(True)
    with pytest.raises(TypeError):
        get_spec(key).validate("true")


@pytest.mark.django_db
class TestStoredValues:
    def test_defaults_until_the_owner_sets_them(self) -> None:
        business = BusinessFactory()
        with tenant_context(business.id):
            assert selectors.get_setting("vat.registered") is False
            assert selectors.decimal_setting("vat.rate") == Decimal("16.00")
            assert selectors.decimal_setting("discounts.max_percent") == Decimal("0")

    def test_a_business_sets_its_own_values(
        self, business_a: Business, business_b: Business
    ) -> None:
        with tenant_context(business_a.id):
            services.set_setting("vat.registered", True)
            services.set_setting("discounts.max_percent", "15")
            assert selectors.get_setting("vat.registered") is True
            assert selectors.decimal_setting("discounts.max_percent") == Decimal("15")
        with tenant_context(business_b.id):
            assert selectors.get_setting("vat.registered") is False
            assert selectors.decimal_setting("discounts.max_percent") == Decimal("0")

    def test_bad_values_are_refused_when_saved(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            with pytest.raises(ValueError, match="from 0 to 100"):
                services.set_setting("vat.rate", "120")
            with pytest.raises(TypeError):
                services.set_setting("vat.rate", 16.0)

    def test_decimal_setting_is_exact(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            services.set_setting("vat.rate", "7.5")
            value = selectors.decimal_setting("vat.rate")
            assert value == Decimal("7.5")
            assert isinstance(value, Decimal)
