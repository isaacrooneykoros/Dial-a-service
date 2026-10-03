"""create_business (M1 T10): a business with its address, branding, branch and owner."""

from collections.abc import Callable
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import Role, User
from apps.branches.models import Branch, BranchMember
from apps.catalog.models import Service
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business, BusinessBranding, BusinessDomain

pytestmark = pytest.mark.django_db


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

    def test_the_new_business_gets_the_template_list(
        self, django_capture_on_commit_callbacks: Callable[..., Any]
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            call_command("create_business", *self.ARGS, stdout=StringIO())
        with tenant_context(Business.objects.get(slug="safiwash").pk):
            assert Service.objects.count() == 8
            assert not Service.objects.filter(is_active=True).exists()

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
