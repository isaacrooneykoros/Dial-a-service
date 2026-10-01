"""Minimal branches and membership (M1 T05a; full branch details arrive with A-40 in M5)."""

import pytest
from django.db import IntegrityError, transaction

from apps.branches.models import Branch, BranchMember
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.tenant_context import tenant_context
from apps.tenancy.tests.factories import BusinessFactory

pytestmark = pytest.mark.django_db


def test_branch_defaults_and_names() -> None:
    business = BusinessFactory()
    with tenant_context(business.id):
        branch = BranchFactory(name="Kilimani")
        member = BranchMemberFactory(branch=branch)
    assert branch.status == Branch.Status.ACTIVE
    assert str(branch) == "Kilimani"
    assert str(member) == f"{member.user_id} @ {branch.pk}"


def test_branch_names_are_unique_per_business() -> None:
    a, b = BusinessFactory(), BusinessFactory()
    with tenant_context(a.id):
        BranchFactory(name="Main")
        with pytest.raises(IntegrityError), transaction.atomic():
            BranchFactory(name="Main")
    with tenant_context(b.id):
        BranchFactory(name="Main")


def test_a_person_is_a_member_of_a_branch_once() -> None:
    business = BusinessFactory()
    with tenant_context(business.id):
        member = BranchMemberFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            BranchMember.objects.create(branch=member.branch, user=member.user)
