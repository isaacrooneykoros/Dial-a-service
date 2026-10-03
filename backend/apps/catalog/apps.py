from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    label = "catalog"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Registers the outbox handler that gives a new business the template list.
        from apps.catalog import handlers  # noqa: F401
