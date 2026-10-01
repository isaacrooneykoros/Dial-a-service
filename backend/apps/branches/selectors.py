"""Read queries for the branches app. Other apps call these, never the models directly."""

from collections.abc import Iterable
from typing import Any

from apps.branches.models import Branch, BranchMember


def branches_for_user(user_id: Any) -> list[Branch]:
    """Active branches the person works at in the current business (S-01)."""
    branch_ids = BranchMember.objects.filter(user_id=user_id).values("branch_id")
    return list(
        Branch.objects.filter(pk__in=branch_ids, status=Branch.Status.ACTIVE).order_by("name")
    )


def branches_by_ids(branch_ids: Iterable[Any]) -> list[Branch]:
    """Active branches of the current business among ``branch_ids`` (unknown IDs are skipped)."""
    return list(Branch.objects.filter(pk__in=list(branch_ids), status=Branch.Status.ACTIVE))


def member_branch_ids(user_id: Any) -> set[Any]:
    return set(BranchMember.objects.filter(user_id=user_id).values_list("branch_id", flat=True))
