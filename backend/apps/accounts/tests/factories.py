"""Factories for accounts. Business users must be created inside tenant_context()."""

import factory
from django.utils import timezone

from apps.accounts.models import Role, User, UserSession
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
