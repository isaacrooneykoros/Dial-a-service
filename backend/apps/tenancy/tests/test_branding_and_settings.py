"""BusinessBranding colour rules and the typed BusinessSetting registry (M1 T04b)."""

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.tenant_context import tenant_context
from apps.tenancy import selectors, services, settings_registry
from apps.tenancy.colors import contrast_ratio, validate_hex_color, validate_primary_color
from apps.tenancy.models import Business, BusinessBranding, BusinessSetting
from apps.tenancy.settings_registry import SettingSpec
from apps.tenancy.tests.factories import BusinessFactory


class TestColours:
    @pytest.mark.parametrize(
        ("first", "second", "ratio"),
        [("#FFFFFF", "#000000", 21.0), ("#FFFFFF", "#FFFFFF", 1.0), ("#0F6B5C", "#FFFFFF", 6.41)],
    )
    def test_contrast_ratio(self, first: str, second: str, ratio: float) -> None:
        assert contrast_ratio(first, second) == pytest.approx(ratio, abs=0.01)

    @pytest.mark.parametrize("color", ["#0F6B5C", "#2458B3", "#C23B30", "#1b1f1d"])
    def test_dark_primaries_pass_aa_against_white(self, color: str) -> None:
        validate_primary_color(color)

    @pytest.mark.parametrize("color", ["#F2A900", "#FFFFFF", "#DCE1DE", "#7FB3A8"])
    def test_light_primaries_are_refused(self, color: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_primary_color(color)
        assert excinfo.value.code == "low_contrast"

    @pytest.mark.parametrize("color", ["0F6B5C", "#0F6B5", "#0F6B5CZ", "#GGGGGG", "green", ""])
    def test_badly_formed_colours(self, color: str) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_hex_color(color)
        assert excinfo.value.code == "invalid_color"


@pytest.mark.django_db
class TestBranding:
    def test_defaults_are_the_proposed_tokens(self) -> None:
        business = BusinessFactory()
        with tenant_context(business.id):
            branding = BusinessBranding.objects.create(app_name="Mama Safi")
        assert (branding.primary_color, branding.accent_color) == ("#0F6B5C", "#F2A900")
        assert str(branding) == "Mama Safi"

    def test_full_clean_refuses_a_light_primary(self) -> None:
        business = BusinessFactory()
        with tenant_context(business.id):
            branding = BusinessBranding(app_name="X", primary_color="#F2A900")
            branding.business_id = business.id
            with pytest.raises(ValidationError) as excinfo:
                branding.full_clean()
        assert "primary_color" in excinfo.value.message_dict

    def test_one_branding_per_business(self) -> None:
        business = BusinessFactory()
        with tenant_context(business.id):
            BusinessBranding.objects.create(app_name="A")
            with pytest.raises(IntegrityError):
                BusinessBranding.objects.create(app_name="B")


@pytest.fixture
def registered() -> Iterator[None]:
    saved = dict(settings_registry.SETTINGS)
    settings_registry.register(SettingSpec("test.flag", bool, False, "A test flag"))
    settings_registry.register(SettingSpec("test.count", int, 3, "A test count"))
    yield
    settings_registry.SETTINGS.clear()
    settings_registry.SETTINGS.update(saved)


@pytest.fixture
def business() -> Business:
    return BusinessFactory()


class TestRegistry:
    def test_m1_declares_no_business_settings(self) -> None:
        assert settings_registry.SETTINGS == {}

    def test_unknown_key(self) -> None:
        with pytest.raises(KeyError, match="Unknown business setting"):
            settings_registry.get_spec("nope")

    def test_duplicate_registration(self, registered: None) -> None:
        with pytest.raises(ValueError, match="already registered"):
            settings_registry.register(SettingSpec("test.flag", bool, True, "again"))

    def test_default_must_match_type(self) -> None:
        with pytest.raises(TypeError):
            settings_registry.register(SettingSpec("test.bad", int, "3", "wrong default"))

    def test_bool_is_not_an_int(self, registered: None) -> None:
        with pytest.raises(TypeError, match="not a bool"):
            settings_registry.get_spec("test.count").validate(True)


@pytest.mark.django_db
class TestSettingsServices:
    def test_default_when_unset(self, registered: None, business: Business) -> None:
        with tenant_context(business.id):
            assert selectors.get_setting("test.count") == 3

    def test_set_and_get(self, registered: None, business: Business) -> None:
        with tenant_context(business.id):
            services.set_setting("test.count", 7)
            services.set_setting("test.count", 9)
            assert selectors.get_setting("test.count") == 9
            assert str(BusinessSetting.objects.get()) == "test.count"

    def test_values_are_per_business(self, registered: None, business: Business) -> None:
        other = BusinessFactory()
        with tenant_context(business.id):
            services.set_setting("test.flag", True)
        with tenant_context(other.id):
            assert selectors.get_setting("test.flag") is False

    def test_wrong_type_is_refused(self, registered: None, business: Business) -> None:
        with tenant_context(business.id), pytest.raises(TypeError):
            services.set_setting("test.flag", "yes")

    def test_unknown_key_is_refused(self, registered: None, business: Business) -> None:
        with tenant_context(business.id), pytest.raises(KeyError):
            services.set_setting("test.typo", 1)
