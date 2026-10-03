"""CSV price import (M2 T07, A-31)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import time_machine

from apps.catalog import imports, selectors, services
from apps.catalog.imports import CatalogImportError, preview, read_rows
from apps.catalog.models import Service, ServiceCategory, ServicePrice
from apps.catalog.services import CatalogError
from apps.catalog.tests.factories import ServiceCategoryFactory, ServiceFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
HEADER = "service,category,pricing_model,price,minimum\n"


def file_error(text: str) -> CatalogImportError:
    with pytest.raises(CatalogImportError) as error:
        read_rows(text)
    return error.value


class TestReadingTheFile:
    def test_a_plain_file(self) -> None:
        rows = read_rows(HEADER + "Wash and fold,Wash,per_kg,120,500\n")
        assert rows == [
            {
                "service": "Wash and fold",
                "category": "Wash",
                "pricing_model": "per_kg",
                "price": "120",
                "minimum": "500",
                "_line": 2,
            }
        ]

    def test_excel_extras_bom_semicolons_and_friendly_headers(self) -> None:
        bom = chr(0xFEFF)  # Excel's byte-order mark
        text = (
            f"{bom}Service;Category;Pricing model;Price;Minimum charge\r\n"
            "Duvets;Special;per item;450;\r\n"
        )
        rows = read_rows(text)
        assert rows[0]["pricing_model"] == "per item"
        assert rows[0]["price"] == "450"
        assert rows[0]["minimum"] == ""

    def test_quoted_values_keep_their_commas(self) -> None:
        rows = read_rows(HEADER + '"Suits, two piece",Special,per_item,800,\n')
        assert rows[0]["service"] == "Suits, two piece"

    def test_blank_lines_are_skipped_and_line_numbers_kept(self) -> None:
        rows = read_rows(
            HEADER + "\nDuvets,Special,per_item,450,\n,,,,\nShoes,Special,per_item,300,\n"
        )
        assert [r["_line"] for r in rows] == [3, 5]

    @pytest.mark.parametrize(
        ("text", "code"),
        [
            ("", "empty"),
            ("   \n", "empty"),
            (HEADER, "empty"),
            ("service,price\nDuvets,450\n", "missing_columns"),
        ],
    )
    def test_files_that_cannot_be_imported(self, text: str, code: str) -> None:
        assert file_error(text).code == code

    def test_missing_columns_are_named(self) -> None:
        assert file_error("service,price\nDuvets,450\n").detail == {
            "columns": ["category", "pricing_model"]
        }

    def test_limits(self) -> None:
        assert file_error("x" * (imports.MAX_BYTES + 1)).code == "too_big"
        many = HEADER + "".join(f"S{i},Wash,per_item,10,\n" for i in range(imports.MAX_ROWS + 1))
        assert file_error(many).code == "too_many_rows"


@pytest.fixture
def ctx(business_a: Business) -> Iterator[Business]:
    with time_machine.travel(NOW, tick=False), tenant_context(business_a.id):
        yield business_a


def priced(code: str, name: str, model: str, unit: str, price: str, minimum: str = "0") -> Service:
    category = ServiceCategory.objects.filter(name_en="Wash").first() or ServiceCategoryFactory(
        name_en="Wash"
    )
    service: Service = ServiceFactory(
        code=code, name_en=name, pricing_model=model, unit=unit, category=category, is_active=False
    )
    services.set_price(service, unit_price=Decimal(price), minimum_charge=Decimal(minimum))
    return service


def statuses(text: str) -> list[tuple[str, str]]:
    return [(row.status, row.problem) for row in preview(text).rows]


@pytest.mark.django_db
class TestPreview:
    def test_new_changed_and_unchanged(self, ctx: Business) -> None:
        priced("wash-fold", "Wash and fold", "per_kg", "kg", "120.00", "500.00")
        priced("duvet", "Duvets", "per_item", "item", "450.00")
        result = preview(
            HEADER
            + "Wash and fold,Wash,per_kg,130,500\n"  # changed price
            + "duvet,Special,per_item,450.00,\n"  # by code, unchanged
            + "Curtains,Home,per_item,600,\n"  # new, in a new category
        )
        changed, unchanged, new = result.rows
        assert (changed.status, changed.old_price, changed.price) == ("changed", "120.00", "130.00")
        assert unchanged.status == "unchanged"
        assert unchanged.category == "Wash"  # an existing service keeps its category
        assert (new.status, new.new_code, new.new_category, new.unit) == (
            "new",
            "curtains",
            True,
            "item",
        )
        assert result.counts == {"new": 1, "changed": 1, "unchanged": 1, "invalid": 0}

    def test_names_match_whatever_the_case(self, ctx: Business) -> None:
        priced("duvet", "Duvets", "per_item", "item", "450.00")
        assert statuses(HEADER + "DUVETS,Special,per_item,500,\n") == [("changed", "")]

    @pytest.mark.parametrize(
        ("row", "problem"),
        [
            (",Wash,per_kg,120,", "service_required"),
            ("Ironing,Special,hourly,50,", "bad_pricing_model"),
            ('Ironing,Special,per_item,"1,200",', "price_amount_has_comma"),
            ("Ironing,Special,per_item,12.345,", "price_bad_amount"),
            ("Ironing,Special,per_item,0,", "price_bad_amount"),
            ("Ironing,Special,per_item,-5,", "price_bad_amount"),
            ("Ironing,Special,per_item,KSh 50,", "price_bad_amount"),
            ("Ironing,Special,per_item,50,abc", "minimum_bad_amount"),
            ("Ironing,Special,per_item,50,100", "minimum_per_kg_only"),
            ("Ironing,,per_item,50,", "category_required"),
        ],
    )
    def test_invalid_rows_say_why(self, ctx: Business, row: str, problem: str) -> None:
        assert statuses(HEADER + row + "\n") == [("invalid", problem)]

    def test_an_existing_service_keeps_its_pricing_model_and_unit(self, ctx: Business) -> None:
        priced("duvet", "Duvets", "per_item", "item", "450.00")
        assert statuses(HEADER + "Duvets,Special,per_kg,450,\n") == [
            ("invalid", "pricing_model_differs")
        ]
        text = "service,category,pricing_model,price,unit\nDuvets,Special,per_item,450,pair\n"
        assert statuses(text) == [("invalid", "unit_differs")]

    def test_a_unit_that_does_not_fit(self, ctx: Business) -> None:
        text = "service,category,pricing_model,price,unit\nShoes,Special,per_kg,300,pair\n"
        assert statuses(text) == [("invalid", "unit_mismatch")]

    def test_a_service_twice_in_one_file(self, ctx: Business) -> None:
        text = HEADER + "Shoes,Special,per_item,300,\nshoes,Special,per_item,350,\n"
        assert statuses(text) == [("new", ""), ("invalid", "duplicate_row")]

    def test_a_name_shared_by_two_services_needs_the_code(self, ctx: Business) -> None:
        priced("suit-2pc", "Suits", "per_item", "item", "800.00")
        priced("suit-3pc", "Suits", "per_item", "item", "1000.00")
        assert statuses(HEADER + "Suits,Special,per_item,900,\n") == [
            ("invalid", "ambiguous_service")
        ]
        assert statuses(HEADER + "suit-3pc,Special,per_item,900,\n") == [("changed", "")]

    def test_new_codes_never_clash(self, ctx: Business) -> None:
        priced("shoes", "Old shoes", "per_item", "pair", "300.00")
        rows = preview(HEADER + "Shoes!,Special,per_item,300,\n").rows
        assert rows[0].new_code == "shoes-2"

    def test_another_business_services_are_unknown(
        self, business_a: Business, business_b: Business
    ) -> None:
        with time_machine.travel(NOW, tick=False):
            with tenant_context(business_b.id):
                priced("duvet", "Duvets", "per_item", "item", "450.00")
            with tenant_context(business_a.id):
                assert statuses(HEADER + "Duvets,Special,per_item,450,\n") == [("new", "")]


@pytest.mark.django_db
class TestApply:
    def test_applies_everything_as_new_versions(self, ctx: Business) -> None:
        wash = priced("wash-fold", "Wash and fold", "per_kg", "kg", "120.00", "500.00")
        text = HEADER + "Wash and fold,Wash,per_kg,130,550\nCurtains,Home,per_item,600,\n"
        later = NOW + timedelta(days=7)
        imports.apply(text, fingerprint=preview(text).fingerprint, effective_from=later)

        today = selectors.price_at(wash.pk)
        assert today is not None
        assert today.unit_price == Decimal("120.00")  # still today
        new_wash = selectors.price_at(wash.pk, at=later)
        assert new_wash is not None
        assert (new_wash.unit_price, new_wash.minimum_charge) == (
            Decimal("130.00"),
            Decimal("550.00"),
        )
        curtains = Service.objects.get(code="curtains")
        assert curtains.is_active is False  # never on sale unseen
        assert curtains.category.name_en == "Home"
        assert AuditLog.objects.filter(action="catalog.import.apply").count() == 1

    def test_unchanged_rows_create_no_version(self, ctx: Business) -> None:
        priced("duvet", "Duvets", "per_item", "item", "450.00")
        text = HEADER + "Duvets,Special,per_item,450,\n"
        imports.apply(text, fingerprint=preview(text).fingerprint)
        assert ServicePrice.objects.count() == 1

    def test_a_catalogue_change_since_the_preview_stops_it(self, ctx: Business) -> None:
        duvet = priced("duvet", "Duvets", "per_item", "item", "450.00")
        text = HEADER + "Duvets,Special,per_item,500,\n"
        fingerprint = preview(text).fingerprint
        services.set_price(
            duvet, unit_price=Decimal("480.00"), effective_from=NOW + timedelta(hours=1)
        )
        later = time_machine.travel(NOW + timedelta(hours=2), tick=False)
        with later, pytest.raises(CatalogImportError) as error:
            imports.apply(text, fingerprint=fingerprint)
        assert error.value.code == "changed_since_preview"

    def test_invalid_rows_stop_it(self, ctx: Business) -> None:
        text = HEADER + "Shoes,Special,per_item,300,\nIroning,Special,hourly,50,\n"
        with pytest.raises(CatalogImportError) as error:
            imports.apply(text, fingerprint=preview(text).fingerprint)
        assert (error.value.code, error.value.detail) == ("has_invalid_rows", {"count": 1})
        assert not Service.objects.exists()

    def test_all_or_nothing(self, ctx: Business) -> None:
        text = HEADER + "Shoes,Special,per_item,300,\nCurtains,Home,per_item,600,\n"
        fingerprint = preview(text).fingerprint
        with pytest.raises(CatalogError):
            # A start in the past fails on the first price: nothing may be left behind.
            imports.apply(text, fingerprint=fingerprint, effective_from=NOW - timedelta(days=1))
        assert not Service.objects.exists()
        assert not ServiceCategory.objects.exists()


@pytest.mark.django_db
def test_the_template_is_the_current_price_list(ctx: Business) -> None:
    priced("wash-fold", "Wash and fold", "per_kg", "kg", "120.00", "500.00")
    priced("duvet", "Duvets", "per_item", "item", "450.00")
    lines = imports.template_csv().splitlines()
    assert lines[0] == "service,category,pricing_model,price,minimum,unit"
    assert "Wash and fold,Wash,per_kg,120.00,500.00,kg" in lines
    assert "Duvets,Wash,per_item,450.00,,item" in lines
    # Importing the template unchanged changes nothing.
    assert {row.status for row in preview(imports.template_csv()).rows} == {"unchanged"}
