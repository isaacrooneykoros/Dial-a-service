"""S-02 register this device, and the device X-15 runs on (M1 T06a, ADR-0002 section 7)."""

from typing import Any

import pytest

from apps.accounts.api.cookies import DEVICE_COOKIE, REFRESH_COOKIE
from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.services.devices import hash_device_token
from apps.accounts.tests.factories import DeviceFactory, UserFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.branches.models import Branch
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/staff/devices"
CURRENT = "/api/v1/devices/current"


@pytest.fixture
def branch(business_a: Business) -> Branch:
    with tenant_context(business_a.id):
        created: Branch = BranchFactory(name="Kilimani")
    return created


def person(business: Business, role: str, branch: Branch | None = None, **kwargs: Any) -> User:
    with tenant_context(business.id):
        user: User = UserFactory(role=role, **kwargs)
        if branch is not None:
            BranchMemberFactory(branch=branch, user=user)
    return user


def register(business: Business, user: User, branch: Branch, name: str = "Front counter") -> Any:
    signed_in = sign_in(user)
    client = client_for(business, signed_in.access)
    response = client.post(REGISTER, {"name": name, "branch_id": str(branch.pk)}, format="json")
    return response, signed_in


class TestRegister:
    def test_a_manager_registers_their_branch_device_and_is_signed_out_of_it(
        self, business_a: Business, branch: Branch
    ) -> None:
        manager = person(business_a, Role.MANAGER, branch)
        response, signed_in = register(business_a, manager, branch)
        assert response.status_code == 201, response.json()
        assert response.json()["name"] == "Front counter"
        assert response.json()["branch"] == {"id": str(branch.pk), "name": "Kilimani"}

        cookie = response.cookies[DEVICE_COOKIE]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Strict"
        assert cookie["path"] == "/api/v1"
        assert response.cookies[REFRESH_COOKIE].value == ""  # signed out here (S-02)

        with tenant_context(business_a.id):
            device = Device.objects.get()
            assert device.token_hash == hash_device_token(cookie.value)  # stored hashed
            assert cookie.value not in device.token_hash
            session = UserSession.objects.get(pk=signed_in.session.pk)
            assert session.revoke_reason == "device_registered"
            assert AuditLog.objects.filter(action="device.register").exists()
        assert client_for(business_a, signed_in.access).get("/api/v1/me").status_code == 401

    def test_owners_register_for_any_branch(self, business_a: Business, branch: Branch) -> None:
        owner = person(business_a, Role.OWNER)  # not a member of the branch
        assert register(business_a, owner, branch)[0].status_code == 201

    def test_managers_only_for_their_own_branches(
        self, business_a: Business, branch: Branch
    ) -> None:
        manager = person(business_a, Role.MANAGER)
        response = register(business_a, manager, branch)[0]
        assert response.status_code == 400
        assert response.json()["code"] == "not_your_branch"

    @pytest.mark.parametrize("role", [Role.STAFF, Role.ACCOUNTANT])
    def test_staff_and_accountants_cannot(
        self, business_a: Business, branch: Branch, role: str
    ) -> None:
        user = person(business_a, role, branch)
        response = register(business_a, user, branch)[0]
        assert response.status_code == 403
        assert response.json()["code"] == "not_allowed"

    def test_another_business_branch_is_unknown(
        self, business_a: Business, business_b: Business
    ) -> None:
        owner = person(business_a, Role.OWNER)
        with tenant_context(business_b.id):
            theirs = BranchFactory()
        response = register(business_a, owner, theirs)[0]
        assert response.json()["code"] == "unknown_branch"

    def test_closed_branches_are_unknown(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        with tenant_context(business_a.id):
            closed = BranchFactory(status=Branch.Status.CLOSED)
        assert register(business_a, owner, closed)[0].json()["code"] == "unknown_branch"

    def test_validation(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        client = client_for(business_a, sign_in(owner).access)
        response = client.post(REGISTER, {"name": "", "branch_id": "nope"}, format="json")
        assert response.status_code == 400
        assert set(response.json()["fields"]) == {"name", "branch_id"}

    def test_needs_sign_in(self, business_a: Business) -> None:
        assert client_for(business_a).post(REGISTER, {}, format="json").status_code == 401


class TestCurrentDevice:
    def device_client(self, business: Business, user: User, branch: Branch) -> Any:
        response, _ = register(business, user, branch)
        client = client_for(business)
        client.cookies[DEVICE_COOKIE] = response.cookies[DEVICE_COOKIE].value
        return client

    def test_roster_lists_branch_people_with_a_pin(
        self, business_a: Business, branch: Branch
    ) -> None:
        manager = person(business_a, Role.MANAGER, branch, pin_hash="x", first_name="Juma")
        staff = person(
            business_a, Role.STAFF, branch, pin_hash="x", first_name="Achieng", last_name="otieno"
        )
        person(business_a, Role.STAFF, branch, first_name="NoPin")
        person(business_a, Role.ACCOUNTANT, branch, pin_hash="x", first_name="Accounts")
        person(
            business_a,
            Role.STAFF,
            branch,
            pin_hash="x",
            status=User.Status.SUSPENDED,
            first_name="Away",
        )
        with tenant_context(business_a.id):
            other_branch = BranchFactory()
        person(business_a, Role.STAFF, other_branch, pin_hash="x", first_name="Elsewhere")

        response = self.device_client(business_a, manager, branch).get(CURRENT)
        assert response.status_code == 200
        body = response.json()
        assert body["locked"] is False
        assert body["device"]["branch"]["id"] == str(branch.pk)
        assert body["roster"] == [
            {"id": str(staff.pk), "first_name": "Achieng", "last_initial": "O", "role": "staff"},
            {"id": str(manager.pk), "first_name": "Juma", "last_initial": "K", "role": "manager"},
        ]
        assert "phone" not in str(body)

    def test_locked_devices_say_so(self, business_a: Business, branch: Branch) -> None:
        manager = person(business_a, Role.MANAGER, branch)
        client = self.device_client(business_a, manager, branch)
        with tenant_context(business_a.id):
            Device.objects.update(status=Device.Status.LOCKED)
        assert client.get(CURRENT).json()["locked"] is True

    def test_removed_devices_are_unknown(self, business_a: Business, branch: Branch) -> None:
        manager = person(business_a, Role.MANAGER, branch)
        client = self.device_client(business_a, manager, branch)
        with tenant_context(business_a.id):
            Device.objects.update(status=Device.Status.REMOVED)
        assert client.get(CURRENT).status_code == 404

    @pytest.mark.parametrize("cookie", [None, "", "made-up"])
    def test_no_or_unknown_device(self, business_a: Business, cookie: str | None) -> None:
        client = client_for(business_a)
        if cookie is not None:
            client.cookies[DEVICE_COOKIE] = cookie
        assert client.get(CURRENT).status_code == 404

    def test_a_device_cookie_from_another_business_is_unknown_here(
        self, business_a: Business, business_b: Business, branch: Branch
    ) -> None:
        manager = person(business_a, Role.MANAGER, branch)
        response, _ = register(business_a, manager, branch)
        intruder = client_for(business_b)
        intruder.cookies[DEVICE_COOKIE] = response.cookies[DEVICE_COOKIE].value
        assert intruder.get(CURRENT).status_code == 404

    def test_cross_business(self, business_a: Business, business_b: Business) -> None:
        """The harness form: B's device, reached with B's cookie, is 404 for A."""

        def make() -> Device:
            device: Device = DeviceFactory(token_hash=hash_device_token("b-device-token"))
            return device

        owner_client = client_for(business_b)
        owner_client.cookies[DEVICE_COOKIE] = "b-device-token"
        intruder = client_for(business_a)
        intruder.cookies[DEVICE_COOKIE] = "b-device-token"
        assert_cross_business_404(
            owner=business_b,
            owner_client=owner_client,
            intruder=intruder,
            make_object=make,
            url_for=lambda device: CURRENT,
        )
