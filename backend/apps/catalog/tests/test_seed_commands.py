"""seed_dev (M1 T10; moved to the catalogue in M2 T05 with sample prices)."""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.models import User
from apps.branches.models import Branch, BranchMember
from apps.catalog import selectors as catalog_selectors
from apps.catalog.management.commands.seed_dev import DEV_PASSWORD, SEED
from apps.catalog.models import PriceModifier, Service, ServicePrice
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business, BusinessBranding, BusinessDomain

pytestmark = pytest.mark.django_db


def seed() -> str:
    out = StringIO()
    call_command("seed_dev", stdout=out)
    return out.getvalue()


def counts(business: Business) -> dict[str, int]:
    with tenant_context(business.pk):
        return {
            "users": User.objects.count(),
            "branches": Branch.objects.count(),
            "members": BranchMember.objects.count(),
            "branding": BusinessBranding.objects.count(),
            "services": Service.objects.count(),
            "prices": ServicePrice.objects.count(),
            "modifiers": PriceModifier.objects.count(),
        }


class TestSeedDev:
    def test_creates_two_businesses_with_addresses_branding_branch_and_three_people(self) -> None:
        seed()
        for spec in SEED:
            business = Business.objects.get(slug=spec.slug)
            assert BusinessDomain.objects.get(business=business).host == f"{spec.slug}.localhost"
            assert counts(business) == {
                "users": 3,
                "branches": 1,
                "members": 3,
                "branding": 1,
                "services": 8,  # the template list (D-57)
                "prices": len(spec.prices),
                "modifiers": len(spec.modifiers),
            }
            with tenant_context(business.pk):
                branding = BusinessBranding.objects.get()
                assert branding.primary_color == spec.primary_color
                for person in spec.people:
                    user = User.objects.get(phone=person.phone)
                    assert user.role == person.role
                    assert user.is_phone_verified
                    assert user.check_password(DEV_PASSWORD)
                    assert user.pin_hash
                    assert user.pin_hash != person.pin  # stored hashed

    def test_sample_prices_switch_their_services_on(self) -> None:
        seed()
        with tenant_context(Business.objects.get(slug="mamasafi").pk):
            listed = {s.code: p for s, p in catalog_selectors.active_price_list()}
            assert set(listed) == {"wash-fold", "wash-iron", "duvet", "shoes"}
            assert (listed["wash-fold"].unit_price, listed["wash-fold"].minimum_charge) == (
                Decimal("120.00"),
                Decimal("500.00"),
            )
            assert PriceModifier.objects.get(name_en="Express").percent == Decimal("50.00")
        with tenant_context(Business.objects.get(slug="cleanpro").pk):
            listed = {s.code: p for s, p in catalog_selectors.active_price_list()}
            assert set(listed) == {"wash-fold", "suit", "curtains"}
            assert listed["wash-fold"].unit_price == Decimal("140.00")  # differs on purpose
            assert PriceModifier.objects.get(name_en="Express").amount == Decimal("300.00")

    def test_brand_colours_differ(self) -> None:
        assert len({spec.primary_color for spec in SEED}) == len(SEED)

    def test_running_twice_creates_nothing_new(self) -> None:
        seed()
        before = {spec.slug: counts(Business.objects.get(slug=spec.slug)) for spec in SEED}
        seed()
        after = {spec.slug: counts(Business.objects.get(slug=spec.slug)) for spec in SEED}
        assert after == before
        assert Business.objects.filter(slug__in=[s.slug for s in SEED]).count() == 2

    def test_each_business_sees_only_its_own_people_even_in_raw_sql(self) -> None:
        seed()
        mamasafi = Business.objects.get(slug="mamasafi")
        with tenant_context(mamasafi.pk), connection.cursor() as cursor:
            cursor.execute("SELECT phone FROM accounts_user")
            phones = {row[0] for row in cursor.fetchall()}
        assert phones == {p.phone for p in SEED[0].people}

    def test_prints_the_logins(self, settings: object) -> None:
        # As in local development (config/settings/local.py).
        settings.APP_LINK_SCHEME = "http"  # type: ignore[attr-defined]
        settings.APP_LINK_PORT = ":5173"  # type: ignore[attr-defined]
        output = seed()
        assert "http://mamasafi.localhost:5173/staff/login" in output
        assert "http://cleanpro.localhost:5173/console/login" in output
        assert "0700 000 101" in output
        assert DEV_PASSWORD in output

    def test_never_runs_in_production(self, settings: object) -> None:
        settings.SETTINGS_MODULE = "config.settings.production"  # type: ignore[attr-defined]
        with pytest.raises(CommandError, match="never runs in production"):
            seed()
        assert not Business.objects.filter(slug="mamasafi").exists()
