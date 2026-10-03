"""The price list: categories, services, versioned prices and modifiers (M2 T01).

Design doc "Pricing engine" and "Data model" (catalog); owner decisions D-53 to D-60.
Every price calculation lives in apps/catalog/pricing.py, never here (CLAUDE.md
section 6.2). Prices are versions with an effective period, so a change never
rewrites what past orders were charged.
"""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel

# Money: DecimalField(max_digits=12, decimal_places=2) plus a currency (CLAUDE.md 6.2).
DEFAULT_CURRENCY = "KES"
# Stands in for "no branch" so business-wide prices are checked against each other
# (NULL never equals NULL in the overlap constraint).
NO_BRANCH = "00000000-0000-0000-0000-000000000000"

service_code_validator = RegexValidator(
    r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$",
    _("Use lowercase letters, numbers and hyphens, like wash-fold."),
    code="invalid_code",
)


class TsTzRange(models.Func):
    """tstzrange(start, end, '[)'): valid from the start up to, not including, the end."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class ServiceCategory(TenantModel):
    """A group of services in the price list and the staff app ("Wash", "Special items")."""

    name_en = models.CharField(max_length=120)
    name_sw = models.CharField(max_length=120, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "service categories"
        ordering = ["position", "name_en"]
        constraints = [
            models.UniqueConstraint(fields=["business", "name_en"], name="category_unique_name"),
        ]

    def __str__(self) -> str:
        return self.name_en


class Service(TenantModel):
    """Something a business charges for: wash and fold per kg, a duvet per item..."""

    class PricingModel(models.TextChoices):
        PER_KG = "per_kg", _("Per kg")
        PER_ITEM = "per_item", _("Per item")
        FLAT = "flat", _("Flat")

    class Unit(models.TextChoices):
        # D-58: per kg always shows kg; per-item services use item, pair or set.
        KG = "kg", _("kg")
        ITEM = "item", _("item")
        PAIR = "pair", _("pair")
        SET = "set", _("set")

    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    code = models.CharField(max_length=32, validators=[service_code_validator])
    name_en = models.CharField(max_length=120)
    name_sw = models.CharField(max_length=120, blank=True)
    pricing_model = models.CharField(max_length=8, choices=PricingModel.choices)
    unit = models.CharField(max_length=4, choices=Unit.choices)
    # Order in the price list and the staff app's quick-add buttons (A-30, S-10).
    position = models.PositiveIntegerField(default=0)
    # Off until switched on (template services start off, D-57). Switching on
    # needs a current price (catalog services).
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "name_en"]
        constraints = [
            models.UniqueConstraint(fields=["business", "code"], name="service_unique_code"),
            # Per kg always uses kg; per item and flat never do.
            models.CheckConstraint(
                condition=(Q(pricing_model="per_kg") & Q(unit="kg"))
                | (~Q(pricing_model="per_kg") & ~Q(unit="kg")),
                name="service_unit_matches_pricing_model",
            ),
        ]

    def __str__(self) -> str:
        return self.name_en


class ServicePrice(TenantModel):
    """One version of a service's price, business-wide or for one branch.

    Valid from ``effective_from`` up to (not including) ``effective_to``; an open
    end means "until replaced". Versions of the same service and branch never
    overlap: the database refuses it.
    """

    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="prices")
    # A branch override; empty for the business-wide price.
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    # Per kg only: the least a line can cost (design doc pricing formula).
    minimum_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-effective_from"]
        indexes = [
            models.Index(
                fields=["business", "service", "effective_from"], name="price_service_from_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="price_unit_price_positive"),
            models.CheckConstraint(
                condition=Q(minimum_charge__gte=0), name="price_minimum_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=models.F("effective_from")),
                name="price_period_ends_after_it_starts",
            ),
            ExclusionConstraint(
                name="price_versions_never_overlap",
                expressions=[
                    ("business", RangeOperators.EQUAL),
                    ("service", RangeOperators.EQUAL),
                    (
                        Coalesce(
                            "branch", models.Value(NO_BRANCH, output_field=models.UUIDField())
                        ),
                        RangeOperators.EQUAL,
                    ),
                    (
                        TsTzRange(
                            "effective_from", "effective_to", RangeBoundary(inclusive_lower=True)
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_id} {self.unit_price} from {self.effective_from:%Y-%m-%d %H:%M}"


class PriceModifier(TenantModel):
    """An extra on a line: Express, or a chargeable preference such as hypoallergenic
    detergent. A percentage applies per line (percentages add up); a flat amount is
    added once per order (D-54). It applies to all services or to a chosen list (D-55)."""

    class Kind(models.TextChoices):
        EXPRESS = "express", _("Express")
        PREFERENCE = "preference", _("Preference")

    name_en = models.CharField(max_length=120)
    name_sw = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    applies_to_all = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "name_en"]
        constraints = [
            models.UniqueConstraint(fields=["business", "name_en"], name="modifier_unique_name"),
            # Exactly one of a percentage and an amount, and it is positive.
            models.CheckConstraint(
                condition=(Q(percent__isnull=False, percent__gt=0) & Q(amount__isnull=True))
                | (Q(amount__isnull=False, amount__gt=0) & Q(percent__isnull=True)),
                name="modifier_percent_or_amount",
            ),
        ]

    def __str__(self) -> str:
        return self.name_en


class PriceModifierService(TenantModel):
    """A service a modifier applies to, when it doesn't apply to all (D-55)."""

    modifier = models.ForeignKey(PriceModifier, on_delete=models.CASCADE, related_name="links")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "modifier", "service"], name="modifier_service_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.modifier_id} -> {self.service_id}"
