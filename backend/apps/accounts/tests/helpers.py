"""Signed-in test clients and the token half of the cross-business harness."""

from apps.accounts.models import User, UserSession
from apps.accounts.services.auth import SignedIn, _start_session
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import AppClient, host_of
from apps.tenancy.models import Business


def sign_in(user: User, kind: str = UserSession.Kind.PASSWORD) -> SignedIn:
    """A real session and tokens for ``user`` (as if they had logged in)."""
    with tenant_context(user.business_id):  # type: ignore[arg-type]
        return _start_session(user, None, kind)


def client_for(business: Business, access: str | None = None) -> AppClient:
    client = AppClient(headers={"host": host_of(business)}, raise_request_exception=False)
    if access:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def assert_cross_business_token_rejected(
    *, user: User, other: Business, url: str, method: str = "get"
) -> None:
    """A real token from ``user``'s business gets 401 on another business's host."""
    signed_in = sign_in(user)
    own = getattr(client_for(user.business, signed_in.access), method)(url)  # type: ignore[arg-type]
    assert own.status_code < 400, f"The token doesn't work on its own business ({own.status_code})."
    response = getattr(client_for(other, signed_in.access), method)(url)
    assert response.status_code == 401, (
        f"A token from another business was accepted: {method.upper()} {url} -> "
        f"{response.status_code}"
    )
    assert response.json()["code"] == "not_authenticated"
