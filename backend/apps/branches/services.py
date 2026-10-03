"""Write operations for the branches app. Other apps call these, never the models directly."""

from collections.abc import Iterable
from typing import Any

from apps.branches.models import Branch, BranchMember


def add_member(user_id: Any, branches: Iterable[Branch]) -> None:
    """Make a person a member of each branch (skips existing memberships)."""
    for branch in branches:
        BranchMember.objects.get_or_create(branch=branch, user_id=user_id)


def create_branch(name: str) -> Branch:
    """A new active branch in the current business."""
    branch = Branch(name=name)
    branch.full_clean(exclude=["business"])
    branch.save()
    return branch


def get_or_create_branch(name: str) -> Branch:
    """The current business's branch with this name, created if missing (seed data)."""
    existing = Branch.objects.filter(name=name).first()
    return existing or create_branch(name)
