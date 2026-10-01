"""The httpOnly refresh-token cookie (ADR-0002 section 3).

HttpOnly (scripts can't read it), Secure (except local development), SameSite
Strict, limited to /api/v1/auth, and with no Domain attribute so it belongs to
one business's host only.
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponseBase

from apps.accounts.tokens import REFRESH_TOKEN_LIFETIME

REFRESH_COOKIE = "das_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: HttpResponseBase, raw: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=int(REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )


def clear_refresh_cookie(response: HttpResponseBase) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite="Strict")


def read_refresh_cookie(request: HttpRequest) -> str:
    return request.COOKIES.get(REFRESH_COOKIE, "")
