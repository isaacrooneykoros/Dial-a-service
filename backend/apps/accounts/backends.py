"""Sign-in by phone and password within the current business (ADR-0002 section 1).

The same phone can have accounts in several businesses, so the business comes
from the request's host (the tenant context), never from the client.
"""

from typing import Any

from django.contrib.auth.backends import BaseBackend
from django.http import HttpRequest

from apps.accounts.models import User
from apps.accounts.phones import InvalidPhoneError, normalize_ke_phone
from apps.core.tenant_context import peek_current_business_id


class BusinessPhoneBackend(BaseBackend):
    def authenticate(
        self,
        request: HttpRequest | None,
        phone: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        """The user if the password is right, else None.

        Status (suspended, deactivated) is checked by the login service, which
        must only reveal it after a correct password (X-10).
        """
        if peek_current_business_id() is None or not phone or not password:
            return None
        try:
            user = User.objects.get(phone=normalize_ke_phone(phone))
        except (InvalidPhoneError, User.DoesNotExist):
            # Hash anyway, so a missing account takes as long as a wrong password.
            User().set_password(password)
            return None
        return user if user.check_password(password) else None

    def get_user(self, user_id: Any) -> User | None:
        if peek_current_business_id() is None:
            return None
        return User.objects.filter(pk=user_id).first()
