"""X-10 log in, refresh, log out and /me (M1 T05b, ADR-0002 section 3)."""

from datetime import timedelta
from typing import Any

import pytest
import time_machine
from django.utils import timezone

from apps.accounts.api.cookies import REFRESH_COOKIE
from apps.accounts.models import User, UserSession
from apps.accounts.tests.factories import TEST_PASSWORD, UserFactory
from apps.accounts.tests.helpers import assert_cross_business_token_rejected, client_for, sign_in
from apps.branches.models import Branch
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business, BusinessBranding

pytestmark = pytest.mark.django_db

PHONE = "+254712345678"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/me"
WRONG = "Phone number or password is incorrect"


@pytest.fixture
def user(business_a: Business) -> User:
    with tenant_context(business_a.id):
        created: User = UserFactory(phone=PHONE, first_name="Wanjiru", last_name="Kamau")
    return created


def login(business: Business, phone: str = "0712 345 678", password: str = TEST_PASSWORD) -> Any:
    return client_for(business).post(LOGIN, {"phone": phone, "password": password}, format="json")


def sessions(business: Business) -> list[UserSession]:
    with tenant_context(business.id):
        return list(UserSession.objects.order_by("created_at"))


class TestLogin:
    def test_success_returns_an_access_token_and_sets_the_refresh_cookie(
        self, business_a: Business, user: User
    ) -> None:
        response = login(business_a)
        assert response.status_code == 200
        body = response.json()
        assert body["access"]
        assert body["user"]["id"] == str(user.pk)
        assert body["user"]["rights"] == {
            "accept_cash": False,
            "give_discounts": False,
            "correct_prices": False,
        }
        assert body["user"]["has_pin"] is False
        cookie = response.cookies[REFRESH_COOKIE]
        assert cookie["httponly"]
        assert cookie["secure"]
        assert cookie["samesite"] == "Strict"
        assert cookie["path"] == "/api/v1/auth"
        assert not cookie["domain"]
        assert cookie["max-age"] == 7 * 24 * 3600

    def test_success_creates_a_session_and_audit_row(
        self, business_a: Business, user: User
    ) -> None:
        login(business_a)
        [session] = sessions(business_a)
        assert session.user_id == user.pk
        assert session.kind == UserSession.Kind.PASSWORD
        assert session.expires_at > timezone.now() + timedelta(days=6)
        with tenant_context(business_a.id):
            assert AuditLog.objects.filter(action="auth.login", actor=user).exists()
            user.refresh_from_db()
        assert user.last_login is not None

    @pytest.mark.parametrize("phone", ["0712345678", "712345678", "+254712345678", "254712345678"])
    def test_any_phone_form_works(self, business_a: Business, user: User, phone: str) -> None:
        assert login(business_a, phone=phone).status_code == 200

    @pytest.mark.parametrize(
        ("phone", "password"),
        [(PHONE, "wrong-password"), ("0799999999", TEST_PASSWORD), ("not a phone", "x")],
    )
    def test_failures_never_say_which_part_was_wrong(
        self, business_a: Business, user: User, phone: str, password: str
    ) -> None:
        response = login(business_a, phone=phone, password=password)
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_credentials"
        assert response.json()["message"] == WRONG
        assert REFRESH_COOKIE not in response.cookies
        assert sessions(business_a) == []

    def test_missing_fields_are_a_validation_error(self, business_a: Business) -> None:
        response = client_for(business_a).post(LOGIN, {"phone": ""}, format="json")
        assert response.status_code == 400
        assert response.json()["code"] == "validation_error"
        assert set(response.json()["fields"]) == {"phone", "password"}

    def test_suspension_is_only_revealed_after_a_correct_password(
        self, business_a: Business, user: User
    ) -> None:
        with tenant_context(business_a.id):
            User.objects.filter(pk=user.pk).update(status=User.Status.SUSPENDED)
            BusinessBranding.objects.create(app_name="Mama Safi", support_phone="+254700111222")
        assert login(business_a, password="wrong-password").json()["message"] == WRONG
        response = login(business_a)
        assert response.status_code == 403
        assert response.json()["code"] == "account_suspended"
        assert response.json()["message"] == (
            "Your account is suspended. Contact Mama Safi on 0700 111 222"
        )

    def test_an_account_in_another_business_does_not_sign_in_here(
        self, business_b: Business, user: User
    ) -> None:
        assert login(business_b).json()["code"] == "invalid_credentials"

    def test_attempts_are_throttled_per_phone_within_a_business(
        self, business_a: Business, business_b: Business, user: User
    ) -> None:
        for _ in range(10):
            assert login(business_a, password="wrong-password").status_code == 400
        response = login(business_a)
        assert response.status_code == 429
        assert response.json()["code"] == "throttled"
        assert response.json()["retry_after"] > 0
        # Another business's counter is separate.
        assert login(business_b, password="wrong-password").status_code == 400


class TestRefresh:
    def test_rotates_the_cookie_and_returns_a_new_access_token(
        self, business_a: Business, user: User
    ) -> None:
        signed_in = sign_in(user)
        client = client_for(business_a)
        client.cookies[REFRESH_COOKIE] = signed_in.refresh
        response = client.post(REFRESH)
        assert response.status_code == 200
        assert response.json()["access"]
        new_cookie = response.cookies[REFRESH_COOKIE].value
        assert new_cookie != signed_in.refresh
        me = client_for(business_a, response.json()["access"]).get(ME)
        assert me.status_code == 200

    def test_reusing_an_old_refresh_token_signs_the_session_out(
        self, business_a: Business, user: User
    ) -> None:
        signed_in = sign_in(user)
        first = client_for(business_a)
        first.cookies[REFRESH_COOKIE] = signed_in.refresh
        assert first.post(REFRESH).status_code == 200

        thief = client_for(business_a)
        thief.cookies[REFRESH_COOKIE] = signed_in.refresh
        response = thief.post(REFRESH)
        assert response.status_code == 401
        assert response.json()["code"] == "session_expired"
        [session] = sessions(business_a)
        assert session.revoke_reason == "refresh_reuse"  # kept, though the response was an error
        assert client_for(business_a, signed_in.access).get(ME).status_code == 401

    @pytest.mark.parametrize("cookie", [None, "", "made-up-token"])
    def test_missing_or_unknown_cookie(self, business_a: Business, cookie: str | None) -> None:
        client = client_for(business_a)
        if cookie is not None:
            client.cookies[REFRESH_COOKIE] = cookie
        response = client.post(REFRESH)
        assert response.status_code == 401
        assert response.cookies[REFRESH_COOKIE].value == ""

    def test_expired_session(self, business_a: Business, user: User) -> None:
        signed_in = sign_in(user)
        client = client_for(business_a)
        client.cookies[REFRESH_COOKIE] = signed_in.refresh
        with time_machine.travel(timezone.now() + timedelta(days=7, minutes=1)):
            assert client.post(REFRESH).status_code == 401

    def test_deactivated_person(self, business_a: Business, user: User) -> None:
        signed_in = sign_in(user)
        with tenant_context(business_a.id):
            User.objects.filter(pk=user.pk).update(status=User.Status.DEACTIVATED)
        client = client_for(business_a)
        client.cookies[REFRESH_COOKIE] = signed_in.refresh
        assert client.post(REFRESH).status_code == 401

    def test_a_refresh_cookie_from_another_business_is_unknown_here(
        self, business_b: Business, user: User
    ) -> None:
        client = client_for(business_b)
        client.cookies[REFRESH_COOKIE] = sign_in(user).refresh
        assert client.post(REFRESH).status_code == 401


class TestAccessTokens:
    def test_me(self, business_a: Business, user: User) -> None:
        response = client_for(business_a, sign_in(user).access).get(ME)
        assert response.status_code == 200
        assert response.json()["phone"] == PHONE

    def test_no_token(self, business_a: Business) -> None:
        response = client_for(business_a).get(ME)
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"
        assert response["WWW-Authenticate"].startswith("Bearer")

    @pytest.mark.parametrize(
        "header", ["Bearer", "Bearer not.a.jwt", "Bearer a b", "Basic abc", "Bearer \xe9"]
    )
    def test_malformed_tokens(self, business_a: Business, header: str) -> None:
        client = client_for(business_a)
        client.credentials(HTTP_AUTHORIZATION=header)
        assert client.get(ME).status_code == 401

    def test_access_tokens_expire_after_15_minutes(self, business_a: Business, user: User) -> None:
        access = sign_in(user).access
        with time_machine.travel(timezone.now() + timedelta(minutes=16)):
            assert client_for(business_a, access).get(ME).status_code == 401

    def test_signing_out_a_session_stops_its_token_at_once(
        self, business_a: Business, user: User
    ) -> None:
        signed_in = sign_in(user)
        with tenant_context(business_a.id):
            UserSession.objects.filter(pk=signed_in.session.pk).update(revoked_at=timezone.now())
        assert client_for(business_a, signed_in.access).get(ME).status_code == 401

    def test_last_seen_is_updated_at_most_once_a_minute(
        self, business_a: Business, user: User
    ) -> None:
        signed_in = sign_in(user)
        client = client_for(business_a, signed_in.access)
        client.get(ME)
        first = sessions(business_a)[0].last_seen_at
        with time_machine.travel(timezone.now() + timedelta(minutes=2)):
            client.get(ME)
        assert sessions(business_a)[0].last_seen_at > first

    def test_cross_business_token_is_rejected(self, business_b: Business, user: User) -> None:
        assert_cross_business_token_rejected(user=user, other=business_b, url=ME)
        assert_cross_business_token_rejected(user=user, other=business_b, url="/api/v1/me/branches")


class TestLogout:
    def test_with_the_access_token(self, business_a: Business, user: User) -> None:
        signed_in = sign_in(user)
        response = client_for(business_a, signed_in.access).post(LOGOUT)
        assert response.status_code == 204
        assert response.cookies[REFRESH_COOKIE].value == ""
        [session] = sessions(business_a)
        assert session.revoke_reason == "logout"
        assert client_for(business_a, signed_in.access).get(ME).status_code == 401

    def test_with_only_the_refresh_cookie(self, business_a: Business, user: User) -> None:
        signed_in = sign_in(user)
        client = client_for(business_a)
        client.cookies[REFRESH_COOKIE] = signed_in.refresh
        assert client.post(LOGOUT).status_code == 204
        assert sessions(business_a)[0].revoked_at is not None

    def test_with_nothing_is_harmless(self, business_a: Business) -> None:
        assert client_for(business_a).post(LOGOUT).status_code == 204


class TestMyBranches:
    def test_lists_active_branches_the_person_works_at(
        self, business_a: Business, user: User
    ) -> None:
        with tenant_context(business_a.id):
            kilimani = BranchFactory(name="Kilimani")
            BranchMemberFactory(branch=kilimani, user=user)
            closed = BranchFactory(name="Closed", status=Branch.Status.CLOSED)
            BranchMemberFactory(branch=closed, user=user)
            BranchFactory(name="Not mine")
        response = client_for(business_a, sign_in(user).access).get("/api/v1/me/branches")
        assert response.json() == [{"id": str(kilimani.pk), "name": "Kilimani"}]
