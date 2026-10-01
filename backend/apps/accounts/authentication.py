"""Bearer-token authentication bound to the business and the session (ADR-0002 section 3).

A token is accepted only if:
- it is validly signed and unexpired,
- it was issued for the business this host belongs to (a mamasafi token is
  useless on cleanpro),
- its session hasn't been signed out or expired, and
- the person is still active.

The session check costs one indexed lookup per request and makes sign-out from
the console (A-42) and deactivation (A-41) take effect immediately.
"""

from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.models import User, UserSession
from apps.accounts.tokens import InvalidAccessTokenError, read_access_token

SEEN_UPDATE_INTERVAL = timedelta(minutes=1)


class SessionTokenAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[User, UserSession] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed()
        try:
            claims = read_access_token(parts[1].decode())
        except (InvalidAccessTokenError, UnicodeDecodeError) as exc:
            raise AuthenticationFailed() from exc

        business = getattr(request._request, "business", None)
        if business is None or claims.business_id != business.id:
            raise AuthenticationFailed()

        session = (
            UserSession.objects.select_related("user")
            .filter(pk=claims.session_id, user_id=claims.user_id)
            .first()
        )
        if session is None or not session.is_live or not session.user.is_active:
            raise AuthenticationFailed()

        now = timezone.now()
        if now - session.last_seen_at > SEEN_UPDATE_INTERVAL:
            session.last_seen_at = now
            session.save(update_fields=["last_seen_at"])
        return session.user, session

    def authenticate_header(self, request: Any) -> str:
        return 'Bearer realm="api"'
