"""The price list in GET /business/config (M2 T09, D-59)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import time_machine

from apps.branches.tests.factories import BranchFactory
from apps.catalog import services
from apps.catalog.models import Service
from apps.catalog.tests.factories import ServiceFactory
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import AppClient, host_of
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

URL = "/api/v1/business/config"
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen() -> Iterator[time_machine.Traveller]:
    with time_machine.travel(NOW, tick=False) as traveller:
        yield traveller


def catalog(business: Business) -> Any:
    client = AppClient(headers={"host": host_of(business)}, raise_request_exception=False)
    response = client.get(URL)  # public: no sign-in
    assert response.status_code == 200
    return response.json()["catalog"]


def priced(price: str, *, active: bool = True, **fields: Any) -> Service:
    service: Service = ServiceFactory(is_active=False, **fields)
    services.set_price(service, unit_price=Decimal(price))
    if active:
        services.set_service_active(service, True)
    return service


def test_only_active_priced_services_with_their_categories(business_a: Business) -> None:
    with tenant_context(business_a.id):
        wash = priced("120.00", code="wash-fold", name_en="Wash and fold")
        priced("450.00", active=False, code="duvet")  # switched off
        ServiceFactory(is_active=False, code="shoes")  # no price
    body = catalog(business_a)
    assert [s["code"] for s in body["services"]] == ["wash-fold"]
    service = body["services"][0]
    assert (service["unit_price"], service["minimum_charge"], service["currency"]) == (
        "120.00",
        "0.00",
        "KES",
    )
    assert [c["id"] for c in body["categories"]] == [str(wash.category_id)]


def test_modifiers_and_vat(business_a: Business) -> None:
    with tenant_context(business_a.id):
        wash = priced("120.00")
        services.create_modifier(name_en="Express", kind="express", percent=Decimal("50"))
        services.create_modifier(
            name_en="Hypo",
            kind="preference",
            amount=Decimal("100.00"),
            applies_to_all=False,
            service_ids=[wash.pk],
        )
        off = services.create_modifier(name_en="Old", kind="express", percent=Decimal("10"))
        services.update_modifier(off, is_active=False)
        tenancy_services.set_setting("vat.registered", True)
    body = catalog(business_a)
    assert [(m["name_en"], m["percent"], m["amount"]) for m in body["modifiers"]] == [
        ("Express", "50.00", None),
        ("Hypo", None, "100.00"),
    ]
    assert body["modifiers"][1]["service_ids"] == [str(wash.pk)]
    assert body["vat"] == {"registered": True, "rate": "16.00", "prices_include_vat": True}


def test_a_price_change_shows_at_once_and_history_does_not(
    business_a: Business, frozen: time_machine.Traveller
) -> None:
    with tenant_context(business_a.id):
        wash = priced("120.00")
        services.set_price(
            wash, unit_price=Decimal("150.00"), effective_from=NOW + timedelta(days=1)
        )
    assert catalog(business_a)["services"][0]["unit_price"] == "120.00"  # the future price waits
    frozen.shift(timedelta(days=1, seconds=1))
    assert catalog(business_a)["services"][0]["unit_price"] == "150.00"


def test_branch_overrides_stay_private(business_a: Business) -> None:
    with tenant_context(business_a.id):
        wash = priced("120.00")
        services.set_price(wash, unit_price=Decimal("99.00"), branch_id=BranchFactory().pk)
    assert [s["unit_price"] for s in catalog(business_a)["services"]] == ["120.00"]


def test_another_business_prices_never_appear(business_a: Business, business_b: Business) -> None:
    with tenant_context(business_a.id):
        priced("120.00", code="wash-fold")
    with tenant_context(business_b.id):
        priced("200.00", code="ironing")
    assert [s["code"] for s in catalog(business_a)["services"]] == ["wash-fold"]
    assert [s["code"] for s in catalog(business_b)["services"]] == ["ironing"]


def test_a_business_with_nothing_priced(business_a: Business) -> None:
    assert catalog(business_a) == {
        "categories": [],
        "services": [],
        "modifiers": [],
        "vat": {"registered": False, "rate": "16.00", "prices_include_vat": True},
    }
