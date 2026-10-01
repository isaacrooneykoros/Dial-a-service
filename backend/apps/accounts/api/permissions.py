"""Role permissions (design doc "Roles, permissions and sign-in"). Never rely on the frontend."""

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.accounts.models import Role


class IsOwnerOrManager(BasePermission):
    """Team management (A-41: owner and manager; managers can't manage owners)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role in (Role.OWNER, Role.MANAGER))
