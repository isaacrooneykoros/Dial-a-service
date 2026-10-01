"""Session revocation services (M1 T05b; used by password reset, deactivation and A-42)."""

import pytest

from apps.accounts.models import UserSession
from apps.accounts.services.auth import revoke_all_sessions, revoke_session
from apps.accounts.tests.factories import UserFactory, UserSessionFactory
from apps.core.models import AuditLog
from apps.core.tenant_context import tenant_context
from apps.tenancy.tests.factories import BusinessFactory

pytestmark = pytest.mark.django_db


def test_sign_out_everywhere_except_the_current_session() -> None:
    business = BusinessFactory()
    with tenant_context(business.id):
        user = UserFactory()
        keep, other1, other2 = (UserSessionFactory(user=user) for _ in range(3))
        someone_else = UserSessionFactory()
        assert revoke_all_sessions(user, reason="password_changed", keep=keep) == 2
        live = set(UserSession.objects.filter(revoked_at__isnull=True).values_list("pk", flat=True))
        assert live == {keep.pk, someone_else.pk}
        assert AuditLog.objects.filter(action="auth.session_revoked").count() == 2
        assert str(other1) == f"password session {other1.pk}"
        assert other2.pk not in live


def test_sign_out_everywhere_without_keeping_one() -> None:
    business = BusinessFactory()
    with tenant_context(business.id):
        user = UserFactory()
        UserSessionFactory(user=user)
        assert revoke_all_sessions(user, reason="deactivated") == 1


def test_revoking_twice_keeps_the_first_reason() -> None:
    business = BusinessFactory()
    with tenant_context(business.id):
        session = UserSessionFactory()
        revoke_session(session, reason="logout")
        revoke_session(session, reason="other")
        session.refresh_from_db()
        assert session.revoke_reason == "logout"
        assert AuditLog.objects.filter(action="auth.session_revoked").count() == 1
