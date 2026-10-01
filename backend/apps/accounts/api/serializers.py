"""Shapes for the accounts API. Validation of shape only (CLAUDE.md section 6.6)."""

from typing import Any

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.accounts.phones import InvalidPhoneError, normalize_ke_phone


class LoginSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=32, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


def validate_ke_phone(value: str) -> str:
    try:
        return normalize_ke_phone(value)
    except InvalidPhoneError as exc:
        raise serializers.ValidationError(
            _("Enter a Kenyan mobile number, like 0712 345 678."), code=exc.code
        ) from exc


def validate_new_password(value: str) -> str:
    try:
        password_validation.validate_password(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class PhoneSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value: str) -> str:
        return validate_ke_phone(value)


class VerifyCodeSerializer(PhoneSerializer):
    code = serializers.RegexField(r"^\d{6}$", max_length=6)


class ResetConfirmSerializer(serializers.Serializer[Any]):
    reset_token = serializers.CharField(max_length=128)
    password = serializers.CharField(
        max_length=128, trim_whitespace=False, validators=[validate_new_password]
    )


class PasswordChangeSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(
        max_length=128, trim_whitespace=False, validators=[validate_new_password]
    )


class MessageSerializer(serializers.Serializer[Any]):
    message = serializers.CharField()


class ResetTokenSerializer(serializers.Serializer[Any]):
    reset_token = serializers.CharField(help_text="Single use, valid for 10 minutes.")


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
