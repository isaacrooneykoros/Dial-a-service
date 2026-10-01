"""Factories for accounts. Business users must be created inside tenant_context()."""

from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.models import (
    ConsentRecord,
    Invitation,
    InvitationBranch,
    PhoneOTP,
    Role,
    User,
    UserSession,
)
from apps.accounts.tokens import REFRESH_TOKEN_LIFETIME, new_refresh_token

TEST_PASSWORD = "correct-horse-42"


class UserFactory(factory.django.DjangoModelFactory[User]):
    class Meta:
        model = User
        skip_postgeneration_save = True

    phone = factory.Sequence(lambda n: f"+2547{n:08d}")
    first_name = "Wanjiru"
    last_name = factory.Sequence(lambda n: f"Kamau{n}")
    role = Role.STAFF
    is_phone_verified = True
    password = factory.django.Password(TEST_PASSWORD)


class UserSessionFactory(factory.django.DjangoModelFactory[UserSession]):
    class Meta:
        model = UserSession

    user = factory.SubFactory(UserFactory)
    last_seen_at = factory.LazyFunction(timezone.now)
    expires_at = factory.LazyFunction(lambda: timezone.now() + REFRESH_TOKEN_LIFETIME)
    refresh_hash = factory.LazyFunction(lambda: new_refresh_token()[1])


class PhoneOTPFactory(factory.django.DjangoModelFactory[PhoneOTP]):
    class Meta:
        model = PhoneOTP

    phone = "+254712345678"
    purpose = PhoneOTP.Purpose.PASSWORD_RESET
    code_hash = factory.LazyFunction(lambda: "0" * 64)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))


class InvitationFactory(factory.django.DjangoModelFactory[Invitation]):
    class Meta:
        model = Invitation

    phone = factory.Sequence(lambda n: f"+2541{n:08d}")
    first_name = "Achieng"
    last_name = "Otieno"
    role = Role.STAFF
    invited_by = factory.SubFactory(UserFactory, role=Role.OWNER)
    token_hash = factory.Sequence(lambda n: f"{n:064d}")
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))


class InvitationBranchFactory(factory.django.DjangoModelFactory[InvitationBranch]):
    class Meta:
        model = InvitationBranch

    invitation = factory.SubFactory(InvitationFactory)
    branch = factory.SubFactory("apps.branches.tests.factories.BranchFactory")


class ConsentRecordFactory(factory.django.DjangoModelFactory[ConsentRecord]):
    class Meta:
        model = ConsentRecord

    user = factory.SubFactory(UserFactory)
    document = "terms"
    version = "1"
