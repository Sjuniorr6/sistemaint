from django.apps import AppConfig


class AcompanhamentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "acompanhamentos"

    def ready(self):
        from . import signals
