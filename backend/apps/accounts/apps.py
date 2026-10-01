from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Registers the OpenAPI description of the bearer-token scheme.
        from apps.accounts import schema  # noqa: F401
