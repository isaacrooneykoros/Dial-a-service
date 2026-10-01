"""Invitations (A-41 minimal), X-14 accept and the first PIN (M1 T05d, ADR-0002 section 6)."""

import functools
import re
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
import time_machine
from django.utils import timezone

from apps.accounts.api.cookies import REFRESH_COOKIE
from apps.accounts.models import Invitation, Role, User
from apps.accounts.tests.factories import InvitationFactory, UserFactory
from apps.accounts.tests.helpers import client_for, sign_in
from apps.branches.models import Branch, BranchMember
from apps.branches.tests.factories import BranchFactory, BranchMemberFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.core.testing.tenancy import assert_cross_business_404
from apps.notifications.backends import LocmemSmsBackend
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db

INVITES = "/api/v1/console/invitations"
NEW_PHONE = "+254722000111"
PASSWORD = "Ndizi-na-chai-77"


@pytest.fixture(autouse=True)
def sms() -> Iterator[list[Any]]:
    LocmemSmsBackend.outbox.clear()
    yield LocmemSmsBackend.outbox
    LocmemSmsBackend.outbox.clear()


@pytest.fixture
def branch(business_a: Business) -> Branch:
    with tenant_context(business_a.id):
        created: Branch = BranchFactory(name="Kilimani")
    return created


@pytest.fixture
def owner(business_a: Business) -> User:
    with tenant_context(business_a.id):
        created: User = UserFactory(role=Role.OWNER)
    return created


def business_of(user: User) -> Business:
    assert user.business is not None
    return user.business


def as_user(user: User) -> Any:
    return client_for(business_of(user), sign_in(user).access)


def invite(client: Any, capture: Any = None, **overrides: Any) -> Any:
    data = {
        "phone": "0722 000 111",
        "first_name": "Achieng",
        "last_name": "Otieno",
        "role": "staff",
        "branch_ids": [],
        "rights": {"accept_cash": True},
    }
    data.update(overrides)
    if capture is None:
        return client.post(INVITES, data, format="json")
    with capture(execute=True):
        return client.post(INVITES, data, format="json")


def link_token(sms: list[Any]) -> str:
    match = re.search(r"/invite/(\S+)$", sms[-1].text)
    assert match, sms[-1].text
    return match[1]


def code_from(sms: list[Any]) -> str:
    match = re.match(r"^(\d{6}) is your ", sms[-1].text)
    assert match, sms[-1].text
    return match[1]


class TestInviting:
    def test_owner_invites_staff_and_the_sms_has_the_catalogue_text(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        response = invite(
            as_user(owner), django_capture_on_commit_callbacks, branch_ids=[str(branch.pk)]
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["phone"] == NEW_PHONE
        assert body["branch_ids"] == [str(branch.pk)]
        assert body["rights"] == {
            "accept_cash": True,
            "give_discounts": False,
            "correct_prices": False,
        }
        assert sms[-1].to == NEW_PHONE
        assert re.fullmatch(
            r"Business-A invited you to join as Shop staff\. Set up your account: "
            r"https://business-a\.localhost/invite/\S+",
            sms[-1].text,
        )
        with tenant_context(business_of(owner).id):
            invitation = Invitation.objects.get()
            assert link_token(sms) not in invitation.token_hash  # stored hashed
            assert AuditLog.objects.filter(action="invitation.create").exists()

    def test_accountants_need_no_branch(self, owner: User) -> None:
        assert invite(as_user(owner), role="accountant").status_code == 201

    def test_staff_and_managers_need_a_branch(self, owner: User) -> None:
        response = invite(as_user(owner))
        assert response.status_code == 400
        assert response.json()["code"] == "branch_required"
        assert response.json()["fields"] == {"branch_ids": ["Choose at least one branch."]}

    @pytest.mark.parametrize("role", ["owner", "rider", "customer", "platform_super_admin"])
    def test_only_managers_accountants_and_staff_can_be_invited(
        self, owner: User, role: str
    ) -> None:
        response = invite(as_user(owner), role=role)
        assert response.status_code == 400
        assert "role" in response.json()["fields"]

    def test_a_number_with_an_account_here_is_refused(self, owner: User, branch: Branch) -> None:
        with tenant_context(business_of(owner).id):
            UserFactory(phone=NEW_PHONE)
        response = invite(as_user(owner), branch_ids=[str(branch.pk)])
        assert response.status_code == 409
        assert response.json()["code"] == "already_registered"

    def test_another_business_branch_is_unknown(self, owner: User, business_b: Business) -> None:
        with tenant_context(business_b.id):
            theirs = BranchFactory()
        response = invite(as_user(owner), branch_ids=[str(theirs.pk)])
        assert response.json()["code"] == "unknown_branch"

    def test_managers_invite_only_into_their_own_branches(
        self, business_a: Business, branch: Branch
    ) -> None:
        with tenant_context(business_a.id):
            manager = UserFactory(role=Role.MANAGER)
            BranchMemberFactory(branch=branch, user=manager)
            other = BranchFactory(name="Westlands")
        client = as_user(manager)
        assert invite(client, branch_ids=[str(branch.pk)]).status_code == 201
        refused = invite(client, phone="0733000222", branch_ids=[str(other.pk)])
        assert refused.json()["code"] == "not_your_branch"

    @pytest.mark.parametrize("role", [Role.STAFF, Role.ACCOUNTANT])
    def test_staff_and_accountants_cannot_invite(self, business_a: Business, role: str) -> None:
        with tenant_context(business_a.id):
            user = UserFactory(role=role)
        assert invite(as_user(user), role="accountant").status_code == 403

    def test_needs_sign_in(self, business_a: Business) -> None:
        assert client_for(business_a).post(INVITES, {}, format="json").status_code == 401

    def test_inviting_the_same_number_again_resends_with_the_new_details(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        client = as_user(owner)
        first = invite(client, django_capture_on_commit_callbacks, branch_ids=[str(branch.pk)])
        old_token = link_token(sms)
        second = invite(
            client, django_capture_on_commit_callbacks, role="accountant", branch_ids=[]
        )
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["role"] == "accountant"
        assert second.json()["sent_count"] == 2
        assert (
            client_for(business_of(owner)).get(f"/api/v1/auth/invitations/{old_token}").status_code
            == 404
        )

    def test_list_shows_open_invitations(self, owner: User) -> None:
        with tenant_context(business_of(owner).id):
            open_one = InvitationFactory()
            InvitationFactory(cancelled_at=timezone.now())
            InvitationFactory(expires_at=timezone.now() - timedelta(minutes=1))
        response = as_user(owner).get(INVITES)
        assert [row["id"] for row in response.json()["results"]] == [str(open_one.pk)]


def action_url(invitation: Invitation, *, action: str) -> str:
    return f"{INVITES}/{invitation.pk}/{action}"


class TestResendAndCancel:
    def test_resend_gives_a_new_link(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        client = as_user(owner)
        invitation_id = invite(
            client, django_capture_on_commit_callbacks, branch_ids=[str(branch.pk)]
        ).json()["id"]
        old = link_token(sms)
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(f"{INVITES}/{invitation_id}/resend")
        assert response.status_code == 200
        assert link_token(sms) != old
        public = client_for(business_of(owner))
        assert public.get(f"/api/v1/auth/invitations/{old}").status_code == 404
        assert public.get(f"/api/v1/auth/invitations/{link_token(sms)}").status_code == 200

    def test_cancel_then_nothing_more(self, owner: User) -> None:
        with tenant_context(business_of(owner).id):
            invitation = InvitationFactory()
        client = as_user(owner)
        assert client.post(f"{INVITES}/{invitation.pk}/cancel").status_code == 200
        again = client.post(f"{INVITES}/{invitation.pk}/resend")
        assert again.status_code == 409
        assert again.json()["code"] == "invitation_closed"

    def test_cross_business(self, business_a: Business, business_b: Business, owner: User) -> None:
        with tenant_context(business_b.id):
            their_owner = UserFactory(role=Role.OWNER)
        for action in ("resend", "cancel"):
            assert_cross_business_404(
                owner=business_b,
                owner_client=as_user(their_owner),
                intruder=as_user(owner),
                make_object=InvitationFactory,
                url_for=functools.partial(action_url, action=action),
                method="post",
            )


class TestAcceptInvitation:
    """X-14 -> X-12 -> X-13 -> choose a PIN."""

    def start(self, owner: User, branch: Branch, sms: list[Any], capture: Any) -> tuple[Any, str]:
        invite(as_user(owner), capture, branch_ids=[str(branch.pk)])
        return client_for(business_of(owner)), link_token(sms)

    def test_the_whole_journey(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)

        details = public.get(f"/api/v1/auth/invitations/{token}")
        assert details.json() == {
            "business_name": "Business-A",
            "role": "staff",
            "role_label": "Shop staff",
            "first_name": "Achieng",
            "phone": NEW_PHONE,
        }

        with django_capture_on_commit_callbacks(execute=True):
            sent = public.post(f"/api/v1/auth/invitations/{token}/send-code")
        assert sent.status_code == 200
        verified = public.post(
            f"/api/v1/auth/invitations/{token}/verify", {"code": code_from(sms)}, format="json"
        )
        assert verified.status_code == 200
        accepted = public.post(
            "/api/v1/auth/invitations/accept",
            {"setup_token": verified.json()["setup_token"], "password": PASSWORD},
            format="json",
        )
        assert accepted.status_code == 201, accepted.json()
        assert accepted.cookies[REFRESH_COOKIE].value
        me = accepted.json()["user"]
        assert (me["phone"], me["role"], me["is_phone_verified"], me["has_pin"]) == (
            NEW_PHONE,
            "staff",
            True,
            False,
        )
        assert me["rights"]["accept_cash"] is True

        with tenant_context(business_of(owner).id):
            user = User.objects.get(phone=NEW_PHONE)
            assert BranchMember.objects.filter(user=user, branch=branch).exists()
            assert Invitation.objects.get().accepted_user_id == user.pk

        signed_in = client_for(business_of(owner), accepted.json()["access"])
        assert signed_in.post("/api/v1/me/pin", {"pin": "4826"}, format="json").status_code == 204
        assert signed_in.get("/api/v1/me").json()["has_pin"] is True
        assert public.get(f"/api/v1/auth/invitations/{token}").status_code == 410

    def test_a_weak_password_does_not_spend_the_setup_token(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        with django_capture_on_commit_callbacks(execute=True):
            public.post(f"/api/v1/auth/invitations/{token}/send-code")
        setup = public.post(
            f"/api/v1/auth/invitations/{token}/verify", {"code": code_from(sms)}, format="json"
        ).json()["setup_token"]
        weak = public.post(
            "/api/v1/auth/invitations/accept",
            {"setup_token": setup, "password": "12345678"},
            format="json",
        )
        assert weak.status_code == 400
        good = public.post(
            "/api/v1/auth/invitations/accept",
            {"setup_token": setup, "password": PASSWORD},
            format="json",
        )
        assert good.status_code == 201

    def test_expired_invitation_shows_the_x14_message(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        with time_machine.travel(timezone.now() + timedelta(days=7, minutes=1)):
            response = public.get(f"/api/v1/auth/invitations/{token}")
        assert response.status_code == 410
        assert response.json()["message"] == "Ask Business-A to send a new invitation"

    def test_number_registered_meanwhile_is_refused_at_accept(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        with django_capture_on_commit_callbacks(execute=True):
            public.post(f"/api/v1/auth/invitations/{token}/send-code")
        setup = public.post(
            f"/api/v1/auth/invitations/{token}/verify", {"code": code_from(sms)}, format="json"
        ).json()["setup_token"]
        with tenant_context(business_of(owner).id):
            UserFactory(phone=NEW_PHONE)
        response = public.post(
            "/api/v1/auth/invitations/accept",
            {"setup_token": setup, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 409
        assert response.json()["code"] == "already_registered"

    def test_a_used_setup_token_shows_the_expired_message(self, business_a: Business) -> None:
        response = client_for(business_a).post(
            "/api/v1/auth/invitations/accept",
            {"setup_token": "made-up", "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 410

    def test_unknown_token(self, business_a: Business) -> None:
        response = client_for(business_a).get("/api/v1/auth/invitations/made-up")
        assert response.status_code == 404
        assert (
            client_for(business_a).post("/api/v1/auth/invitations/made-up/send-code").status_code
            == 404
        )
        assert (
            client_for(business_a)
            .post("/api/v1/auth/invitations/made-up/verify", {"code": "123456"}, format="json")
            .status_code
            == 404
        )

    def test_a_link_from_another_business_is_unknown_here(
        self,
        owner: User,
        branch: Branch,
        business_b: Business,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        _, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        assert client_for(business_b).get(f"/api/v1/auth/invitations/{token}").status_code == 404

    def test_wrong_code_counts(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        with django_capture_on_commit_callbacks(execute=True):
            public.post(f"/api/v1/auth/invitations/{token}/send-code")
        wrong = "000000" if code_from(sms) != "000000" else "111111"
        response = public.post(
            f"/api/v1/auth/invitations/{token}/verify", {"code": wrong}, format="json"
        )
        assert response.json()["attempts_left"] == 4

    def test_resend_code_too_soon(
        self,
        owner: User,
        branch: Branch,
        sms: list[Any],
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        public, token = self.start(owner, branch, sms, django_capture_on_commit_callbacks)
        with django_capture_on_commit_callbacks(execute=True):
            public.post(f"/api/v1/auth/invitations/{token}/send-code")
        assert public.post(f"/api/v1/auth/invitations/{token}/send-code").status_code == 429


class TestFirstPin:
    @pytest.mark.parametrize(
        ("pin", "code"),
        [("1234", "pin_too_common"), ("0000", "pin_too_common"), ("12a4", "pin_format")],
    )
    def test_refused_pins(self, business_a: Business, pin: str, code: str) -> None:
        with tenant_context(business_a.id):
            user = UserFactory()
        response = as_user(user).post("/api/v1/me/pin", {"pin": pin}, format="json")
        assert response.status_code == 400
        assert response.json()["code"] == code

    def test_wrong_length(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            user = UserFactory()
        response = as_user(user).post("/api/v1/me/pin", {"pin": "12345"}, format="json")
        assert response.status_code == 400
        assert response.json()["code"] == "validation_error"

    def test_only_once(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            user = UserFactory()
        client = as_user(user)
        assert client.post("/api/v1/me/pin", {"pin": "4826"}, format="json").status_code == 204
        again = client.post("/api/v1/me/pin", {"pin": "7391"}, format="json")
        assert again.status_code == 409
        with tenant_context(business_a.id):
            user.refresh_from_db()
            assert user.pin_hash
            assert "4826" not in user.pin_hash  # stored hashed
            assert AuditLog.objects.filter(action="user.pin_set").count() == 1

    def test_accountants_have_no_pin(self, business_a: Business) -> None:
        with tenant_context(business_a.id):
            user = UserFactory(role=Role.ACCOUNTANT)
        response = as_user(user).post("/api/v1/me/pin", {"pin": "4826"}, format="json")
        assert response.status_code == 403
