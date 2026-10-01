from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Registers the outbox handler that sends notifications.
        from apps.notifications import handlers  # noqa: F401
