from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    label = "catalog"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Registers the outbox handler that gives a new business the template list,
        # and the price list section of GET /business/config.
        from apps.catalog import handlers  # noqa: F401
        from apps.catalog.config import SECTION
        from apps.tenancy.config_sections import register_config_section

        register_config_section(SECTION)
