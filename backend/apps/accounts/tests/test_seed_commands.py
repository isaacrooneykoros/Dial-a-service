"""T10: create_business and seed_dev."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.management.commands.seed_dev import DEV_PASSWORD, SEED
from apps.accounts.models import Role, User
from apps.branches.models import Branch, BranchMember
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
        }


class TestSeedDev:
    def test_creates_two_businesses_with_addresses_branding_branch_and_three_people(self) -> None:
        seed()
        for spec in SEED:
            business = Business.objects.get(slug=spec.slug)
            assert BusinessDomain.objects.get(business=business).host == f"{spec.slug}.localhost"
            assert counts(business) == {"users": 3, "branches": 1, "members": 3, "branding": 1}
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


class TestCreateBusiness:
    ARGS = (
        "--name",
        "Safi Wash",
        "--slug",
        "safiwash",
        "--branch",
        "Ngong Road",
        "--owner-phone",
        "0712345678",
        "--owner-first-name",
        "Grace",
        "--owner-last-name",
        "Wambui",
    )

    @pytest.fixture(autouse=True)
    def owner_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DIAL_OWNER_PASSWORD", "kahawa-tamu-42")
        monkeypatch.setenv("DIAL_OWNER_PIN", "2468")

    def test_creates_the_business_with_its_owner(self) -> None:
        out = StringIO()
        call_command("create_business", *self.ARGS, stdout=out)
        business = Business.objects.get(slug="safiwash")
        assert BusinessDomain.objects.get(business=business).host == "safiwash.localhost"
        with tenant_context(business.pk):
            owner = User.objects.get()
            assert owner.phone == "+254712345678"
            assert owner.role == Role.OWNER
            assert owner.check_password("kahawa-tamu-42")
            assert owner.pin_hash
            branch = Branch.objects.get()
            assert branch.name == "Ngong Road"
            assert BranchMember.objects.filter(branch=branch, user_id=owner.pk).exists()
            assert BusinessBranding.objects.get().app_name == "Safi Wash"
        assert "Created Safi Wash" in out.getvalue()
        assert "kahawa" not in out.getvalue()

    def test_refuses_an_address_name_in_use(self) -> None:
        call_command("create_business", *self.ARGS, stdout=StringIO())
        with pytest.raises(CommandError, match="already exists"):
            call_command("create_business", *self.ARGS, stdout=StringIO())

    def test_refuses_reserved_address_names(self) -> None:
        args = list(self.ARGS)
        args[3] = "admin"
        with pytest.raises(CommandError, match="slug"):
            call_command("create_business", *args, stdout=StringIO())

    def test_a_weak_password_leaves_nothing_behind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DIAL_OWNER_PASSWORD", "12345678")
        with pytest.raises(CommandError):
            call_command("create_business", *self.ARGS, stdout=StringIO())
        assert not Business.objects.filter(slug="safiwash").exists()

    def test_a_bad_phone_leaves_nothing_behind(self) -> None:
        args = list(self.ARGS)
        args[7] = "12345"
        with pytest.raises(CommandError, match="Kenyan mobile number"):
            call_command("create_business", *args, stdout=StringIO())
        assert not Business.objects.filter(slug="safiwash").exists()

    def test_a_light_brand_colour_is_refused(self) -> None:
        with pytest.raises(CommandError, match="too light"):
            call_command(
                "create_business", *self.ARGS, "--primary-color", "#F5F5A0", stdout=StringIO()
            )
