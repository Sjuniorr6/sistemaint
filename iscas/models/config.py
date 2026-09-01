"""Parâmetros globais e cache de geocodificação.

`ConfiguracaoIscas` é singleton editável no /admin pelo Superusuário GSInt —
raio padrão, prazo de alerta de retornável, provedor de tiles. Trocar o
provedor de mapa é mudança de configuração, não de código (ISC-ADR-10).
"""
from django.core.exceptions import ValidationError
from django.db import models


class ConfiguracaoIscas(models.Model):
    """Singleton de parâmetros do app. Sempre acessado por `carregar()`."""

    raio_padrao_km = models.PositiveIntegerField(
        default=50, verbose_name="Raio padrão de busca (km)"
    )
    dias_alerta_retornavel = models.PositiveIntegerField(
        default=90,
        verbose_name="Alerta de retornável em posse (dias)",
        help_text="Retornável com cliente há mais dias que isto é sinalizado (ISC-RF-33).",
    )
    saldo_minimo_alerta = models.PositiveIntegerField(
        default=5,
        verbose_name="Saldo mínimo antes do alerta",
        help_text="Agente com saldo abaixo disto aparece no dashboard (ISC-RF-38).",
    )
    horas_alerta_em_rota = models.PositiveIntegerField(
        default=24,
        verbose_name="Alerta de atribuição em rota (horas)",
        help_text="Atribuição parada em EM_ROTA por mais que isto vira pendência.",
    )
    tiles_url = models.CharField(
        max_length=300,
        default="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        verbose_name="URL dos tiles",
    )
    tiles_atribuicao = models.CharField(
        max_length=300,
        default="© OpenStreetMap contributors",
        verbose_name="Atribuição dos tiles",
        help_text="Obrigatória pela política de uso do OpenStreetMap.",
    )

    class Meta:
        verbose_name = "Configuração do Iscas Fast"
        verbose_name_plural = "Configuração do Iscas Fast"

    def __str__(self):
        return "Configuração do Iscas Fast"

    def clean(self):
        super().clean()
        if not self.pk and type(self).objects.exists():
            raise ValidationError("Já existe uma configuração; edite a existente.")

    def save(self, *args, **kwargs):
        """Força o singleton: sempre PK 1."""
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("A configuração do Iscas Fast não pode ser removida.")

    @classmethod
    def carregar(cls):
        """Devolve a configuração, criando-a com os defaults se ainda não existir."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class GeocodeCache(models.Model):
    """Endereços já geocodificados, para não reconsultar o Nominatim.

    A política de uso do OSM limita a 1 requisição por segundo; o cache é o que
    torna o cadastro do dia a dia viável (ISC-ADR-11).
    """

    endereco_hash = models.CharField(
        max_length=64, unique=True, verbose_name="Hash do endereço"
    )
    endereco_normalizado = models.CharField(
        max_length=300, verbose_name="Endereço normalizado"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitude")
    provedor = models.CharField(max_length=50, default="nominatim", verbose_name="Provedor")
    consultado_em = models.DateTimeField(auto_now_add=True, verbose_name="Consultado em")

    class Meta:
        verbose_name = "Cache de geocodificação"
        verbose_name_plural = "Cache de geocodificação"
        ordering = ["-consultado_em"]

    def __str__(self):
        return self.endereco_normalizado
