"""Users are per business; platform staff are separate (M1 T05a, ADR-0002 section 1)."""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.accounts.backends import BusinessPhoneBackend
from apps.accounts.models import Role, User
from apps.accounts.tests.factories import TEST_PASSWORD, UserFactory
from apps.core.tenant_context import TenantContextMissing, TenantMismatch, tenant_context
from apps.core.testing.database import platform_connect
from apps.tenancy.models import Business
from apps.tenancy.tests.factories import BusinessFactory

pytestmark = pytest.mark.django_db

PHONE = "+254712345678"


@pytest.fixture
def a() -> Business:
    return BusinessFactory()


@pytest.fixture
def b() -> Business:
    return BusinessFactory()


class TestPerBusinessAccounts:
    def test_user_gets_the_current_business(self, a: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory(phone=PHONE)
        assert user.business_id == a.id

    def test_same_phone_twice_in_one_business_is_refused(self, a: Business) -> None:
        with tenant_context(a.id):
            UserFactory(phone=PHONE)
            with pytest.raises(IntegrityError), transaction.atomic():
                UserFactory(phone=PHONE)

    def test_same_phone_in_two_businesses_is_two_accounts(self, a: Business, b: Business) -> None:
        with tenant_context(a.id):
            first = UserFactory(phone=PHONE)
        with tenant_context(b.id):
            second = UserFactory(phone=PHONE)
        assert first.pk != second.pk

    def test_queries_need_a_business(self) -> None:
        with pytest.raises(TenantContextMissing):
            User.objects.count()

    def test_another_business_user_is_invisible(self, a: Business, b: Business) -> None:
        with tenant_context(a.id):
            UserFactory(phone=PHONE)
        with tenant_context(b.id):
            assert not User.objects.filter(phone=PHONE).exists()

    def test_saving_into_another_business_is_refused(self, a: Business, b: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory()
        with tenant_context(b.id), pytest.raises(TenantMismatch):
            user.save()

    def test_badly_formatted_phone_is_refused_by_the_database(self, a: Business) -> None:
        with tenant_context(a.id), pytest.raises(IntegrityError), transaction.atomic():
            UserFactory(phone="0712345678")

    def test_status_drives_is_active(self, a: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory()
        assert user.is_active
        user.status = User.Status.SUSPENDED
        assert not user.is_active

    def test_business_users_have_no_admin_permissions(self, a: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory(role=Role.OWNER, is_staff=True)
        assert not user.has_perm("tenancy.view_business")
        assert not user.has_module_perms("tenancy")
        assert not user.is_platform_staff
        assert str(user).startswith("Wanjiru Kamau")


@pytest.fixture
def platform_db() -> Iterator[psycopg.Connection[object]]:
    with platform_connect(connection.settings_dict["NAME"]) as conn:
        yield conn
        conn.execute("DELETE FROM accounts_user WHERE business_id IS NULL")


def insert_user(conn: psycopg.Connection[object], *, role: str, business: object = None) -> None:
    conn.execute(
        "INSERT INTO accounts_user (id, business_id, phone, first_name, last_name, role, language, "
        "is_phone_verified, status, pin_hash, can_accept_cash, can_give_discounts, "
        "can_correct_prices, is_staff, password, created_at, updated_at) VALUES "
        "(%s, %s, %s, 'P', 'Staff', %s, 'en', true, 'active', '', false, false, false, true, '!', "
        "now(), now())",
        (uuid.uuid4(), business, PHONE, role),
    )


class TestPlatformStaff:
    def test_platform_service_can_create_platform_staff(
        self, platform_db: psycopg.Connection[object]
    ) -> None:
        insert_user(platform_db, role=Role.PLATFORM_SUPER_ADMIN)

    def test_platform_staff_phones_are_unique(
        self, platform_db: psycopg.Connection[object]
    ) -> None:
        insert_user(platform_db, role=Role.PLATFORM_SUPPORT)
        with pytest.raises(psycopg.errors.UniqueViolation):
            insert_user(platform_db, role=Role.PLATFORM_FINANCE)

    def test_business_roles_need_a_business(self, platform_db: psycopg.Connection[object]) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            insert_user(platform_db, role=Role.STAFF)

    def test_platform_roles_cannot_have_a_business(
        self, a: Business, platform_db: psycopg.Connection[object]
    ) -> None:
        # Committed outside the test transaction so the platform connection can see it.
        with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation)):
            insert_user(platform_db, role=Role.PLATFORM_SUPPORT, business=a.id)

    def test_dial_app_cannot_create_platform_staff(self, a: Business) -> None:
        user = User(
            phone=PHONE, first_name="P", last_name="S", role=Role.PLATFORM_SUPPORT, is_staff=True
        )
        user.set_unusable_password()
        with tenant_context(a.id), pytest.raises(DatabaseError), transaction.atomic():
            user.save()

    def test_platform_super_admin_permissions(self) -> None:
        user = User(role=Role.PLATFORM_SUPER_ADMIN, is_staff=True)
        assert user.is_platform_staff
        assert user.has_perm("tenancy.view_business")
        assert not User(role=Role.PLATFORM_SUPPORT, is_staff=True).has_perm("x")


class TestSignInBackend:
    def test_correct_password_in_this_business(self, a: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory(phone=PHONE)
            assert authenticate(None, phone="0712 345 678", password=TEST_PASSWORD) == user

    def test_wrong_password(self, a: Business) -> None:
        with tenant_context(a.id):
            UserFactory(phone=PHONE)
            assert authenticate(None, phone=PHONE, password="wrong-password") is None

    def test_account_in_another_business_does_not_sign_in_here(
        self, a: Business, b: Business
    ) -> None:
        with tenant_context(b.id):
            UserFactory(phone=PHONE)
        with tenant_context(a.id):
            assert authenticate(None, phone=PHONE, password=TEST_PASSWORD) is None

    @pytest.mark.parametrize("phone", ["", "not a phone", "0812345678"])
    def test_bad_phone(self, a: Business, phone: str) -> None:
        with tenant_context(a.id):
            assert authenticate(None, phone=phone, password=TEST_PASSWORD) is None

    def test_no_business_no_sign_in(self, a: Business) -> None:
        with tenant_context(a.id):
            UserFactory(phone=PHONE)
        assert authenticate(None, phone=PHONE, password=TEST_PASSWORD) is None

    def test_suspended_users_still_authenticate_so_login_can_explain(self, a: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory(phone=PHONE, status=User.Status.SUSPENDED)
            assert BusinessPhoneBackend().authenticate(None, PHONE, TEST_PASSWORD) == user

    def test_get_user_is_scoped(self, a: Business, b: Business) -> None:
        with tenant_context(a.id):
            user = UserFactory()
            assert BusinessPhoneBackend().get_user(user.pk) == user
        with tenant_context(b.id):
            assert BusinessPhoneBackend().get_user(user.pk) is None
        assert BusinessPhoneBackend().get_user(user.pk) is None


class TestPasswordRules:
    """Exactly the X-13 checklist."""

    @pytest.mark.parametrize("password", ["short1!", "12345678901", "password123"])
    def test_refused(self, password: str) -> None:
        with pytest.raises(ValidationError):
            password_validation.validate_password(password)

    def test_accepted(self) -> None:
        password_validation.validate_password(TEST_PASSWORD)
