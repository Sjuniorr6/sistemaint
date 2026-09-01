from django.apps import AppConfig


class IscasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'iscas'
    verbose_name = 'Iscas Fast'

    def ready(self):
        # Signals criam a Custodia junto com Agente/Cliente/Deposito (ISC-ADR-03).
        from iscas import signals  # noqa: F401
