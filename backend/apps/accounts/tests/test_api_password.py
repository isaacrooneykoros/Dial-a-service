"""X-11 to X-13 forgot password, and password change (M1 T05c, ADR-0002 section 5)."""

import re
from collections.abc import Iterator
from typing import Any

import pytest

from apps.accounts.api.cookies import REFRESH_COOKIE
from apps.accounts.models import User, UserSession
from apps.accounts.tests.factories import TEST_PASSWORD, UserFactory
from apps.accounts.tests.helpers import assert_cross_business_token_rejected, client_for, sign_in
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.notifications.backends import LocmemSmsBackend
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

PHONE = "+254712345678"
REQUEST = "/api/v1/auth/password-reset/request"
VERIFY = "/api/v1/auth/password-reset/verify"
CONFIRM = "/api/v1/auth/password-reset/confirm"
CHANGE = "/api/v1/auth/password/change"
SENT = "If this number has an account, we've sent a code"
NEW_PASSWORD = "Ndizi-na-chai-77"


@pytest.fixture(autouse=True)
def sms() -> Iterator[list[Any]]:
    LocmemSmsBackend.outbox.clear()
    yield LocmemSmsBackend.outbox
    LocmemSmsBackend.outbox.clear()


@pytest.fixture
def user(business_a: Business) -> User:
    with tenant_context(business_a.id):
        created: User = UserFactory(phone=PHONE)
    return created


def post(business: Business, url: str, data: dict[str, Any], capture: Any = None) -> Any:
    if capture is None:
        return client_for(business).post(url, data, format="json")
    with capture(execute=True):
        return client_for(business).post(url, data, format="json")


def code_from(sms: list[Any]) -> str:
    match = re.match(r"^(\d{6}) is your ", sms[-1].text)
    assert match, sms
    return match[1]


def reset_token(business: Business, sms: list[Any], capture: Any) -> str:
    post(business, REQUEST, {"phone": "0712 345 678"}, capture)
    response = post(business, VERIFY, {"phone": "0712345678", "code": code_from(sms)})
    assert response.status_code == 200, response.json()
    token: str = response.json()["reset_token"]
    return token


class TestRequest:
    def test_known_number_gets_a_code(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        response = post(
            business_a, REQUEST, {"phone": "0712345678"}, django_capture_on_commit_callbacks
        )
        assert response.status_code == 200
        assert response.json() == {"message": SENT}
        assert len(sms) == 1

    def test_unknown_number_gets_the_same_answer_and_no_sms(
        self, business_a: Business, sms: list[Any], django_capture_on_commit_callbacks: Any
    ) -> None:
        response = post(
            business_a, REQUEST, {"phone": "0799999999"}, django_capture_on_commit_callbacks
        )
        assert response.status_code == 200
        assert response.json() == {"message": SENT}
        assert sms == []

    def test_suspended_accounts_get_no_code(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        with tenant_context(business_a.id):
            User.objects.filter(pk=user.pk).update(status=User.Status.SUSPENDED)
        assert post(
            business_a, REQUEST, {"phone": PHONE}, django_capture_on_commit_callbacks
        ).json() == {"message": SENT}
        assert sms == []

    def test_a_second_request_within_60_seconds_is_refused(
        self, business_a: Business, user: User, django_capture_on_commit_callbacks: Any
    ) -> None:
        post(business_a, REQUEST, {"phone": PHONE}, django_capture_on_commit_callbacks)
        response = post(business_a, REQUEST, {"phone": PHONE})
        assert response.status_code == 429
        assert response.json()["code"] == "throttled"
        assert response.json()["retry_after"] <= 60

    def test_invalid_phone(self, business_a: Business) -> None:
        response = post(business_a, REQUEST, {"phone": "0202345678"})
        assert response.status_code == 400
        assert response.json()["fields"]["phone"] == [
            "Enter a Kenyan mobile number, like 0712 345 678."
        ]

    def test_a_phone_registered_in_another_business_gets_nothing_here(
        self,
        business_b: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        response = post(business_b, REQUEST, {"phone": PHONE}, django_capture_on_commit_callbacks)
        assert response.json() == {"message": SENT}
        assert sms == []


class TestVerify:
    def test_wrong_code_counts_attempts(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        post(business_a, REQUEST, {"phone": PHONE}, django_capture_on_commit_callbacks)
        wrong = "000000" if code_from(sms) != "000000" else "111111"
        response = post(business_a, VERIFY, {"phone": PHONE, "code": wrong})
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_code"
        assert response.json()["attempts_left"] == 4
        # The attempt was kept although the response was an error.
        assert (
            post(business_a, VERIFY, {"phone": PHONE, "code": wrong}).json()["attempts_left"] == 3
        )

    @pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
    def test_code_must_be_six_digits(self, business_a: Business, code: str) -> None:
        response = post(business_a, VERIFY, {"phone": PHONE, "code": code})
        assert response.status_code == 400
        assert "code" in response.json()["fields"]


class TestConfirm:
    def test_reset_signs_in_and_signs_out_everywhere_else(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        old = sign_in(user)
        token = reset_token(business_a, sms, django_capture_on_commit_callbacks)
        response = post(business_a, CONFIRM, {"reset_token": token, "password": NEW_PASSWORD})
        assert response.status_code == 200
        assert response.json()["user"]["id"] == str(user.pk)
        assert response.cookies[REFRESH_COOKIE].value
        assert client_for(business_a, old.access).get("/api/v1/me").status_code == 401
        assert (
            client_for(business_a, response.json()["access"]).get("/api/v1/me").status_code == 200
        )
        login = post(business_a, "/api/v1/auth/login", {"phone": PHONE, "password": NEW_PASSWORD})
        assert login.status_code == 200
        with tenant_context(business_a.id):
            assert AuditLog.objects.filter(action="auth.password_reset").exists()

    def test_a_weak_password_does_not_spend_the_token(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        token = reset_token(business_a, sms, django_capture_on_commit_callbacks)
        weak = post(business_a, CONFIRM, {"reset_token": token, "password": "12345678"})
        assert weak.status_code == 400
        assert "password" in weak.json()["fields"]
        good = post(business_a, CONFIRM, {"reset_token": token, "password": NEW_PASSWORD})
        assert good.status_code == 200

    def test_a_token_works_once(
        self,
        business_a: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        token = reset_token(business_a, sms, django_capture_on_commit_callbacks)
        assert (
            post(business_a, CONFIRM, {"reset_token": token, "password": NEW_PASSWORD}).status_code
            == 200
        )
        again = post(business_a, CONFIRM, {"reset_token": token, "password": NEW_PASSWORD})
        assert again.status_code == 400
        assert again.json()["code"] == "invalid_reset_token"

    def test_a_token_from_another_business_is_unknown_here(
        self,
        business_a: Business,
        business_b: Business,
        user: User,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        token = reset_token(business_a, sms, django_capture_on_commit_callbacks)
        response = post(business_b, CONFIRM, {"reset_token": token, "password": NEW_PASSWORD})
        assert response.json()["code"] == "invalid_reset_token"


class TestChange:
    def test_change_keeps_this_session_and_ends_the_others(
        self, business_a: Business, user: User
    ) -> None:
        here, elsewhere = sign_in(user), sign_in(user)
        response = client_for(business_a, here.access).post(
            CHANGE, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}, format="json"
        )
        assert response.status_code == 204
        assert client_for(business_a, here.access).get("/api/v1/me").status_code == 200
        assert client_for(business_a, elsewhere.access).get("/api/v1/me").status_code == 401
        with tenant_context(business_a.id):
            assert UserSession.objects.filter(revoke_reason="password_changed").count() == 1
            assert AuditLog.objects.filter(action="auth.password_changed").exists()

    def test_wrong_current_password(self, business_a: Business, user: User) -> None:
        response = client_for(business_a, sign_in(user).access).post(
            CHANGE, {"current_password": "nope-nope", "new_password": NEW_PASSWORD}, format="json"
        )
        assert response.status_code == 400
        assert response.json()["fields"] == {
            "current_password": ["That isn't your current password."]
        }

    @pytest.mark.parametrize("weak", ["short1", "1234567890", "password123"])
    def test_new_password_follows_the_x13_checklist(
        self, business_a: Business, user: User, weak: str
    ) -> None:
        response = client_for(business_a, sign_in(user).access).post(
            CHANGE, {"current_password": TEST_PASSWORD, "new_password": weak}, format="json"
        )
        assert response.status_code == 400
        assert "new_password" in response.json()["fields"]

    def test_needs_sign_in(self, business_a: Business) -> None:
        assert client_for(business_a).post(CHANGE, {}, format="json").status_code == 401

    def test_cross_business(self, business_b: Business, user: User) -> None:
        assert_cross_business_token_rejected(user=user, other=business_b, url="/api/v1/me")
        response = client_for(business_b, sign_in(user).access).post(
            CHANGE, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}, format="json"
        )
        assert response.status_code == 401
