"""Branches and who works at them (minimal for M1; full fields in M5, A-40).

M1 needs only enough for registered devices (S-02), the X-15 roster and
invitations. Address, hours, capacity and a branch's own Till come with A-40.
Users are referenced only through settings.AUTH_USER_MODEL, so this app never
imports apps.accounts (ADR-0001 section 8).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel


class Branch(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        CLOSED = "closed", _("Closed")

    name = models.CharField(max_length=120)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name_plural = "branches"
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="branch_unique_name"),
        ]

    def __str__(self) -> str:
        return self.name


class BranchMember(TenantModel):
    """A person who works at a branch. Unique per branch and user (data model)."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "branch", "user"], name="branch_member_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.branch_id}"
