from django.apps import AppConfig


class EnterpriseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enterprise"
    verbose_name = "MyDoctor Enterprise Platform"

    def ready(self):
        from . import signals  # noqa: F401
