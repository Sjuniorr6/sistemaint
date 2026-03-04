from django.db import models
from django.conf import settings
from decimal import Decimal
import datetime

DIAS_SEMANA_PT = {
    0: 'Segunda-feira',
    1: 'Terça-feira',
    2: 'Quarta-feira',
    3: 'Quinta-feira',
    4: 'Sexta-feira',
    5: 'Sábado',
    6: 'Domingo',
}


class horas(models.Model):
    STATUS_CHOICES = [
        ('Pendente', 'Pendente'),
        ('Aprovado', 'Aprovado'),
    ]

    status_choice = models.CharField(
        choices=STATUS_CHOICES,
        max_length=50,
        null=True,
        blank=True,
    )

    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    comprovante1 = models.ImageField(upload_to='imagens/', null=True, blank=True)
    comprovante2 = models.ImageField(upload_to='imagens/', null=True, blank=True)

    hora_inicial = models.DateTimeField(null=True, blank=True, verbose_name='Hora Inicial')
    hora_final   = models.DateTimeField(null=True, blank=True, verbose_name='Hora Final')

    motivo = models.CharField(max_length=50, null=True, blank=True)

    total = models.CharField(max_length=10, null=True, blank=True)
    total_de_horas = models.CharField(max_length=50, null=True, blank=True)

    # Novos campos
    solicitante = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Solicitante da Hora Extra',
    )
    data_solicitacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Horário da Solicitação',
    )

    # ------------------------------------------------------------------ #
    # Propriedades auxiliares – dia da semana em português                #
    # ------------------------------------------------------------------ #
    @property
    def dia_semana_inicial(self) -> str:
        """Retorna o dia da semana da hora_inicial em português."""
        if self.hora_inicial:
            return DIAS_SEMANA_PT.get(self.hora_inicial.weekday(), '')
        return ''

    @property
    def dia_semana_final(self) -> str:
        """Retorna o dia da semana da hora_final em português."""
        if self.hora_final:
            return DIAS_SEMANA_PT.get(self.hora_final.weekday(), '')
        return ''

    def save(self, *args, **kwargs):
        if self.hora_inicial and self.hora_final and self.hora_final > self.hora_inicial:
            diff = self.hora_final - self.hora_inicial
            total_seconds = int(diff.total_seconds())

            horas_ = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60

            self.total = f"{horas_:02d}:{minutos:02d}"
        else:
            self.total = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Horas extras - {self.funcionario}'

from datetime import datetime, time
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import horas  # ajuste se seu import for diferente


def _format_seconds_to_hhmm(total_seconds: int) -> str:
    """Converte segundos em string HH:MM."""
    if total_seconds <= 0:
        return "00:00"

    total_minutes = total_seconds // 60
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


@login_required
def consultar_horas(request):
    """
    Lista registros de horas e calcula o total somado por funcionário,
    devolvendo no formato esperado pelo template: employee_data.
    """
    data_inicial = request.GET.get("data_inicial")
    data_final = request.GET.get("data_final")

    qs = (
        horas.objects
        .select_related("funcionario")
        .all()
        .order_by("funcionario__username", "hora_inicial")
    )

    # ==========================
    # FILTRO POR DATA (GET)
    # ==========================
    # Aqui o seu input é type="date" (YYYY-MM-DD)
    # Então precisamos montar um intervalo datetime para pegar o dia inteiro.
    if data_inicial:
        dt_ini = timezone.make_aware(
            datetime.combine(datetime.strptime(data_inicial, "%Y-%m-%d").date(), time.min)
        )
        qs = qs.filter(hora_inicial__gte=dt_ini)

    if data_final:
        dt_fim = timezone.make_aware(
            datetime.combine(datetime.strptime(data_final, "%Y-%m-%d").date(), time.max)
        )
        qs = qs.filter(hora_final__lte=dt_fim)

    # ==========================
    # AGRUPAR POR FUNCIONÁRIO
    # ==========================
    employees_map = {}

    for registro in qs:
        if not registro.funcionario:
            continue  # segurança, caso exista registro sem funcionário

        user_id = registro.funcionario_id

        if user_id not in employees_map:
            employees_map[user_id] = {
                "funcionario": (
                    registro.funcionario.get_full_name().strip()
                    if registro.funcionario.get_full_name()
                    else registro.funcionario.username
                ),
                "records": [],
                "total_seconds": 0,
            }

        # Guarda o registro para o template
        employees_map[user_id]["records"].append(registro)

        # Soma pelo intervalo real (mais confiável do que string "total")
        if registro.hora_inicial and registro.hora_final and registro.hora_final > registro.hora_inicial:
            diff = registro.hora_final - registro.hora_inicial
            employees_map[user_id]["total_seconds"] += int(diff.total_seconds())

    # ==========================
    # MONTAR LISTA FINAL
    # ==========================
    employee_data = []
    for _, payload in employees_map.items():
        payload["total_de_horas"] = _format_seconds_to_hhmm(payload["total_seconds"])
        # remove o campo interno se quiser deixar limpo
        payload.pop("total_seconds", None)
        employee_data.append(payload)

    return render(request, "consultar_horas.html", {"employee_data": employee_data})
