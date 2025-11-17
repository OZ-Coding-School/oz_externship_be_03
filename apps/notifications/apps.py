from django.apps import AppConfig


class AppNotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"

    def ready(self) -> None:
        import apps.notifications.signals
