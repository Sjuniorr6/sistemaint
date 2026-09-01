"""Reprocessa cadastros que ficaram sem coordenada (ISC-RF-02, ISC-ADR-11).

Geocodificação falha acontece: o Nominatim cai, o timeout de 3s estoura, o
endereço vem torto. O cadastro grava mesmo assim, marcado como PENDENTE, e este
command reprocessa em lote.

Respeita o limite de 1 requisição por segundo da política de uso do Nominatim —
por isso o throttle não é opcional.

Uso:
    python manage.py geocodificar_pendentes
    python manage.py geocodificar_pendentes --modelo agente --limite 50
"""
import time

from django.core.management.base import BaseCommand

from iscas.enums import GeoOrigem
from iscas.models.cadastro import Agente, Cliente, Deposito
from iscas.services.geo import geocodificar_entidade

#: Intervalo entre requisições — exigência da política do Nominatim.
INTERVALO_SEGUNDOS = 1.1

_MODELOS = {"agente": Agente, "cliente": Cliente, "deposito": Deposito}


class Command(BaseCommand):
    help = "Geocodifica cadastros com coordenada pendente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--modelo",
            choices=sorted(_MODELOS),
            help="Processa só um tipo de cadastro. Por padrão, todos.",
        )
        parser.add_argument(
            "--limite", type=int, default=0, help="Máximo de registros a processar."
        )

    def handle(self, *args, **options):
        escolhidos = (
            {options["modelo"]: _MODELOS[options["modelo"]]}
            if options["modelo"]
            else _MODELOS
        )
        limite = options["limite"]
        processados = sucesso = 0

        for nome, Modelo in escolhidos.items():
            # Pendentes de verdade: sem coordenada e sem ajuste manual. Pin
            # manual nunca é reprocessado (ISC-RF-03).
            pendentes = Modelo.objects.filter(latitude__isnull=True).exclude(
                geo_origem=GeoOrigem.MANUAL
            )
            if limite:
                pendentes = pendentes[: limite - processados]

            for entidade in pendentes:
                if limite and processados >= limite:
                    break
                if geocodificar_entidade(entidade):
                    sucesso += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  {nome} {entidade.pk}: "
                            f"{entidade.latitude}, {entidade.longitude}"
                        )
                    )
                else:
                    self.stdout.write(f"  {nome} {entidade.pk}: sem resultado.")
                processados += 1
                time.sleep(INTERVALO_SEGUNDOS)

        if not processados:
            self.stdout.write(self.style.SUCCESS("Nenhum cadastro pendente."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"{sucesso} de {processados} cadastro(s) geocodificado(s)."
            )
        )
