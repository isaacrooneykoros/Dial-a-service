"""Factories for branches. Call inside tenant_context()."""

import factory

from apps.accounts.tests.factories import UserFactory
from apps.branches.models import Branch, BranchMember


class BranchFactory(factory.django.DjangoModelFactory[Branch]):
    class Meta:
        model = Branch

    name = factory.Sequence(lambda n: f"Branch {n}")


class BranchMemberFactory(factory.django.DjangoModelFactory[BranchMember]):
    class Meta:
        model = BranchMember

    branch = factory.SubFactory(BranchFactory)
    user = factory.SubFactory(UserFactory)
