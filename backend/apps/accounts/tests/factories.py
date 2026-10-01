"""Factories for accounts. Business users must be created inside tenant_context()."""

import factory

from apps.accounts.models import Role, User

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
