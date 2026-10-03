"""The pricing engine (M2 T03). Every expected value here is worked out by hand.

Owner decisions: D-53 VAT, D-54 modifiers, D-55 what a modifier applies to,
D-56 discounts. No database: pricing.py is pure.
"""

from decimal import Decimal

import pytest

from apps.catalog.pricing import (
    DiscountInput,
    LineInput,
    ModifierSnapshot,
    PriceSnapshot,
    PricingError,
    VatInput,
    quote,
    to_cents,
    to_shillings,
)

D = Decimal  # short, so the worked examples read like a receipt

NO_VAT = VatInput(registered=False)
VAT_INCLUDED = VatInput(registered=True, rate=D("16"), prices_include_vat=True)
VAT_ADDED = VatInput(registered=True, rate=D("16"), prices_include_vat=False)

WASH_FOLD = PriceSnapshot("wash-fold", "p-wf", "per_kg", "kg", D("120.00"), D("500.00"))
WASH_IRON = PriceSnapshot("wash-iron", "p-wi", "per_kg", "kg", D("150.00"))
DUVET = PriceSnapshot("duvet", "p-du", "per_item", "item", D("450.00"))
SHOES = PriceSnapshot("shoes", "p-sh", "per_item", "pair", D("300.00"))
CURTAIN_SET = PriceSnapshot("curtains", "p-cu", "flat", "set", D("1200.00"))

EXPRESS_50 = ModifierSnapshot("express", percent=D("50"))
HYPO_10 = ModifierSnapshot("hypo", percent=D("10"))
EXPRESS_FLAT_200 = ModifierSnapshot("express-flat", amount=D("200.00"))


def kg(price: PriceSnapshot, weight: str) -> LineInput:
    return LineInput(price, D(weight))


def items(price: PriceSnapshot, count: int) -> LineInput:
    return LineInput(price, D(count))


class TestRounding:
    @pytest.mark.parametrize(
        ("value", "shillings"),
        [("1249.49", "1249"), ("1249.50", "1250"), ("1249.51", "1250"), ("0.50", "1"), ("0", "0")],
    )
    def test_half_up_to_the_shilling(self, value: str, shillings: str) -> None:
        assert to_shillings(D(value)) == D(shillings)

    @pytest.mark.parametrize(
        ("value", "cents"), [("777.5475", "777.55"), ("777.5449", "777.54"), ("0.005", "0.01")]
    )
    def test_half_up_to_the_cent(self, value: str, cents: str) -> None:
        assert to_cents(D(value)) == D(cents)


class TestLines:
    @pytest.mark.parametrize(
        ("weight", "base", "minimum_applied"),
        [
            ("6.40", "768.00", False),  # 6.4 x 120
            ("4.17", "500.40", False),  # just over the KSh 500 minimum
            ("4.16", "500.00", True),  # 499.20 -> the minimum
            ("1.00", "500.00", True),
            ("0.01", "500.00", True),
        ],
    )
    def test_per_kg_with_a_minimum_charge(
        self, weight: str, base: str, minimum_applied: bool
    ) -> None:
        line = quote([kg(WASH_FOLD, weight)], vat=NO_VAT).lines[0]
        assert line.base == D(base)
        assert line.amount == D(base)
        assert line.minimum_applied is minimum_applied

    def test_per_kg_amounts_are_rounded_to_the_cent(self) -> None:
        price = PriceSnapshot("x", "p-x", "per_kg", "kg", D("120.55"))
        line = quote([kg(price, "6.45")], vat=NO_VAT).lines[0]
        assert line.base == D("777.55")  # 6.45 x 120.55 = 777.5475

    def test_per_item(self) -> None:
        line = quote([items(DUVET, 3)], vat=NO_VAT).lines[0]
        assert (line.quantity, line.unit, line.amount) == (D("3"), "item", D("1350.00"))

    def test_flat(self) -> None:
        line = quote([items(CURTAIN_SET, 1)], vat=NO_VAT).lines[0]
        assert line.amount == D("1200.00")

    def test_a_mixed_order(self) -> None:
        result = quote([kg(WASH_FOLD, "6.40"), items(DUVET, 2), items(SHOES, 1)], vat=NO_VAT)
        assert [line.amount for line in result.lines] == [D("768.00"), D("900.00"), D("300.00")]
        assert result.subtotal == D("1968.00")
        assert result.total == D("1968")

    def test_each_line_names_the_price_version_it_used(self) -> None:
        result = quote([kg(WASH_FOLD, "5"), items(DUVET, 1)], vat=NO_VAT)
        assert [(line.service_id, line.price_id) for line in result.lines] == [
            ("wash-fold", "p-wf"),
            ("duvet", "p-du"),
        ]

    @pytest.mark.parametrize(
        ("line", "code"),
        [
            (kg(WASH_FOLD, "0"), "bad_quantity"),
            (kg(WASH_FOLD, "-1"), "bad_quantity"),
            (kg(WASH_FOLD, "6.405"), "bad_quantity"),  # 3 decimals
            (kg(WASH_FOLD, "1000"), "bad_quantity"),
            (LineInput(DUVET, D("1.5")), "bad_quantity"),
            (items(DUVET, 0), "bad_quantity"),
            (items(DUVET, 10000), "bad_quantity"),
            (items(CURTAIN_SET, 2), "bad_quantity"),
        ],
    )
    def test_bad_quantities(self, line: LineInput, code: str) -> None:
        with pytest.raises(PricingError) as error:
            quote([line], vat=NO_VAT)
        assert error.value.code == code

    def test_no_lines(self) -> None:
        with pytest.raises(PricingError) as error:
            quote([], vat=NO_VAT)
        assert error.value.code == "no_lines"


class TestModifiers:
    def test_a_percentage_applies_per_line(self) -> None:
        result = quote([kg(WASH_FOLD, "6.40")], modifiers=[EXPRESS_50], vat=NO_VAT)
        line = result.lines[0]
        assert (line.base, line.modifier_percent, line.modifier_amount, line.amount) == (
            D("768.00"),
            D("50"),
            D("384.00"),
            D("1152.00"),
        )
        assert line.modifier_ids == ("express",)

    def test_percentages_add_up_not_compound(self) -> None:
        # D-54: 50% + 10% = +60% (compounding would be +65%).
        line = quote([items(DUVET, 1)], modifiers=[EXPRESS_50, HYPO_10], vat=NO_VAT).lines[0]
        assert line.modifier_percent == D("60")
        assert line.amount == D("720.00")  # 450 x 1.6

    def test_percentages_apply_to_the_minimum_charge(self) -> None:
        line = quote([kg(WASH_FOLD, "2")], modifiers=[EXPRESS_50], vat=NO_VAT).lines[0]
        assert line.minimum_applied
        assert line.amount == D("750.00")  # max(500, 240) x 1.5

    def test_a_flat_amount_is_added_once_per_order(self) -> None:
        # D-54: Express +KSh 200 once, however many lines.
        result = quote(
            [kg(WASH_FOLD, "6.40"), items(DUVET, 2)], modifiers=[EXPRESS_FLAT_200], vat=NO_VAT
        )
        assert [line.amount for line in result.lines] == [D("768.00"), D("900.00")]
        assert [(f.modifier_id, f.amount) for f in result.flat_modifiers] == [
            ("express-flat", D("200.00"))
        ]
        assert result.laundry_total == D("1868.00")

    def test_a_modifier_for_chosen_services_only(self) -> None:
        # D-55: hypoallergenic only on wash and fold.
        hypo = ModifierSnapshot("hypo", percent=D("10"), service_ids=frozenset({"wash-fold"}))
        result = quote([kg(WASH_FOLD, "6.40"), items(DUVET, 1)], modifiers=[hypo], vat=NO_VAT)
        assert [line.amount for line in result.lines] == [D("844.80"), D("450.00")]
        assert result.lines[1].modifier_ids == ()

    def test_a_flat_modifier_with_no_matching_line_is_not_charged(self) -> None:
        shoes_only = ModifierSnapshot("rush", amount=D("100.00"), service_ids=frozenset({"shoes"}))
        result = quote([items(DUVET, 1)], modifiers=[shoes_only], vat=NO_VAT)
        assert result.flat_modifiers == ()
        assert result.modifiers_not_applied == ("rush",)
        assert result.total == D("450")

    def test_a_percentage_with_no_matching_line_is_reported(self) -> None:
        shoes_only = ModifierSnapshot("rush", percent=D("20"), service_ids=frozenset({"shoes"}))
        result = quote([items(DUVET, 1)], modifiers=[shoes_only], vat=NO_VAT)
        assert result.modifiers_not_applied == ("rush",)
        assert result.total == D("450")

    @pytest.mark.parametrize(
        "modifier",
        [
            ModifierSnapshot("m", percent=D("10"), amount=D("10.00")),
            ModifierSnapshot("m"),
            ModifierSnapshot("m", percent=D("0")),
            ModifierSnapshot("m", amount=D("-5.00")),
        ],
    )
    def test_bad_modifiers(self, modifier: ModifierSnapshot) -> None:
        with pytest.raises(PricingError) as error:
            quote([items(DUVET, 1)], modifiers=[modifier], vat=NO_VAT)
        assert error.value.code == "bad_modifier"

    def test_a_modifier_once(self) -> None:
        with pytest.raises(PricingError) as error:
            quote([items(DUVET, 1)], modifiers=[EXPRESS_50, EXPRESS_50], vat=NO_VAT)
        assert error.value.code == "duplicate_modifier"


class TestDiscounts:
    def cap(self, max_percent: str, **kwargs: D) -> DiscountInput:
        return DiscountInput(max_percent=D(max_percent), **kwargs)

    def test_a_percentage_of_the_laundry_total_after_modifiers(self) -> None:
        # D-56: 10% off (768 x 1.5 = 1152) = 115.20
        result = quote(
            [kg(WASH_FOLD, "6.40")],
            modifiers=[EXPRESS_50],
            discount=self.cap("15", percent=D("10")),
            vat=NO_VAT,
        )
        assert result.discount == D("115.20")
        assert result.total == D("1037")  # 1036.80

    def test_flat_modifiers_are_part_of_what_is_discounted(self) -> None:
        result = quote(
            [items(DUVET, 2)],
            modifiers=[EXPRESS_FLAT_200],
            discount=self.cap("10", percent=D("10")),
            vat=NO_VAT,
        )
        assert result.discount == D("110.00")  # 10% of (900 + 200)

    def test_an_amount(self) -> None:
        result = quote([items(DUVET, 2)], discount=self.cap("20", amount=D("150.00")), vat=NO_VAT)
        assert (result.discount, result.total) == (D("150.00"), D("750"))

    @pytest.mark.parametrize(
        ("max_percent", "discount", "allowed"),
        [
            ("10", {"percent": D("10")}, True),  # exactly the cap
            ("10", {"percent": D("10.01")}, False),
            ("10", {"amount": D("90.00")}, True),  # 10% of 900
            ("10", {"amount": D("90.01")}, False),
            ("0", {"percent": D("1")}, False),  # D-56: no discounts until a cap is set
            ("0", {"amount": D("0.01")}, False),
            ("100", {"percent": D("100")}, True),
            ("100", {"amount": D("900.01")}, False),  # never below zero
        ],
    )
    def test_the_cap(self, max_percent: str, discount: dict[str, D], allowed: bool) -> None:
        def run() -> object:
            return quote([items(DUVET, 2)], discount=self.cap(max_percent, **discount), vat=NO_VAT)

        if allowed:
            assert run().total >= 0  # type: ignore[attr-defined]
        else:
            with pytest.raises(PricingError) as error:
                run()
            assert error.value.code == "discount_over_cap"

    def test_a_full_discount_is_free_not_negative(self) -> None:
        result = quote([items(DUVET, 2)], discount=self.cap("100", percent=D("100")), vat=NO_VAT)
        assert (result.discount, result.total) == (D("900.00"), D("0"))

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"percent": D("10"), "amount": D("10.00")},
            {},
            {"percent": D("0")},
            {"amount": D("0.00")},
            {"amount": D("10.005")},
        ],
    )
    def test_bad_discounts(self, kwargs: dict[str, D]) -> None:
        with pytest.raises(PricingError) as error:
            quote([items(DUVET, 2)], discount=self.cap("50", **kwargs), vat=NO_VAT)
        assert error.value.code == "bad_discount"


class TestVat:
    def test_not_registered_means_no_vat_line(self) -> None:
        result = quote([items(DUVET, 2)], vat=NO_VAT)
        assert (result.vat_registered, result.vat, result.vat_rate) == (False, D("0"), D("0"))
        assert result.total == D("900")

    def test_prices_including_vat_show_of_which_vat(self) -> None:
        # D-53: 900 includes VAT; of which 900 x 16/116 = 124.137... -> 124.14
        result = quote([items(DUVET, 2)], vat=VAT_INCLUDED)
        assert (result.vat_included, result.vat, result.total) == (True, D("124.14"), D("900"))

    def test_prices_excluding_vat_add_it_on_top(self) -> None:
        # D-53: 900 + 16% = 900 + 144 = 1044
        result = quote([items(DUVET, 2)], vat=VAT_ADDED)
        assert (result.vat_included, result.vat, result.total) == (False, D("144.00"), D("1044"))

    def test_vat_comes_after_the_discount(self) -> None:
        # D-53: (900 - 90) x 16% = 129.60; total 939.60 -> 940
        result = quote(
            [items(DUVET, 2)],
            discount=DiscountInput(max_percent=D("10"), percent=D("10")),
            vat=VAT_ADDED,
        )
        assert result.taxable == D("810.00")
        assert result.vat == D("129.60")
        assert (result.total_unrounded, result.total, result.rounding) == (
            D("939.60"),
            D("940"),
            D("0.40"),
        )

    def test_included_vat_is_taken_from_the_rounded_total_paid(self) -> None:
        # 6.45 kg x 120.55 = 777.55 -> pays 778; of which 778 x 16/116 = 107.31
        price = PriceSnapshot("x", "p-x", "per_kg", "kg", D("120.55"))
        result = quote([kg(price, "6.45")], vat=VAT_INCLUDED)
        assert (result.total, result.vat, result.rounding) == (D("778"), D("107.31"), D("0.45"))

    def test_the_delivery_fee_is_taxable(self) -> None:
        # From M9: (900 + 150) x 16% = 168
        result = quote([items(DUVET, 2)], vat=VAT_ADDED, delivery_fee=D("150.00"))
        assert (result.taxable, result.vat, result.total) == (D("1050.00"), D("168.00"), D("1218"))

    def test_a_zero_rate(self) -> None:
        result = quote([items(DUVET, 2)], vat=VatInput(registered=True, rate=D("0")))
        assert (result.vat, result.total) == (D("0.00"), D("900"))

    @pytest.mark.parametrize("rate", ["-1", "100.01"])
    def test_bad_rates(self, rate: str) -> None:
        with pytest.raises(PricingError) as error:
            quote([items(DUVET, 1)], vat=VatInput(registered=True, rate=D(rate)))
        assert error.value.code == "bad_vat_rate"


class TestTotals:
    @pytest.mark.parametrize(
        ("price", "weight", "total", "rounding"),
        [
            ("100.49", "1", "100", "-0.49"),
            ("100.50", "1", "101", "0.50"),  # half-up
            ("100.51", "1", "101", "0.49"),
        ],
    )
    def test_the_total_is_whole_shillings_half_up(
        self, price: str, weight: str, total: str, rounding: str
    ) -> None:
        snapshot = PriceSnapshot("x", "p-x", "per_kg", "kg", D(price))
        result = quote([kg(snapshot, weight)], vat=NO_VAT)
        assert (result.total, result.rounding) == (D(total), D(rounding))
        assert result.total_unrounded == D(price)

    def test_a_full_counter_order(self) -> None:
        """6.4 kg wash and fold + 2 duvets + 1 pair of shoes, Express 50% on the wash only,
        hypoallergenic +KSh 100 once, 5% off (cap 10%), VAT 16% added on top.

        Lines:   wash 768.00 x 1.5 = 1152.00; duvets 900.00; shoes 300.00 -> 2352.00
        Flat:    + 100.00 -> laundry total 2452.00
        Discount 5% = 122.60 -> taxable 2329.40
        VAT      16% = 372.704 -> 372.70 -> 2702.10 -> KSh 2702
        """
        express_wash = ModifierSnapshot(
            "express", percent=D("50"), service_ids=frozenset({"wash-fold"})
        )
        hypo_flat = ModifierSnapshot("hypo", amount=D("100.00"))
        result = quote(
            [kg(WASH_FOLD, "6.40"), items(DUVET, 2), items(SHOES, 1)],
            modifiers=[express_wash, hypo_flat],
            discount=DiscountInput(max_percent=D("10"), percent=D("5")),
            vat=VAT_ADDED,
        )
        assert [line.amount for line in result.lines] == [D("1152.00"), D("900.00"), D("300.00")]
        assert result.subtotal == D("2352.00")
        assert result.laundry_total == D("2452.00")
        assert result.discount == D("122.60")
        assert result.taxable == D("2329.40")
        assert result.vat == D("372.70")
        assert result.total_unrounded == D("2702.10")
        assert result.total == D("2702")
        assert result.rounding == D("-0.10")

    def test_every_amount_is_a_decimal(self) -> None:
        result = quote([kg(WASH_FOLD, "6.40")], modifiers=[EXPRESS_FLAT_200], vat=VAT_ADDED)
        for value in (result.subtotal, result.vat, result.total, result.lines[0].amount):
            assert isinstance(value, D)

    @pytest.mark.parametrize("fee", ["-1.00", "10.005"])
    def test_bad_delivery_fees(self, fee: str) -> None:
        with pytest.raises(PricingError) as error:
            quote([items(DUVET, 1)], vat=NO_VAT, delivery_fee=D(fee))
        assert error.value.code == "bad_delivery_fee"

    def test_one_currency(self) -> None:
        ugx = PriceSnapshot("x", "p-x", "per_item", "item", D("100.00"), currency="UGX")
        with pytest.raises(PricingError) as error:
            quote([items(ugx, 1)], vat=NO_VAT)
        assert error.value.code == "currency_mismatch"
