"""X-15 switch user with a PIN, the 5-wrong-PIN lock and unlocking (M1 T06b, ADR-0002 section 7)."""

from typing import Any

import pytest
from django.contrib.auth.hashers import make_password

from apps.accounts.api.cookies import DEVICE_COOKIE, REFRESH_COOKIE
from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.tests.factories import TEST_PASSWORD, UserFactory
from apps.accounts.tests.helpers import assert_cross_business_token_rejected, client_for, sign_in
from apps.branches.models import Branch
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

SWITCH = "/api/v1/auth/pin-switch"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/me"


@pytest.fixture
def branch(business_a: Business) -> Branch:
    with tenant_context(business_a.id):
        created: Branch = BranchFactory(name="Kilimani")
    return created


def person(
    business: Business, role: str, branch: Branch | None, pin: str | None = None, **kw: Any
) -> User:
    with tenant_context(business.id):
        user: User = UserFactory(role=role, pin_hash=make_password(pin) if pin else "", **kw)
        if branch is not None:
            BranchMemberFactory(branch=branch, user=user)
    return user


@pytest.fixture
def manager(business_a: Business, branch: Branch) -> User:
    return person(business_a, Role.MANAGER, branch, pin="4826")


@pytest.fixture
def staff(business_a: Business, branch: Branch) -> User:
    return person(business_a, Role.STAFF, branch, pin="7391")


@pytest.fixture
def counter(business_a: Business, branch: Branch, manager: User) -> Any:
    """A registered device's client with only the device cookie (S-02 signed the manager out)."""
    client = client_for(business_a, sign_in(manager).access)
    response = client.post(
        "/api/v1/staff/devices", {"name": "Front", "branch_id": str(branch.pk)}, format="json"
    )
    assert response.status_code == 201
    device_client = client_for(business_a)
    device_client.cookies[DEVICE_COOKIE] = response.cookies[DEVICE_COOKIE].value
    return device_client


def switch(client: Any, user: User | str, pin: str) -> Any:
    user_id = user if isinstance(user, str) else str(user.pk)
    return client.post(SWITCH, {"user_id": user_id, "pin": pin}, format="json")


def device_of(business: Business) -> Device:
    with tenant_context(business.id):
        device: Device = Device.objects.get()
    return device


class TestSwitch:
    def test_the_right_pin_signs_the_person_in_on_this_device(
        self, business_a: Business, counter: Any, staff: User
    ) -> None:
        response = switch(counter, staff, "7391")
        assert response.status_code == 200, response.json()
        assert response.json()["user"]["id"] == str(staff.pk)
        assert response.cookies[REFRESH_COOKIE].value
        with tenant_context(business_a.id):
            session = UserSession.objects.get(user=staff)
            assert session.kind == UserSession.Kind.PIN
            assert session.device_id == device_of(business_a).pk
            assert AuditLog.objects.filter(action="auth.pin_switch").exists()
        assert client_for(business_a, response.json()["access"]).get(ME).status_code == 200

    def test_switching_ends_the_previous_pin_session_on_the_device(
        self, business_a: Business, counter: Any, staff: User, manager: User
    ) -> None:
        first = switch(counter, staff, "7391").json()["access"]
        assert switch(counter, manager, "4826").status_code == 200
        assert client_for(business_a, first).get(ME).status_code == 401

    def test_wrong_pins_count_down_and_the_fifth_locks_the_device(
        self, business_a: Business, counter: Any, staff: User
    ) -> None:
        left = [switch(counter, staff, "0000").json().get("attempts_left") for _ in range(4)]
        assert left == [4, 3, 2, 1]
        fifth = switch(counter, staff, "0000")
        assert fifth.status_code == 403
        assert fifth.json()["code"] == "device_locked"
        assert device_of(business_a).status == Device.Status.LOCKED
        locked = switch(counter, staff, "7391")  # even the right PIN
        assert locked.status_code == 403
        assert counter.get("/api/v1/devices/current").json()["locked"] is True

    def test_a_right_pin_resets_the_count(
        self, business_a: Business, counter: Any, staff: User
    ) -> None:
        switch(counter, staff, "0000")
        switch(counter, staff, "7391")
        assert device_of(business_a).failed_pin_attempts == 0

    def test_people_not_on_the_roster_count_as_wrong_pins(
        self, business_a: Business, counter: Any
    ) -> None:
        with tenant_context(business_a.id):
            elsewhere = BranchFactory()
        outsider = person(business_a, Role.STAFF, elsewhere, pin="7391")
        accountant = person(business_a, Role.ACCOUNTANT, None, pin="7391")
        for who in (outsider, accountant, "00000000-0000-4000-8000-000000000000"):
            response = switch(counter, who, "7391")
            assert response.json()["code"] == "wrong_pin"
        assert device_of(business_a).failed_pin_attempts == 3

    def test_no_device_cookie(self, business_a: Business, staff: User) -> None:
        assert switch(client_for(business_a), staff, "7391").status_code == 404

    def test_removed_devices(self, business_a: Business, counter: Any, staff: User) -> None:
        with tenant_context(business_a.id):
            Device.objects.update(status=Device.Status.REMOVED)
        assert switch(counter, staff, "7391").status_code == 404

    def test_validation(self, counter: Any) -> None:
        response = counter.post(SWITCH, {"user_id": "nope", "pin": "12"}, format="json")
        assert response.status_code == 400
        assert set(response.json()["fields"]) == {"user_id", "pin"}

    def test_a_device_cookie_from_another_business_is_unknown_there(
        self, business_b: Business, counter: Any, staff: User
    ) -> None:
        intruder = client_for(business_b)
        intruder.cookies[DEVICE_COOKIE] = counter.cookies[DEVICE_COOKIE].value
        assert switch(intruder, staff, "7391").status_code == 404

    def test_cross_business_token(self, business_b: Business, staff: User) -> None:
        assert_cross_business_token_rejected(user=staff, other=business_b, url=ME)


class TestUnlock:
    """D-37: a manager or owner of the branch signing in on the locked device unlocks it."""

    def lock(self, counter: Any, staff: User) -> None:
        for _ in range(5):
            switch(counter, staff, "0000")

    def login_on(self, counter: Any, user: User) -> Any:
        return counter.post(LOGIN, {"phone": user.phone, "password": TEST_PASSWORD}, format="json")

    def test_the_branch_manager_unlocks_it(
        self, business_a: Business, counter: Any, staff: User, manager: User
    ) -> None:
        self.lock(counter, staff)
        assert self.login_on(counter, manager).status_code == 200
        device = device_of(business_a)
        assert (device.status, device.failed_pin_attempts) == (Device.Status.ACTIVE, 0)
        assert switch(counter, staff, "7391").status_code == 200
        with tenant_context(business_a.id):
            assert AuditLog.objects.filter(action="device.unlock").exists()
            assert UserSession.objects.filter(user=manager, device=device).exists()

    def test_the_owner_unlocks_it(self, business_a: Business, counter: Any, staff: User) -> None:
        owner = person(business_a, Role.OWNER, None)
        self.lock(counter, staff)
        self.login_on(counter, owner)
        assert device_of(business_a).status == Device.Status.ACTIVE

    def test_staff_and_other_branch_managers_do_not(
        self, business_a: Business, counter: Any, staff: User
    ) -> None:
        with tenant_context(business_a.id):
            elsewhere = BranchFactory()
        other_manager = person(business_a, Role.MANAGER, elsewhere)
        self.lock(counter, staff)
        assert self.login_on(counter, staff).status_code == 200
        assert self.login_on(counter, other_manager).status_code == 200
        assert device_of(business_a).status == Device.Status.LOCKED
