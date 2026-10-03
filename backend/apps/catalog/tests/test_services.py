"""Catalogue services and selectors (M2 T04): price versions, overrides, audit."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import time_machine
from django.db import IntegrityError

from apps.branches.tests.factories import BranchFactory
from apps.catalog import selectors, services
from apps.catalog.models import PriceModifier, Service, ServicePrice
from apps.catalog.pricing import LineInput, VatInput, quote
from apps.catalog.services import CatalogError
from apps.catalog.tests.factories import (
    PriceModifierFactory,
    ServiceCategoryFactory,
    ServiceFactory,
)
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
LATER_STILL = NOW + timedelta(days=30)


@pytest.fixture
def frozen() -> Iterator[time_machine.Traveller]:
    with time_machine.travel(NOW, tick=False) as traveller:
        yield traveller


@pytest.fixture
def ctx(business_a: Business, frozen: time_machine.Traveller) -> Iterator[Business]:
    with tenant_context(business_a.id):
        yield business_a


def per_kg(**fields: object) -> Service:
    service: Service = ServiceFactory(
        pricing_model=Service.PricingModel.PER_KG, unit=Service.Unit.KG, is_active=False, **fields
    )
    return service


def per_item(**fields: object) -> Service:
    service: Service = ServiceFactory(
        pricing_model=Service.PricingModel.PER_ITEM,
        unit=Service.Unit.ITEM,
        is_active=False,
        **fields,
    )
    return service


def code_of(error: pytest.ExceptionInfo[CatalogError]) -> tuple[str, str | None]:
    return error.value.code, error.value.field


class TestSetPrice:
    def test_a_first_price_starts_now_and_stays(self, ctx: Business) -> None:
        service = per_kg()
        price = services.set_price(
            service, unit_price=Decimal("120.00"), minimum_charge=Decimal("500.00")
        )
        assert (price.effective_from, price.effective_to) == (NOW, None)
        assert (price.unit_price, price.minimum_charge, price.currency) == (
            Decimal("120.00"),
            Decimal("500.00"),
            "KES",
        )
        assert selectors.price_at(service.pk) == price

    def test_a_new_price_closes_the_current_one(
        self, ctx: Business, frozen: time_machine.Traveller
    ) -> None:
        service = per_kg()
        old = services.set_price(service, unit_price=Decimal("120.00"))
        frozen.shift(timedelta(days=1))
        new = services.set_price(service, unit_price=Decimal("130.00"))
        old.refresh_from_db()
        assert old.effective_to == new.effective_from == NOW + timedelta(days=1)
        assert new.effective_to is None
        assert selectors.price_at(service.pk) == new
        # History is unchanged: yesterday's price is still yesterday's.
        assert selectors.price_at(service.pk, at=NOW) == old

    def test_a_future_price_waits_its_turn(self, ctx: Business) -> None:
        service = per_kg()
        current = services.set_price(service, unit_price=Decimal("120.00"))
        future = services.set_price(service, unit_price=Decimal("140.00"), effective_from=LATER)
        current.refresh_from_db()
        assert current.effective_to == LATER
        assert selectors.price_at(service.pk) == current
        assert selectors.price_at(service.pk, at=LATER) == future
        assert selectors.price_at(service.pk, at=LATER - timedelta(microseconds=1)) == current

    def test_a_price_set_before_a_scheduled_one_ends_where_it_starts(self, ctx: Business) -> None:
        service = per_kg()
        services.set_price(service, unit_price=Decimal("120.00"))
        scheduled = services.set_price(
            service, unit_price=Decimal("150.00"), effective_from=LATER_STILL
        )
        middle = services.set_price(service, unit_price=Decimal("135.00"), effective_from=LATER)
        assert (middle.effective_from, middle.effective_to) == (LATER, LATER_STILL)
        assert selectors.price_at(service.pk, at=LATER_STILL) == scheduled

    def test_a_scheduled_price_is_replaced_by_setting_the_same_start(self, ctx: Business) -> None:
        service = per_kg()
        scheduled = services.set_price(service, unit_price=Decimal("140.00"), effective_from=LATER)
        replaced = services.set_price(service, unit_price=Decimal("145.00"), effective_from=LATER)
        assert replaced.pk == scheduled.pk
        assert replaced.unit_price == Decimal("145.00")
        assert ServicePrice.objects.filter(service=service).count() == 1

    def test_a_gap_stays_a_gap(self, ctx: Business) -> None:
        # A version ending before the next one starts: a new price inside it keeps the gap.
        service = per_kg()
        first = ServicePrice.objects.create(
            service=service, unit_price=Decimal("120.00"), effective_from=NOW, effective_to=LATER
        )
        ServicePrice.objects.create(
            service=service, unit_price=Decimal("150.00"), effective_from=LATER_STILL
        )
        middle = services.set_price(
            service, unit_price=Decimal("125.00"), effective_from=NOW + timedelta(days=1)
        )
        first.refresh_from_db()
        assert first.effective_to == middle.effective_from
        assert middle.effective_to == LATER  # not stretched over the gap
        assert selectors.price_at(service.pk, at=LATER + timedelta(days=1)) is None

    def test_the_past_is_read_only(self, ctx: Business) -> None:
        service = per_kg()
        with pytest.raises(CatalogError) as error:
            services.set_price(
                service, unit_price=Decimal("100.00"), effective_from=NOW - timedelta(hours=1)
            )
        assert code_of(error) == ("starts_in_past", "effective_from")

    def test_a_moment_ago_counts_as_now(self, ctx: Business) -> None:
        service = per_kg()
        price = services.set_price(
            service, unit_price=Decimal("100.00"), effective_from=NOW - timedelta(seconds=30)
        )
        assert price.effective_from == NOW

    def test_a_start_without_a_timezone_is_refused(self, ctx: Business) -> None:
        with pytest.raises(CatalogError) as error:
            services.set_price(
                per_kg(),
                unit_price=Decimal("100.00"),
                effective_from=datetime(2026, 11, 1),  # noqa: DTZ001 - naive on purpose
            )
        assert code_of(error) == ("bad_start", "effective_from")

    @pytest.mark.parametrize(
        ("unit_price", "field"),
        [
            (Decimal("0.00"), "unit_price"),
            (Decimal("-5.00"), "unit_price"),
            (Decimal("10.005"), "unit_price"),
            (Decimal("10000000000.00"), "unit_price"),
        ],
    )
    def test_bad_prices(self, ctx: Business, unit_price: Decimal, field: str) -> None:
        with pytest.raises(CatalogError) as error:
            services.set_price(per_kg(), unit_price=unit_price)
        assert code_of(error) == ("bad_amount", field)

    def test_floats_are_refused(self, ctx: Business) -> None:
        with pytest.raises(CatalogError) as error:
            services.set_price(per_kg(), unit_price=120.0)  # type: ignore[arg-type]
        assert code_of(error) == ("bad_amount", "unit_price")

    def test_a_minimum_is_for_per_kg_only(self, ctx: Business) -> None:
        with pytest.raises(CatalogError) as error:
            services.set_price(
                per_item(), unit_price=Decimal("450.00"), minimum_charge=Decimal("100.00")
            )
        assert code_of(error) == ("minimum_per_kg_only", "minimum_charge")

    def test_every_change_is_audited_with_before_and_after(
        self, ctx: Business, frozen: time_machine.Traveller
    ) -> None:
        service = per_kg()
        services.set_price(service, unit_price=Decimal("120.00"))
        frozen.shift(timedelta(hours=1))
        services.set_price(service, unit_price=Decimal("130.00"))
        rows = list(AuditLog.objects.filter(action="catalog.price.set").order_by("created_at"))
        assert len(rows) == 2
        assert rows[0].before is None
        assert rows[1].before is not None
        assert rows[1].before["unit_price"] == "120.00"
        assert rows[1].after is not None
        assert rows[1].after["unit_price"] == "130.00"  # strings, never floats

    def test_a_clash_the_database_refuses_becomes_a_clear_error(
        self, ctx: Business, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two people setting one price at the same moment are serialised by the row
        # lock, and the database refuses any overlap (T01). If it ever does refuse one,
        # the caller gets a clear error instead of a crash.
        service = per_kg()

        def clash(*args: object, **kwargs: object) -> None:
            raise IntegrityError("price_versions_never_overlap")

        monkeypatch.setattr(ServicePrice.objects, "create", clash)
        with pytest.raises(CatalogError) as error:
            services.set_price(service, unit_price=Decimal("120.00"))
        assert code_of(error) == ("price_conflict", "effective_from")


class TestBranchOverrides:
    def test_an_override_wins_only_at_its_branch(self, ctx: Business) -> None:
        service = per_kg()
        kilimani, westlands = BranchFactory(), BranchFactory()
        business_wide = services.set_price(service, unit_price=Decimal("120.00"))
        override = services.set_price(service, unit_price=Decimal("110.00"), branch_id=kilimani.pk)
        assert selectors.price_at(service.pk, branch_id=kilimani.pk) == override
        assert selectors.price_at(service.pk, branch_id=westlands.pk) == business_wide
        assert selectors.price_at(service.pk) == business_wide

    def test_overrides_have_their_own_versions(self, ctx: Business) -> None:
        service = per_kg()
        branch = BranchFactory()
        services.set_price(service, unit_price=Decimal("120.00"))
        first = services.set_price(service, unit_price=Decimal("110.00"), branch_id=branch.pk)
        second = services.set_price(
            service, unit_price=Decimal("115.00"), branch_id=branch.pk, effective_from=LATER
        )
        first.refresh_from_db()
        assert first.effective_to == LATER
        assert [p.pk for p in selectors.price_versions(service.pk, branch_id=branch.pk)] == [
            second.pk,
            first.pk,
        ]
        assert selectors.price_versions(service.pk).count() == 1  # business-wide untouched

    def test_an_unknown_or_closed_branch_is_refused(self, ctx: Business) -> None:
        closed = BranchFactory(status="closed")
        with pytest.raises(CatalogError) as error:
            services.set_price(per_kg(), unit_price=Decimal("100.00"), branch_id=closed.pk)
        assert code_of(error) == ("unknown_branch", "branch_id")

    def test_another_business_branch_is_unknown(
        self, business_a: Business, business_b: Business, frozen: time_machine.Traveller
    ) -> None:
        with tenant_context(business_b.id):
            other = BranchFactory()
        with tenant_context(business_a.id), pytest.raises(CatalogError) as error:
            services.set_price(per_kg(), unit_price=Decimal("100.00"), branch_id=other.pk)
        assert code_of(error) == ("unknown_branch", "branch_id")


class TestServices:
    def test_create_starts_switched_off_and_audited(self, ctx: Business) -> None:
        category = ServiceCategoryFactory()
        service = services.create_service(
            category=category,
            code="duvet",
            name_en="Duvets",
            pricing_model="per_item",
            unit="item",
        )
        assert service.is_active is False
        assert AuditLog.objects.filter(
            action="catalog.service.create", object_id=str(service.pk)
        ).exists()

    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            ({"pricing_model": "per_kg", "unit": "item"}, ("unit_mismatch", "unit")),
            ({"pricing_model": "per_item", "unit": "kg"}, ("unit_mismatch", "unit")),
            ({"pricing_model": "hourly", "unit": "item"}, ("bad_pricing_model", "pricing_model")),
            ({"pricing_model": "per_item", "unit": "box"}, ("bad_unit", "unit")),
            ({"code": "Wash Fold"}, ("bad_code", "code")),
            ({"name_en": "  "}, ("name_required", "name_en")),
        ],
    )
    def test_bad_services(
        self, ctx: Business, fields: dict[str, str], expected: tuple[str, str]
    ) -> None:
        values = {
            "code": "x",
            "name_en": "X",
            "pricing_model": "per_item",
            "unit": "item",
            **fields,
        }
        with pytest.raises(CatalogError) as error:
            services.create_service(category=ServiceCategoryFactory(), **values)
        assert code_of(error) == expected

    def test_codes_are_unique(self, ctx: Business) -> None:
        category = ServiceCategoryFactory()
        values = {"code": "duvet", "name_en": "Duvets", "pricing_model": "per_item", "unit": "item"}
        services.create_service(category=category, **values)
        with pytest.raises(CatalogError) as error:
            services.create_service(category=category, **values)
        assert code_of(error) == ("duplicate_code", "code")

    def test_switching_on_needs_a_current_price(self, ctx: Business) -> None:
        service = per_kg()
        with pytest.raises(CatalogError) as error:
            services.set_service_active(service, True)
        assert code_of(error) == ("needs_price", "is_active")
        services.set_price(service, unit_price=Decimal("120.00"), effective_from=LATER)
        with pytest.raises(CatalogError):
            services.set_service_active(service, True)  # a future price isn't current
        services.set_price(service, unit_price=Decimal("120.00"))
        assert services.set_service_active(service, True).is_active is True
        assert services.set_service_active(service, False).is_active is False

    def test_the_pricing_model_is_fixed_once_priced(self, ctx: Business) -> None:
        service = per_kg()
        services.update_service(service, pricing_model="per_item", unit="item")  # no price yet
        services.set_price(service, unit_price=Decimal("450.00"))
        with pytest.raises(CatalogError) as error:
            services.update_service(service, pricing_model="per_kg", unit="kg")
        assert code_of(error) == ("pricing_model_locked", "pricing_model")
        services.update_service(service, name_en="Duvets (any size)")  # renaming is fine

    def test_reorder(self, ctx: Business) -> None:
        a, b, c = per_kg(), per_kg(), per_kg()
        services.reorder_services([c.pk, a.pk, b.pk])
        assert [s.pk for s in Service.objects.order_by("position")] == [c.pk, a.pk, b.pk]

    @pytest.mark.parametrize("problem", ["duplicate", "unknown"])
    def test_reorder_refuses_bad_lists(self, ctx: Business, problem: str) -> None:
        a = per_kg()
        ids: list[object] = (
            [a.pk, a.pk]
            if problem == "duplicate"
            else [a.pk, "00000000-0000-0000-0000-000000000001"]
        )
        with pytest.raises(CatalogError) as error:
            services.reorder_services(ids)
        assert error.value.field == "service_ids"


class TestCategories:
    def test_create_update_and_unique_names(self, ctx: Business) -> None:
        wash = services.create_category(name_en="Wash", name_sw="Kufua")
        special = services.create_category(name_en="Special items")
        assert (wash.position, special.position) == (0, 1)
        with pytest.raises(CatalogError) as error:
            services.create_category(name_en="Wash")
        assert code_of(error) == ("duplicate_name", "name_en")
        with pytest.raises(CatalogError):
            services.update_category(special, name_en="Wash")
        assert special.name_en == "Special items"  # the refused name isn't left behind
        assert services.update_category(special, is_active=False).is_active is False


class TestModifiers:
    def test_a_percentage_for_all_services(self, ctx: Business) -> None:
        express = services.create_modifier(
            name_en="Express", kind="express", percent=Decimal("50.00")
        )
        assert express.applies_to_all
        assert selectors.modifier_service_ids(express) is None

    def test_an_amount_for_chosen_services(self, ctx: Business) -> None:
        wash = per_kg()
        hypo = services.create_modifier(
            name_en="Hypoallergenic",
            kind="preference",
            amount=Decimal("100.00"),
            applies_to_all=False,
            service_ids=[wash.pk],
        )
        assert selectors.modifier_service_ids(hypo) == frozenset({str(wash.pk)})

    @pytest.mark.parametrize(
        ("fields", "code"),
        [
            ({"percent": Decimal("50"), "amount": Decimal("10.00")}, "percent_or_amount"),
            ({}, "percent_or_amount"),
            ({"percent": Decimal("0")}, "bad_percent"),
            ({"percent": Decimal("1000.00")}, "bad_percent"),
            ({"percent": Decimal("12.345")}, "bad_percent"),
            ({"amount": Decimal("0.00")}, "bad_amount"),
            ({"percent": Decimal("10"), "kind": "discount"}, "bad_kind"),
            ({"percent": Decimal("10"), "applies_to_all": False}, "unknown_service"),
        ],
    )
    def test_bad_modifiers(self, ctx: Business, fields: dict[str, object], code: str) -> None:
        values: dict[str, object] = {"name_en": "Express", "kind": "express", **fields}
        with pytest.raises(CatalogError) as error:
            services.create_modifier(**values)  # type: ignore[arg-type]
        assert error.value.code == code

    def test_a_list_for_an_all_services_modifier_is_a_contradiction(self, ctx: Business) -> None:
        with pytest.raises(CatalogError) as error:
            services.create_modifier(
                name_en="Express", kind="express", percent=Decimal("50"), service_ids=[per_kg().pk]
            )
        assert code_of(error) == ("applies_to_all", "service_ids")

    def test_update_changes_value_and_services(self, ctx: Business) -> None:
        wash, duvet = per_kg(), per_item()
        modifier = services.create_modifier(
            name_en="Express", kind="express", percent=Decimal("50")
        )
        services.update_modifier(modifier, amount=Decimal("200.00"))
        assert (modifier.percent, modifier.amount) == (None, Decimal("200.00"))
        services.update_modifier(modifier, applies_to_all=False, service_ids=[wash.pk])
        assert selectors.modifier_service_ids(modifier) == frozenset({str(wash.pk)})
        services.update_modifier(modifier, service_ids=[duvet.pk])
        assert selectors.modifier_service_ids(modifier) == frozenset({str(duvet.pk)})
        services.update_modifier(modifier, applies_to_all=True)
        assert selectors.modifier_service_ids(modifier) is None
        services.update_modifier(modifier, is_active=False)
        assert PriceModifier.objects.get(pk=modifier.pk).is_active is False
        assert AuditLog.objects.filter(action="catalog.modifier.update").count() == 5

    def test_a_refused_update_leaves_the_modifier_as_it_was(self, ctx: Business) -> None:
        services.create_modifier(name_en="Express", kind="express", percent=Decimal("50"))
        hypo = services.create_modifier(name_en="Hypo", kind="preference", amount=Decimal("100.00"))
        with pytest.raises(CatalogError) as error:
            services.update_modifier(hypo, name_en="Express")
        assert code_of(error) == ("duplicate_name", "name_en")
        assert hypo.name_en == "Hypo"
        with pytest.raises(CatalogError):
            services.update_modifier(hypo, applies_to_all=False)  # no services chosen
        assert hypo.applies_to_all is True


class TestPriceListAndSnapshots:
    def test_the_active_price_list(self, ctx: Business) -> None:
        priced, unpriced, off = per_kg(), per_kg(), per_kg()
        services.set_price(priced, unit_price=Decimal("120.00"))
        services.set_service_active(priced, True)
        Service.objects.filter(pk=unpriced.pk).update(is_active=True)  # active, but no price
        services.set_price(off, unit_price=Decimal("90.00"))
        assert [s.pk for s, _ in selectors.active_price_list()] == [priced.pk]

    def test_an_inactive_category_hides_its_services(self, ctx: Business) -> None:
        service = per_kg()
        services.set_price(service, unit_price=Decimal("120.00"))
        services.set_service_active(service, True)
        services.update_category(service.category, is_active=False)
        assert selectors.active_price_list() == []

    def test_snapshots_feed_the_pricing_engine(self, ctx: Business) -> None:
        service = per_kg()
        price = services.set_price(
            service, unit_price=Decimal("120.00"), minimum_charge=Decimal("500.00")
        )
        express = PriceModifierFactory(percent=Decimal("50.00"))
        result = quote(
            [LineInput(selectors.price_snapshot(service, price), Decimal("6.40"))],
            modifiers=[selectors.modifier_snapshot(express)],
            vat=VatInput(registered=False),
        )
        assert result.lines[0].price_id == str(price.pk)
        assert result.total == Decimal("1152")  # 6.4 x 120 x 1.5

    def test_prices_never_cross_businesses(
        self, business_a: Business, business_b: Business, frozen: time_machine.Traveller
    ) -> None:
        with tenant_context(business_a.id):
            service = per_kg()
            services.set_price(service, unit_price=Decimal("120.00"))
        with tenant_context(business_b.id):
            assert selectors.price_at(service.pk) is None
            assert selectors.active_price_list() == []
