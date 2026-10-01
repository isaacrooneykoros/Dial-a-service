"""Businesses and their web addresses.

Both models are global (no business column, no RLS): the host lookup has to
find the business before any business is in context. They are listed in
apps/tenancy/registry.py.
"""

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenancy.validators import SLUG_MAX_LENGTH, validate_business_slug, validate_host


class Business(BaseModel):
    """A laundry renting the system (design doc "Data model", tenancy.Business).

    The SMS balance is deliberately not stored here: it is the sum of
    SmsTransaction rows (M6, OPEN.md D-33).
    """

    class Status(models.TextChoices):
        TRIAL = "trial", _("Trial")
        ACTIVE = "active", _("Active")
        READ_ONLY = "read_only", _("Read-only")
        SUSPENDED = "suspended", _("Suspended")
        CANCELLED = "cancelled", _("Cancelled")

    class Language(models.TextChoices):
        ENGLISH = "en", _("English")
        SWAHILI = "sw", _("Kiswahili")

    name = models.CharField(max_length=120)
    slug = models.CharField(
        max_length=SLUG_MAX_LENGTH, unique=True, validators=[validate_business_slug]
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    country = models.CharField(max_length=2, default="KE")
    currency = models.CharField(max_length=3, default="KES")
    timezone = models.CharField(max_length=64, default="Africa/Nairobi")
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)

    class Meta:
        verbose_name_plural = "businesses"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(slug__regex=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"),
                name="business_slug_format",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class BusinessDomain(BaseModel):
    """A host that serves one business, e.g. mamasafi.dialaservice.co.ke."""

    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="domains")
    host = models.CharField(max_length=253, unique=True, validators=[validate_host])
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business"],
                condition=models.Q(is_primary=True),
                name="one_primary_domain_per_business",
            ),
            models.CheckConstraint(
                condition=models.Q(host=Lower("host")), name="domain_host_lowercase"
            ),
        ]

    def __str__(self) -> str:
        return self.host
