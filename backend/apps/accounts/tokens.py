"""Access and refresh tokens (ADR-0002 section 3).

- Access token: a signed JWT (simplejwt), 15 minutes, carrying the user, the
  business and the session. Kept in memory by the apps.
- Refresh token: 256 random bits, not a JWT, stored only as a SHA-256 hash on
  the UserSession, sent in the httpOnly ``das_refresh`` cookie.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)  # design doc "Sign-in"
REFRESH_TOKEN_LIFETIME = timedelta(days=7)  # design doc "Sign-in"


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    business_id: UUID
    session_id: UUID


class InvalidAccessTokenError(Exception):
    """The access token is malformed, badly signed, expired or missing claims."""


def issue_access_token(*, user_id: UUID, business_id: UUID, session_id: UUID) -> str:
    token = AccessToken()
    token["user_id"] = str(user_id)
    token["business_id"] = str(business_id)
    token["session_id"] = str(session_id)
    return str(token)


def read_access_token(raw: str) -> AccessClaims:
    try:
        token = AccessToken(raw)  # type: ignore[arg-type]
        return AccessClaims(
            user_id=UUID(token["user_id"]),
            business_id=UUID(token["business_id"]),
            session_id=UUID(token["session_id"]),
        )
    except (TokenError, KeyError, ValueError, TypeError) as exc:
        raise InvalidAccessTokenError(str(exc)) from exc


def new_refresh_token() -> tuple[str, str]:
    """A new refresh token and the hash to store."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
