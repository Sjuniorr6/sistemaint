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
from iscas.models.operacao import Solicitacao
from iscas.services.geo import geocodificar_entidade
from iscas.services.solicitacao import resolver_coordenada_de_entrega

#: Intervalo entre requisições — exigência da política do Nominatim.
INTERVALO_SEGUNDOS = 1.1

_MODELOS = {"agente": Agente, "cliente": Cliente, "deposito": Deposito}

#: A entrega da solicitação também geocodifica, e também pode falhar. Sem isto
#: um pedido cuja entrega o Nominatim não achou ficaria fora da busca por
#: agentes próximos para sempre, à espera de alguém posicionar o pin à mão.
_ALVO_SOLICITACAO = "solicitacao"


class Command(BaseCommand):
    help = "Geocodifica cadastros com coordenada pendente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--modelo",
            choices=sorted([*_MODELOS, _ALVO_SOLICITACAO]),
            help="Processa só um tipo de registro. Por padrão, todos.",
        )
        parser.add_argument(
            "--limite", type=int, default=0, help="Máximo de registros a processar."
        )

    def handle(self, *args, **options):
        alvo = options["modelo"]
        escolhidos = {alvo: _MODELOS[alvo]} if alvo in _MODELOS else (
            {} if alvo else _MODELOS
        )
        limite = options["limite"]
        processados = sucesso = 0

        for nome, Modelo in escolhidos.items():
            # Pendentes de verdade: sem coordenada, sem ajuste manual E com
            # endereço para geocodificar. Cliente sem endereço — caso legítimo
            # desde que o endereço virou opcional — nunca vai render
            # coordenada; incluí-lo faria o command bater no Nominatim toda
            # execução, para sempre, sem resultado possível.
            pendentes = (
                Modelo.objects.filter(latitude__isnull=True)
                .exclude(geo_origem=GeoOrigem.MANUAL)
                .exclude(logradouro="", cidade="", cep="")
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

        if alvo in (None, _ALVO_SOLICITACAO):
            pendentes = (
                Solicitacao.objects.filter(entrega_latitude__isnull=True)
                .exclude(entrega_geo_origem=GeoOrigem.MANUAL)
                .exclude(entrega_logradouro="", entrega_cidade="")
            )
            if limite:
                pendentes = pendentes[: limite - processados]

            for solicitacao in pendentes:
                if limite and processados >= limite:
                    break
                if resolver_coordenada_de_entrega(solicitacao):
                    sucesso += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  entrega da solicitação {solicitacao.pk}: "
                            f"{solicitacao.entrega_latitude}, "
                            f"{solicitacao.entrega_longitude}"
                        )
                    )
                else:
                    self.stdout.write(
                        f"  entrega da solicitação {solicitacao.pk}: sem resultado."
                    )
                processados += 1
                time.sleep(INTERVALO_SEGUNDOS)

        if not processados:
            self.stdout.write(self.style.SUCCESS("Nenhum registro pendente."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"{sucesso} de {processados} registro(s) geocodificado(s)."
            )
        )
