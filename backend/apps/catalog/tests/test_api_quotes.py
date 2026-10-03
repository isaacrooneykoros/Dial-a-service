"""POST /api/v1/quotes (M2 T08): breakdowns match pricing.py; permissions; isolation."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import time_machine

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tests.helpers import assert_cross_business_token_rejected, client_for, sign_in
from apps.branches.tests.factories import BranchFactory
from apps.catalog import services
from apps.catalog.models import PriceModifier, Service
from apps.catalog.tests.factories import ServiceFactory
from apps.core.tenant_context import tenant_context
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

URL = "/api/v1/quotes"
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen() -> Iterator[None]:
    with time_machine.travel(NOW, tick=False):
        yield


def person(business: Business, role: str = Role.STAFF, **fields: Any) -> User:
    with tenant_context(business.id):
        user: User = UserFactory(role=role, **fields)
    return user


def as_user(business: Business, user: User) -> Any:
    return client_for(business, sign_in(user).access)


def priced(business: Business, price: str, minimum: str = "0", **fields: Any) -> Service:
    with tenant_context(business.id):
        service: Service = ServiceFactory(is_active=False, **fields)
        services.set_price(service, unit_price=Decimal(price), minimum_charge=Decimal(minimum))
        services.set_service_active(service, True)
    return service


def express(business: Business, **fields: Any) -> PriceModifier:
    with tenant_context(business.id):
        return services.create_modifier(name_en="Express", kind="express", **fields)


def ask(client: Any, **body: Any) -> Any:
    return client.post(URL, body, format="json")


class TestBreakdown:
    def test_a_counter_order(self, business_a: Business) -> None:
        # 6.4 kg x 120 = 768 x 1.5 Express = 1152; 2 duvets 900 -> 2052
        wash = priced(business_a, "120.00", "500.00")
        duvet = priced(business_a, "450.00", pricing_model="per_item", unit="item")
        fast = express(
            business_a, percent=Decimal("50"), applies_to_all=False, service_ids=[wash.pk]
        )
        response = ask(
            as_user(business_a, person(business_a)),
            lines=[
                {"service_id": str(wash.pk), "quantity": "6.40"},
                {"service_id": str(duvet.pk), "quantity": "2"},
            ],
            modifier_ids=[str(fast.pk)],
        )
        assert response.status_code == 200
        body = response.json()
        assert [line["amount"] for line in body["lines"]] == ["1152.00", "900.00"]
        assert body["lines"][0]["name_en"] == wash.name_en
        assert (body["subtotal"], body["total"], body["vat_registered"]) == (
            "2052.00",
            "2052",
            False,
        )
        assert body["lines"][0]["modifier_ids"] == [str(fast.pk)]

    def test_vat_and_the_discount_follow_the_business_settings(self, business_a: Business) -> None:
        duvet = priced(business_a, "450.00", pricing_model="per_item", unit="item")
        with tenant_context(business_a.id):
            tenancy_services.set_setting("vat.registered", True)
            tenancy_services.set_setting("vat.prices_include_vat", False)
            tenancy_services.set_setting("discounts.max_percent", "10")
        response = ask(
            as_user(business_a, person(business_a, Role.MANAGER)),
            lines=[{"service_id": str(duvet.pk), "quantity": "2"}],
            discount={"percent": "10", "reason": "Regular customer"},
        )
        # (900 - 90) = 810 + 16% 129.60 = 939.60 -> 940
        body = response.json()
        assert (body["discount"], body["vat"], body["total"], body["rounding"]) == (
            "90.00",
            "129.60",
            "940",
            "0.40",
        )

    def test_a_branch_override(self, business_a: Business) -> None:
        wash = priced(business_a, "120.00")
        with tenant_context(business_a.id):
            branch = BranchFactory()
            services.set_price(wash, unit_price=Decimal("100.00"), branch_id=branch.pk)
        response = ask(
            as_user(business_a, person(business_a)),
            lines=[{"service_id": str(wash.pk), "quantity": "5"}],
            branch_id=str(branch.pk),
        )
        assert response.json()["total"] == "500"

    def test_nothing_is_saved(self, business_a: Business) -> None:
        wash = priced(business_a, "120.00")
        client = as_user(business_a, person(business_a))
        with tenant_context(business_a.id):
            before = Service.objects.get(pk=wash.pk).updated_at
        ask(client, lines=[{"service_id": str(wash.pk), "quantity": "5"}])
        with tenant_context(business_a.id):
            assert Service.objects.get(pk=wash.pk).updated_at == before


class TestRefusals:
    def code(self, response: Any) -> tuple[int, str, list[str]]:
        body = response.json()
        return response.status_code, body["code"], list(body["fields"])

    def test_a_switched_off_or_unpriced_service(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            off: Service = ServiceFactory(is_active=False, name_en="Shoes")
        client = as_user(business_a, person(business_a))
        response = ask(client, lines=[{"service_id": str(off.pk), "quantity": "1"}])
        assert self.code(response) == (400, "service_off", ["lines.0.service_id"])
        assert response.json()["message"] == "Shoes is switched off, so it can't be priced."

    def test_quantities_must_be_text_and_fit_the_model(self, business_a: Business) -> None:
        duvet = priced(business_a, "450.00", pricing_model="per_item", unit="item")
        client = as_user(business_a, person(business_a))
        as_number = ask(client, lines=[{"service_id": str(duvet.pk), "quantity": 2}])
        assert as_number.status_code == 400
        assert "lines" in as_number.json()["fields"] or any(
            key.startswith("lines") for key in as_number.json()["fields"]
        )
        half = ask(client, lines=[{"service_id": str(duvet.pk), "quantity": "1.5"}])
        assert self.code(half) == (400, "bad_quantity", ["lines.0.quantity"])

    def test_no_lines(self, business_a: Business) -> None:
        response = ask(as_user(business_a, person(business_a)), lines=[])
        assert response.status_code == 400

    def test_an_unknown_or_switched_off_modifier(self, business_a: Business) -> None:
        wash = priced(business_a, "120.00")
        fast = express(business_a, percent=Decimal("50"))
        with tenant_context(business_a.id):
            services.update_modifier(fast, is_active=False)
        response = ask(
            as_user(business_a, person(business_a)),
            lines=[{"service_id": str(wash.pk), "quantity": "5"}],
            modifier_ids=[str(fast.pk)],
        )
        assert self.code(response) == (400, "unknown_modifier", ["modifier_ids"])

    def test_staff_need_the_discount_right(self, business_a: Business) -> None:
        wash = priced(business_a, "120.00")
        with tenant_context(business_a.id):
            tenancy_services.set_setting("discounts.max_percent", "20")
        body = {
            "lines": [{"service_id": str(wash.pk), "quantity": "5"}],
            "discount": {"amount": "50.00", "reason": "Late"},
        }
        plain = as_user(business_a, person(business_a))
        assert self.code(ask(plain, **body))[:2] == (400, "no_discount_right")
        allowed = as_user(business_a, person(business_a, can_give_discounts=True))
        assert ask(allowed, **body).json()["discount"] == "50.00"

    def test_a_discount_needs_a_reason_and_stays_under_the_cap(self, business_a: Business) -> None:
        wash = priced(business_a, "120.00")
        manager = as_user(business_a, person(business_a, Role.MANAGER))
        line = [{"service_id": str(wash.pk), "quantity": "5"}]
        no_reason = ask(manager, lines=line, discount={"percent": "5", "reason": " "})
        assert self.code(no_reason) == (400, "discount_reason_required", ["discount.reason"])
        # D-56: the cap is 0% until the owner sets one.
        over = ask(manager, lines=line, discount={"percent": "5", "reason": "Regular"})
        assert self.code(over) == (400, "discount_over_cap", ["discount"])

    def test_an_unknown_branch(self, business_a: Business, business_b: Business) -> None:
        wash = priced(business_a, "120.00")
        with tenant_context(business_b.id):
            theirs = BranchFactory()
        response = ask(
            as_user(business_a, person(business_a)),
            lines=[{"service_id": str(wash.pk), "quantity": "5"}],
            branch_id=str(theirs.pk),
        )
        assert self.code(response) == (400, "unknown_branch", ["branch_id"])


class TestAccess:
    @pytest.mark.parametrize(
        ("role", "status"),
        [(Role.OWNER, 200), (Role.MANAGER, 200), (Role.STAFF, 200), (Role.ACCOUNTANT, 403)],
    )
    def test_the_counter_roles(self, business_a: Business, role: str, status: int) -> None:
        wash = priced(business_a, "120.00")
        client = as_user(business_a, person(business_a, role))
        response = ask(client, lines=[{"service_id": str(wash.pk), "quantity": "5"}])
        assert response.status_code == status

    def test_signed_out(self, business_a: Business) -> None:
        assert client_for(business_a).post(URL, {}, format="json").status_code == 401

    def test_another_business_service_is_unknown(
        self, business_a: Business, business_b: Business
    ) -> None:
        theirs = priced(business_b, "120.00")
        response = ask(
            as_user(business_a, person(business_a)),
            lines=[{"service_id": str(theirs.pk), "quantity": "5"}],
        )
        assert (response.status_code, response.json()["code"]) == (400, "unknown_service")

    def test_cross_business_token(self, business_a: Business, business_b: Business) -> None:
        wash = priced(business_a, "120.00")
        assert_cross_business_token_rejected(
            user=person(business_a),
            other=business_b,
            url=URL,
            method="post",
            data={"lines": [{"service_id": str(wash.pk), "quantity": "5"}]},
        )
