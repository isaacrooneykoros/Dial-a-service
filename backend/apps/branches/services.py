"""Write operations for the branches app. Other apps call these, never the models directly."""

from collections.abc import Iterable
from typing import Any

from apps.branches.models import Branch, BranchMember


def add_member(user_id: Any, branches: Iterable[Branch]) -> None:
    """Make a person a member of each branch (skips existing memberships)."""
    for branch in branches:
        BranchMember.objects.get_or_create(branch=branch, user_id=user_id)
