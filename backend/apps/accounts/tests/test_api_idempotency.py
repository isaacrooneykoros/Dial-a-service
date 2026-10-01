"""Idempotency-Key on POSTs (M1 T07c, CLAUDE.md section 6.5, ADR-0002 section 8)."""

import hashlib
from datetime import timedelta
from typing import Any

import pytest
import time_machine
from django.test import Client, RequestFactory
from django.utils import timezone

from apps.accounts.idempotency import IdempotencyMiddleware
from apps.accounts.models import Invitation, Role, User
from apps.accounts.tests.factories import TEST_PASSWORD, DeviceFactory, UserFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.branches.tests.factories import BranchFactory
from apps.core.models import IdempotencyKey
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.core.tests.factories import IdempotencyKeyFactory
from apps.tenancy.models import Business
from apps.tenancy.tasks import purge_idempotency_keys
from tests.testapp.models import Widget

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.urls")]

INVITES = "/api/v1/console/invitations"
KEY = "retry-key-0001"
BODY = {"phone": "0722000111", "first_name": "A", "last_name": "B", "role": "accountant"}


@pytest.fixture
def owner(business_a: Business) -> User:
    with tenant_context(business_a.id):
        user: User = UserFactory(role=Role.OWNER)
    return user


def owner_client(business: Business, owner: User) -> Any:
    return client_for(business, sign_in(owner).access)


def invitations(business: Business) -> int:
    with tenant_context(business.id):
        return Invitation.objects.count()


class TestRules:
    def test_a_repeat_returns_the_first_response_without_running_again(
        self, business_a: Business, owner: User
    ) -> None:
        client = owner_client(business_a, owner)
        first = client.post(INVITES, BODY, format="json", idempotency_key=KEY)
        assert first.status_code == 201
        again = client.post(INVITES, BODY, format="json", idempotency_key=KEY)
        assert again.status_code == 201
        assert again.json() == first.json()
        assert again["Idempotent-Replayed"] == "true"
        assert invitations(business_a) == 1
        with tenant_context(business_a.id):
            assert Invitation.objects.get().sent_count == 1  # no second SMS either

    def test_the_same_key_with_a_different_body_is_refused(
        self, business_a: Business, owner: User
    ) -> None:
        client = owner_client(business_a, owner)
        client.post(INVITES, BODY, format="json", idempotency_key=KEY)
        other = client.post(
            INVITES, {**BODY, "first_name": "Other"}, format="json", idempotency_key=KEY
        )
        assert other.status_code == 409
        assert other.json()["code"] == "idempotency_key_reused"

    def test_the_same_key_on_another_path_is_refused(
        self, business_a: Business, owner: User
    ) -> None:
        client = owner_client(business_a, owner)
        client.post(INVITES, BODY, format="json", idempotency_key=KEY)
        response = client.post(
            "/api/v1/me/pin", {"pin": "4826"}, format="json", idempotency_key=KEY
        )
        assert response.status_code == 409

    def test_signed_in_posts_need_a_key(self, business_a: Business, owner: User) -> None:
        response = owner_client(business_a, owner).post(
            INVITES, BODY, format="json", idempotency_key=None
        )
        assert response.status_code == 400
        assert response.json()["code"] == "idempotency_key_required"
        assert invitations(business_a) == 0

    @pytest.mark.parametrize("key", ["short", "has spaces in it", "x" * 101, "bad/slash-key"])
    def test_badly_formed_keys(self, business_a: Business, owner: User, key: str) -> None:
        response = owner_client(business_a, owner).post(
            INVITES, BODY, format="json", idempotency_key=key
        )
        assert response.status_code == 400
        assert response.json()["code"] == "idempotency_key_invalid"

    def test_keys_belong_to_one_person(self, business_a: Business, owner: User) -> None:
        with tenant_context(business_a.id):
            other_owner = UserFactory(role=Role.OWNER)
        owner_client(business_a, owner).post(INVITES, BODY, format="json", idempotency_key=KEY)
        theirs = owner_client(business_a, other_owner).post(
            INVITES, {**BODY, "phone": "0733000222"}, format="json", idempotency_key=KEY
        )
        assert theirs.status_code == 201
        assert "Idempotent-Replayed" not in theirs

    def test_after_24_hours_a_key_runs_again(self, business_a: Business, owner: User) -> None:
        client = owner_client(business_a, owner)
        client.post(INVITES, BODY, format="json", idempotency_key=KEY)
        with time_machine.travel(timezone.now() + timedelta(hours=24, minutes=1)):
            later = owner_client(business_a, owner).post(
                INVITES, BODY, format="json", idempotency_key=KEY
            )
        assert "Idempotent-Replayed" not in later

    def test_a_key_still_in_progress(self, business_a: Business, owner: User) -> None:
        with tenant_context(business_a.id):
            IdempotencyKeyFactory(
                scope=str(owner.pk),
                key=KEY,
                path=INVITES,
                body_hash=hashlib.sha256(b"").hexdigest(),
            )
        response = owner_client(business_a, owner).post(
            INVITES, b"", content_type="application/json", idempotency_key=KEY
        )
        assert response.status_code == 409
        assert response.json()["code"] == "idempotency_in_progress"


class TestWhatIsNotStored:
    def test_sign_in_endpoints_never_store_responses(
        self, business_a: Business, owner: User
    ) -> None:
        client = client_for(business_a)
        body = {"phone": owner.phone, "password": TEST_PASSWORD}
        first = client.post("/api/v1/auth/login", body, format="json", idempotency_key=KEY)
        second = client.post("/api/v1/auth/login", body, format="json", idempotency_key=KEY)
        assert first.json()["access"] != second.json()["access"]
        with tenant_context(business_a.id):
            assert not IdempotencyKey.objects.exists()

    def test_responses_that_set_cookies_are_not_kept(
        self, business_a: Business, owner: User
    ) -> None:
        with tenant_context(business_a.id):
            branch = BranchFactory()
        body = {"name": "Front", "branch_id": str(branch.pk)}
        response = owner_client(business_a, owner).post(
            "/api/v1/staff/devices", body, format="json", idempotency_key=KEY
        )
        assert response.status_code == 201
        with tenant_context(business_a.id):
            assert not IdempotencyKey.objects.exists()

    def test_a_crashed_request_leaves_no_key(self, business_a: Business) -> None:
        client = Client(headers={"host": "business-a.localhost"}, raise_request_exception=False)
        crashed = client.post("/api/v1/t/create-then-raise", HTTP_IDEMPOTENCY_KEY=KEY)
        assert crashed.status_code == 500
        with tenant_context(business_a.id):
            assert not IdempotencyKey.objects.exists()
            assert not Widget.objects.exists()

    def test_anonymous_posts_with_a_key_are_kept_per_ip(self, business_a: Business) -> None:
        client = Client(headers={"host": "business-a.localhost"})
        first = client.post("/api/v1/t/create", HTTP_IDEMPOTENCY_KEY=KEY)
        again = client.post("/api/v1/t/create", HTTP_IDEMPOTENCY_KEY=KEY)
        assert again.json() == first.json()
        with tenant_context(business_a.id):
            assert Widget.objects.count() == 1
            assert IdempotencyKey.objects.get().scope.startswith("ip:")

    def test_anonymous_posts_without_a_key_run_normally(self, business_a: Business) -> None:
        client = Client(headers={"host": "business-a.localhost"})
        client.post("/api/v1/t/create")
        client.post("/api/v1/t/create")
        with tenant_context(business_a.id):
            assert Widget.objects.count() == 2

    def test_a_bad_token_is_left_to_the_view(self, business_a: Business) -> None:
        client = client_for(business_a, "not-a-token")
        assert client.post(INVITES, BODY, format="json", idempotency_key=None).status_code == 401

    def test_other_methods_and_paths_are_untouched(self) -> None:
        middleware = IdempotencyMiddleware(lambda request: None)  # type: ignore[arg-type,return-value]
        get = RequestFactory().get("/api/v1/me")
        get.business = object()  # type: ignore[attr-defined]
        assert not middleware.applies(get)
        health = RequestFactory().post("/api/v1/health")
        health.business = None  # type: ignore[attr-defined]
        assert not middleware.applies(health)


def test_keys_are_purged_after_24_hours(business_a: Business) -> None:
    with tenant_context(business_a.id):
        IdempotencyKeyFactory(expires_at=timezone.now() - timedelta(minutes=1))
        IdempotencyKeyFactory()
    assert purge_idempotency_keys() == {"deleted": 1}


def test_cross_business(business_a: Business, business_b: Business) -> None:
    """A key reused on another business is unrelated there; objects stay 404."""
    with tenant_context(business_b.id):
        their_owner = UserFactory(role=Role.OWNER)
    with tenant_context(business_a.id):
        our_owner = UserFactory(role=Role.OWNER)
    assert_cross_business_404(
        owner=business_b,
        owner_client=owner_client(business_b, their_owner),
        intruder=owner_client(business_a, our_owner),
        make_object=DeviceFactory,
        url_for=lambda device: f"/api/v1/console/devices/{device.pk}/remove",
        method="post",
        expected_owner_status=204,
    )
