"""A-42 in the console: signed-in sessions and registered devices (M1 T06b)."""

from typing import Any

import pytest
from django.utils import timezone

from apps.accounts.models import Device, Role, User, UserSession
from apps.accounts.tests.factories import DeviceFactory, UserFactory, UserSessionFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.branches.models import Branch
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

SESSIONS = "/api/v1/console/sessions"
DEVICES = "/api/v1/console/devices"


@pytest.fixture
def branch(business_a: Business) -> Branch:
    with tenant_context(business_a.id):
        created: Branch = BranchFactory(name="Kilimani")
    return created


def person(business: Business, role: str, branch: Branch | None = None) -> User:
    with tenant_context(business.id):
        user: User = UserFactory(role=role)
        if branch is not None:
            BranchMemberFactory(branch=branch, user=user)
    return user


def as_user(business: Business, user: User) -> Any:
    return client_for(business, sign_in(user).access)


class TestSessions:
    def test_owner_sees_every_live_session_and_which_is_theirs(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        staff = person(business_a, Role.STAFF)
        sign_in(staff)
        with tenant_context(business_a.id):
            ended = UserSessionFactory(user=staff)
            UserSession.objects.filter(pk=ended.pk).update(revoked_at=timezone.now())
        signed_in = sign_in(owner)
        response = client_for(business_a, signed_in.access).get(SESSIONS)
        assert response.status_code == 200
        rows = response.json()["results"]
        assert {row["user"]["id"] for row in rows} == {str(owner.pk), str(staff.pk)}
        assert len(rows) == 2
        assert [row["id"] for row in rows if row["is_current"]] == [str(signed_in.session.pk)]
        assert str(ended.pk) not in {row["id"] for row in rows}

    def test_managers_do_not_see_owners_sessions(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        owner_session = sign_in(owner).session
        manager = person(business_a, Role.MANAGER)
        client = as_user(business_a, manager)
        rows = client.get(SESSIONS).json()["results"]
        assert str(owner.pk) not in {row["user"]["id"] for row in rows}
        response = client.post(f"{SESSIONS}/{owner_session.pk}/sign-out")
        assert response.status_code == 404

    def test_signing_a_session_out_takes_effect_at_once(self, business_a: Business) -> None:
        owner = person(business_a, Role.OWNER)
        staff = person(business_a, Role.STAFF)
        theirs = sign_in(staff)
        response = as_user(business_a, owner).post(f"{SESSIONS}/{theirs.session.pk}/sign-out")
        assert response.status_code == 204
        assert client_for(business_a, theirs.access).get("/api/v1/me").status_code == 401
        with tenant_context(business_a.id):
            assert AuditLog.objects.filter(action="auth.session_revoked").exists()

    @pytest.mark.parametrize("role", [Role.STAFF, Role.ACCOUNTANT])
    def test_staff_and_accountants_cannot(self, business_a: Business, role: str) -> None:
        client = as_user(business_a, person(business_a, role))
        assert client.get(SESSIONS).status_code == 403
        assert client.get(DEVICES).status_code == 403

    def test_cross_business(self, business_a: Business, business_b: Business) -> None:
        their_owner = person(business_b, Role.OWNER)
        assert_cross_business_404(
            owner=business_b,
            owner_client=as_user(business_b, their_owner),
            intruder=as_user(business_a, person(business_a, Role.OWNER)),
            make_object=UserSessionFactory,
            url_for=lambda session: f"{SESSIONS}/{session.pk}/sign-out",
            method="post",
        )


def remove_url(device: Device) -> str:
    return f"{DEVICES}/{device.pk}/remove"


class TestDevices:
    def test_owner_lists_all_devices_managers_only_their_branches(
        self, business_a: Business, branch: Branch
    ) -> None:
        with tenant_context(business_a.id):
            mine = DeviceFactory(branch=branch, name="Front")
            other = DeviceFactory(name="Westlands till")
            DeviceFactory(branch=branch, status=Device.Status.REMOVED)
        owner = person(business_a, Role.OWNER)
        manager = person(business_a, Role.MANAGER, branch)
        owner_rows = as_user(business_a, owner).get(DEVICES).json()
        assert {row["id"] for row in owner_rows} == {str(mine.pk), str(other.pk)}
        manager_rows = as_user(business_a, manager).get(DEVICES).json()
        assert [row["id"] for row in manager_rows] == [str(mine.pk)]
        assert manager_rows[0]["branch"]["name"] == "Kilimani"

    def test_removing_a_device_ends_every_session_on_it(
        self, business_a: Business, branch: Branch
    ) -> None:
        with tenant_context(business_a.id):
            device = DeviceFactory(branch=branch)
            staff = UserFactory()
            on_device = UserSessionFactory(user=staff, device=device)
        owner = person(business_a, Role.OWNER)
        response = as_user(business_a, owner).post(remove_url(device))
        assert response.status_code == 204
        with tenant_context(business_a.id):
            device.refresh_from_db()
            on_device.refresh_from_db()
            assert device.status == Device.Status.REMOVED
            assert on_device.revoke_reason == "device_removed"
            assert AuditLog.objects.filter(action="device.remove").exists()

    def test_managers_cannot_remove_other_branch_devices(
        self, business_a: Business, branch: Branch
    ) -> None:
        with tenant_context(business_a.id):
            other = DeviceFactory()
        manager = person(business_a, Role.MANAGER, branch)
        assert as_user(business_a, manager).post(remove_url(other)).status_code == 404

    def test_cross_business(self, business_a: Business, business_b: Business) -> None:
        their_owner = person(business_b, Role.OWNER)
        assert_cross_business_404(
            owner=business_b,
            owner_client=as_user(business_b, their_owner),
            intruder=as_user(business_a, person(business_a, Role.OWNER)),
            make_object=DeviceFactory,
            url_for=remove_url,
            method="post",
            expected_owner_status=204,
        )
