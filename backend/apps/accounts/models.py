"""People who sign in (ADR-0002 section 1).

Accounts are per business: someone who uses two laundries has two accounts.
Platform staff (your team) have no business. Under row-level security their
rows are invisible to dial_app and visible only to the platform service
(dial_platform), so a business host can never see or sign in a platform user.
"""

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.core.tenant_context import TenantMismatch, get_current_business_id


class Role(models.TextChoices):
    OWNER = "owner", _("Owner")
    MANAGER = "manager", _("Manager")
    ACCOUNTANT = "accountant", _("Accountant")
    STAFF = "staff", _("Staff")
    RIDER = "rider", _("Rider")
    CUSTOMER = "customer", _("Customer")
    PLATFORM_SUPER_ADMIN = "platform_super_admin", _("Platform super admin")
    PLATFORM_SUPPORT = "platform_support", _("Platform support")
    PLATFORM_FINANCE = "platform_finance", _("Platform finance")


PLATFORM_ROLES = frozenset(
    {Role.PLATFORM_SUPER_ADMIN, Role.PLATFORM_SUPPORT, Role.PLATFORM_FINANCE}
)


class UserManager(BaseUserManager["User"]):
    """Scoped to the current business, like TenantManager (ADR-0001 section 3).

    Raises TenantContextMissing with no business in context. Platform staff are
    managed by the platform service through the unscoped manager (from M6).
    """

    def get_queryset(self) -> models.QuerySet["User"]:
        return super().get_queryset().filter(business_id=get_current_business_id())


class User(AbstractBaseUser):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        DEACTIVATED = "deactivated", _("Deactivated")

    class Language(models.TextChoices):
        ENGLISH = "en", _("English")
        SWAHILI = "sw", _("Kiswahili")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "tenancy.Business",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        related_name="+",
    )
    phone = models.CharField(max_length=16)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    role = models.CharField(max_length=24, choices=Role.choices)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)
    is_phone_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    # Personal 4-digit PIN for shared counter devices (X-15), stored hashed.
    pin_hash = models.CharField(max_length=128, blank=True, editable=False)
    pin_set_at = models.DateTimeField(null=True, blank=True, editable=False)

    # The three rights an owner switches per staff member (A-41). Stored now
    # because invitations carry them; enforced from M3 and M4.
    can_accept_cash = models.BooleanField(default=False)
    can_give_discounts = models.BooleanField(default=False)
    can_correct_prices = models.BooleanField(default=False)

    # Django admin access, for platform staff only (platform-admin service).
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ClassVar[UserManager] = UserManager()
    unscoped: ClassVar[models.Manager["User"]] = models.Manager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["first_name", "last_name"]

    class Meta:
        default_manager_name = "objects"
        base_manager_name = "unscoped"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "phone"],
                condition=models.Q(business__isnull=False),
                name="user_unique_phone_per_business",
            ),
            models.UniqueConstraint(
                fields=["phone"],
                condition=models.Q(business__isnull=True),
                name="platform_user_unique_phone",
            ),
            models.CheckConstraint(
                condition=models.Q(phone__regex=r"^\+254[17][0-9]{8}$"),
                name="user_phone_e164_ke_mobile",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role__in=sorted(PLATFORM_ROLES), business__isnull=True)
                    | (
                        ~models.Q(role__in=sorted(PLATFORM_ROLES))
                        & models.Q(business__isnull=False)
                    )
                ),
                name="user_platform_roles_have_no_business",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Any = None,
    ) -> None:
        if self.role not in PLATFORM_ROLES:
            self._assign_current_business()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.status == self.Status.ACTIVE

    @property
    def is_platform_staff(self) -> bool:
        return self.role in PLATFORM_ROLES

    def has_perm(self, perm: str, obj: object = None) -> bool:
        """Django admin access: platform super admins only, until P-11 (M6) adds more."""
        return self.is_active and self.is_staff and self.role == Role.PLATFORM_SUPER_ADMIN

    def has_module_perms(self, app_label: str) -> bool:
        return self.has_perm(app_label)

    def _assign_current_business(self) -> None:
        current = get_current_business_id()
        assigned = self.business_id
        if assigned is None:
            self.business_id = current
        elif assigned != current:
            raise TenantMismatch(
                f"User belongs to business {assigned}, but the current business is {current}."
            )


class UserSession(TenantModel):
    """One signed-in device or browser for one person (ADR-0002 section 3; A-42).

    The refresh token is random and stored only as a SHA-256 hash. It rotates on
    every use; presenting the previous one again (a sign of theft) revokes the
    session. Access tokens carry this session's ID and stop working the moment
    it is revoked.
    """

    class Kind(models.TextChoices):
        PASSWORD = "password", _("Password")
        PIN = "pin", _("PIN")

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.PASSWORD)
    user_agent = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=32, blank=True)
    refresh_hash = models.CharField(max_length=64, unique=True, editable=False)
    previous_refresh_hash = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["business", "user", "revoked_at"], name="session_user_active"),
            models.Index(fields=["previous_refresh_hash"], name="session_previous_refresh"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} session {self.pk}"

    @property
    def is_live(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
