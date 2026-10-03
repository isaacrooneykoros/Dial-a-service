"""Console catalogue API (M2 T06): /api/v1/console/catalog/...

Every endpoint: happy path, validation, permission per role (D-60), cross-business
404, and an idempotent replay for POSTs (CLAUDE.md section 8).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import time_machine

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.branches.tests.factories import BranchFactory
from apps.catalog import services
from apps.catalog.models import PriceModifier, Service, ServiceCategory, ServicePrice
from apps.catalog.tests.factories import (
    PriceModifierFactory,
    ServiceCategoryFactory,
    ServiceFactory,
)
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

BASE = "/api/v1/console/catalog"
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen() -> Iterator[None]:
    with time_machine.travel(NOW, tick=False):
        yield


def person(business: Business, role: str) -> User:
    with tenant_context(business.id):
        user: User = UserFactory(role=role)
    return user


def as_role(business: Business, role: str = Role.OWNER) -> Any:
    return client_for(business, sign_in(person(business, role)).access)


def make_service(business: Business, **fields: Any) -> Service:
    with tenant_context(business.id):
        service: Service = ServiceFactory(is_active=False, **fields)
    return service


def fields_of(response: Any) -> dict[str, list[str]]:
    body: dict[str, list[str]] = response.json()["fields"]
    return body


class TestPermissions:
    @pytest.mark.parametrize(
        "path",
        ["/categories", "/services", "/modifiers"],
    )
    @pytest.mark.parametrize(
        ("role", "status"),
        [
            (Role.OWNER, 200),
            (Role.MANAGER, 200),
            (Role.ACCOUNTANT, 403),  # D-60: accountants can't touch the catalogue
            (Role.STAFF, 403),
        ],
    )
    def test_owners_and_managers_only(
        self, business_a: Business, path: str, role: str, status: int
    ) -> None:
        assert as_role(business_a, role).get(BASE + path).status_code == status

    @pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.STAFF])
    def test_others_cannot_change_anything(self, business_a: Business, role: str) -> None:
        response = as_role(business_a, role).post(
            f"{BASE}/categories", {"name_en": "Wash"}, format="json"
        )
        assert response.status_code == 403
        with tenant_context(business_a.id):
            assert not ServiceCategory.objects.exists()

    def test_signed_out(self, business_a: Business) -> None:
        assert client_for(business_a).get(f"{BASE}/services").status_code == 401


class TestCategories:
    def test_create_and_list(self, business_a: Business) -> None:
        client = as_role(business_a)
        response = client.post(
            f"{BASE}/categories", {"name_en": "Wash", "name_sw": "Kufua"}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["name_sw"] == "Kufua"
        listed = client.get(f"{BASE}/categories").json()
        assert [c["name_en"] for c in listed] == ["Wash"]

    def test_duplicate_names_are_refused_on_the_field(self, business_a: Business) -> None:
        client = as_role(business_a)
        client.post(f"{BASE}/categories", {"name_en": "Wash"}, format="json")
        response = client.post(f"{BASE}/categories", {"name_en": "Wash"}, format="json")
        assert response.status_code == 400
        assert response.json()["code"] == "duplicate_name"
        assert fields_of(response) == {"name_en": ["That name is already used. Choose another."]}

    def test_missing_name(self, business_a: Business) -> None:
        response = as_role(business_a).post(f"{BASE}/categories", {}, format="json")
        assert response.status_code == 400
        assert "name_en" in fields_of(response)

    def test_update(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            category = ServiceCategoryFactory(name_en="Wash")
        response = as_role(business_a, Role.MANAGER).post(
            f"{BASE}/categories/{category.pk}/update",
            {"name_en": "Washing", "is_active": False},
            format="json",
        )
        assert response.status_code == 200
        assert (response.json()["name_en"], response.json()["is_active"]) == ("Washing", False)

    def test_an_idempotent_replay_creates_one(self, business_a: Business) -> None:
        client = as_role(business_a)
        first = client.post(
            f"{BASE}/categories", {"name_en": "Wash"}, format="json", idempotency_key="key-wash-1"
        )
        again = client.post(
            f"{BASE}/categories", {"name_en": "Wash"}, format="json", idempotency_key="key-wash-1"
        )
        assert (first.status_code, again.status_code) == (201, 201)
        assert again.json() == first.json()
        assert again.headers.get("Idempotent-Replayed") == "true"
        with tenant_context(business_a.id):
            assert ServiceCategory.objects.count() == 1

    def test_cross_business(self, business_a: Business, business_b: Business) -> None:
        assert_cross_business_404(
            owner=business_b,
            owner_client=as_role(business_b),
            intruder=as_role(business_a),
            make_object=ServiceCategoryFactory,
            url_for=lambda c: f"{BASE}/categories/{c.pk}/update",
            method="post",
            data={"name_en": "Renamed"},
        )


class TestServices:
    def create(self, client: Any, category: ServiceCategory, **overrides: Any) -> Any:
        body = {
            "category_id": str(category.pk),
            "code": "wash-fold",
            "name_en": "Wash and fold",
            "pricing_model": "per_kg",
            "unit": "kg",
            **overrides,
        }
        return client.post(f"{BASE}/services", body, format="json")

    def test_create_starts_off_with_no_price(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            category = ServiceCategoryFactory()
        response = self.create(as_role(business_a), category)
        assert response.status_code == 201
        body = response.json()
        assert (body["is_active"], body["current_price"], body["unit"]) == (False, None, "kg")

    @pytest.mark.parametrize(
        ("overrides", "code", "field"),
        [
            ({"unit": "item"}, "unit_mismatch", "unit"),
            ({"code": "Wash Fold"}, "bad_code", "code"),
        ],
    )
    def test_refused_services(
        self, business_a: Business, overrides: dict[str, str], code: str, field: str
    ) -> None:
        with tenant_context(business_a.id):
            category = ServiceCategoryFactory()
        response = self.create(as_role(business_a), category, **overrides)
        assert response.status_code == 400
        assert response.json()["code"] == code
        assert field in fields_of(response)

    def test_a_bad_choice_is_a_validation_error(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            category = ServiceCategoryFactory()
        response = self.create(as_role(business_a), category, pricing_model="hourly")
        assert response.status_code == 400
        assert "pricing_model" in fields_of(response)

    def test_another_business_category_is_unknown(
        self, business_a: Business, business_b: Business
    ) -> None:
        with tenant_context(business_b.id):
            theirs = ServiceCategoryFactory()
        response = self.create(as_role(business_a), theirs)
        assert response.status_code == 400
        assert response.json()["code"] == "unknown_category"

    def test_price_then_switch_on(self, business_a: Business) -> None:
        service = make_service(business_a)
        client = as_role(business_a)
        refused = client.post(f"{BASE}/services/{service.pk}/activate")
        assert refused.status_code == 400
        assert refused.json()["code"] == "needs_price"
        priced = client.post(
            f"{BASE}/services/{service.pk}/prices",
            {"unit_price": "120.00", "minimum_charge": "500.00"},
            format="json",
        )
        assert priced.status_code == 201
        assert priced.json()["unit_price"] == "120.00"  # text, never a number
        response = client.post(f"{BASE}/services/{service.pk}/activate")
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is True
        assert body["current_price"]["unit_price"] == "120.00"
        off = client.post(f"{BASE}/services/{service.pk}/deactivate")
        assert off.json()["is_active"] is False

    def test_how_it_is_priced_is_fixed_once_priced(self, business_a: Business) -> None:
        service = make_service(business_a)
        client = as_role(business_a)
        client.post(f"{BASE}/services/{service.pk}/prices", {"unit_price": "120.00"}, format="json")
        response = client.post(
            f"{BASE}/services/{service.pk}/update",
            {"pricing_model": "per_item", "unit": "item"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["code"] == "pricing_model_locked"
        renamed = client.post(
            f"{BASE}/services/{service.pk}/update", {"name_en": "Wash & fold"}, format="json"
        )
        assert renamed.json()["name_en"] == "Wash & fold"

    def test_reorder(self, business_a: Business) -> None:
        a, b = make_service(business_a), make_service(business_a)
        response = as_role(business_a).post(
            f"{BASE}/services/reorder", {"service_ids": [str(b.pk), str(a.pk)]}, format="json"
        )
        assert response.status_code == 200
        assert [x["id"] for x in response.json()] == [str(b.pk), str(a.pk)]

    @pytest.mark.parametrize("action", ["update", "activate", "deactivate", "prices"])
    def test_cross_business(self, business_a: Business, business_b: Business, action: str) -> None:
        data = {"name_en": "X"} if action == "update" else None
        if action == "prices":
            data = {"unit_price": "100.00"}

        def make() -> Service:
            service: Service = ServiceFactory(is_active=False)
            if action == "activate":
                services.set_price(service, unit_price=Decimal("100.00"))
            return service

        assert_cross_business_404(
            owner=business_b,
            owner_client=as_role(business_b),
            intruder=as_role(business_a),
            make_object=make,
            url_for=lambda x: f"{BASE}/services/{x.pk}/{action}",
            method="post",
            data=data,
        )

    def test_listing_prices_across_businesses(
        self, business_a: Business, business_b: Business
    ) -> None:
        assert_cross_business_404(
            owner=business_b,
            owner_client=as_role(business_b),
            intruder=as_role(business_a),
            make_object=lambda: ServiceFactory(is_active=False),
            url_for=lambda x: f"{BASE}/services/{x.pk}/prices",
        )


class TestPrices:
    def test_amounts_must_be_text(self, business_a: Business) -> None:
        service = make_service(business_a)
        response = as_role(business_a).post(
            f"{BASE}/services/{service.pk}/prices", {"unit_price": 120.5}, format="json"
        )
        assert response.status_code == 400
        assert fields_of(response) == {"unit_price": ['Send amounts as text, like "120.00".']}

    def test_a_start_in_the_past_is_refused(self, business_a: Business) -> None:
        service = make_service(business_a)
        response = as_role(business_a).post(
            f"{BASE}/services/{service.pk}/prices",
            {"unit_price": "120.00", "effective_from": (NOW - timedelta(days=1)).isoformat()},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["code"] == "starts_in_past"
        assert fields_of(response) == {
            "effective_from": ["A new price can start now or later, not in the past."]
        }

    def test_versions_newest_first_and_branch_overrides(self, business_a: Business) -> None:
        service = make_service(business_a)
        with tenant_context(business_a.id):
            branch = BranchFactory()
        client = as_role(business_a)
        url = f"{BASE}/services/{service.pk}/prices"
        client.post(url, {"unit_price": "120.00"}, format="json")
        later = (NOW + timedelta(days=7)).isoformat()
        client.post(url, {"unit_price": "130.00", "effective_from": later}, format="json")
        client.post(url, {"unit_price": "110.00", "branch_id": str(branch.pk)}, format="json")
        business_wide = client.get(url).json()["results"]
        assert [p["unit_price"] for p in business_wide] == ["130.00", "120.00"]
        overrides = client.get(url, {"branch_id": str(branch.pk)}).json()["results"]
        assert [p["unit_price"] for p in overrides] == ["110.00"]

    def test_a_minimum_on_a_per_item_service(self, business_a: Business) -> None:
        service = make_service(business_a, pricing_model="per_item", unit="item")
        response = as_role(business_a).post(
            f"{BASE}/services/{service.pk}/prices",
            {"unit_price": "450.00", "minimum_charge": "100.00"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["code"] == "minimum_per_kg_only"

    def test_setting_a_price_is_audited_against_the_person(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        service = make_service(business_a)
        client_for(business_a, sign_in(owner).access).post(
            f"{BASE}/services/{service.pk}/prices", {"unit_price": "120.00"}, format="json"
        )
        with tenant_context(business_a.id):
            row = AuditLog.objects.get(action="catalog.price.set")
            assert row.actor_id == owner.pk
            assert row.after is not None
            assert row.after["unit_price"] == "120.00"
            assert ServicePrice.objects.count() == 1


class TestModifiers:
    def test_a_percentage_for_all_services(self, business_a: Business) -> None:
        response = as_role(business_a).post(
            f"{BASE}/modifiers",
            {"name_en": "Express", "kind": "express", "percent": "50.00"},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert (body["percent"], body["amount"], body["applies_to_all"]) == ("50.00", None, True)

    def test_an_amount_for_chosen_services(self, business_a: Business) -> None:
        service = make_service(business_a)
        response = as_role(business_a).post(
            f"{BASE}/modifiers",
            {
                "name_en": "Hypoallergenic",
                "kind": "preference",
                "amount": "100.00",
                "applies_to_all": False,
                "service_ids": [str(service.pk)],
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["service_ids"] == [str(service.pk)]

    def test_both_a_percentage_and_an_amount(self, business_a: Business) -> None:
        response = as_role(business_a).post(
            f"{BASE}/modifiers",
            {"name_en": "Express", "kind": "express", "percent": "50", "amount": "200.00"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["code"] == "percent_or_amount"

    def test_update_and_list(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            modifier = PriceModifierFactory(name_en="Express", percent=Decimal("50.00"))
        client = as_role(business_a)
        response = client.post(
            f"{BASE}/modifiers/{modifier.pk}/update",
            {"amount": "250.00", "is_active": False},
            format="json",
        )
        assert response.status_code == 200
        assert (response.json()["percent"], response.json()["amount"]) == (None, "250.00")
        listed = client.get(f"{BASE}/modifiers").json()
        assert [(m["name_en"], m["is_active"]) for m in listed] == [("Express", False)]
        with tenant_context(business_a.id):
            assert PriceModifier.objects.get().amount == Decimal("250.00")

    def test_cross_business(self, business_a: Business, business_b: Business) -> None:
        assert_cross_business_404(
            owner=business_b,
            owner_client=as_role(business_b),
            intruder=as_role(business_a),
            make_object=PriceModifierFactory,
            url_for=lambda m: f"{BASE}/modifiers/{m.pk}/update",
            method="post",
            data={"name_en": "Renamed"},
        )
