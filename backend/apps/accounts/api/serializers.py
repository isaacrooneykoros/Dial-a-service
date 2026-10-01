"""Shapes for the accounts API. Validation of shape only (CLAUDE.md section 6.6)."""

from typing import Any

from rest_framework import serializers

from apps.accounts.models import Role, User


class LoginSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=32, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RightsSerializer(serializers.Serializer[Any]):
    accept_cash = serializers.BooleanField(source="can_accept_cash")
    give_discounts = serializers.BooleanField(source="can_give_discounts")
    correct_prices = serializers.BooleanField(source="can_correct_prices")


class MeSerializer(serializers.Serializer[User]):
    """The signed-in person. Read-only; a plain serializer so no queries run to build it."""

    id = serializers.UUIDField(read_only=True)
    phone = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    role = serializers.ChoiceField(choices=Role.choices, read_only=True)
    language = serializers.ChoiceField(choices=User.Language.choices, read_only=True)
    is_phone_verified = serializers.BooleanField(read_only=True)
    rights = RightsSerializer(source="*", read_only=True)
    has_pin = serializers.SerializerMethodField()

    def get_has_pin(self, user: User) -> bool:
        return bool(user.pin_hash)


class AccessSerializer(serializers.Serializer[Any]):
    access = serializers.CharField(help_text="Access token (15 minutes). Keep it in memory only.")


class LoginResponseSerializer(AccessSerializer):
    user = MeSerializer()


class BranchSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
