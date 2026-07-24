# Backfill das passagens por setor (SLA) para os chamados JÁ existentes.
#
# O log `ChamadoEvento` é append-only e guarda, de cada transição, o autor e o
# `criado_em` — dá para reconstruir por onde o chamado passou e quando. Como não
# havia registro de ACEITE no passado, as passagens históricas nascem com
# `aceito_em = chegou_em` (espera zero por definição): assim elas não travam o
# fluxo (o aceite é obrigatório para agir) nem inventam tempo de espera.
from django.db import migrations

# Espelha chamados.services._SETOR_POR_STATUS (não importável em migration).
_SETOR_POR_STATUS = {
    "ABERTO": "QUALITY",
    "ENCAMINHADO": "INTELIGENCIA",
    "EXPEDICAO": "EXPEDICAO",
    "LABORATORIO": "LABORATORIO",
    "COMERCIAL": "COMERCIAL",
}


def _backfill(apps, schema_editor):
    Chamado = apps.get_model("chamados", "Chamado")
    PassagemSetor = apps.get_model("chamados", "PassagemSetor")

    for chamado in Chamado.objects.all():
        if chamado.passagens.exists():
            continue  # idempotente: não duplica se rodar de novo

        eventos = list(chamado.eventos.order_by("criado_em", "id"))
        if not eventos:
            continue

        passagem_atual = None
        for evento in eventos:
            # Bloquear/Reabrir não trocam de setor: seguem na mesma passagem.
            if evento.acao in ("BLOQUEAR", "REABRIR"):
                continue

            setor_origem = _SETOR_POR_STATUS.get(evento.estado_origem or "")
            setor_destino = _SETOR_POR_STATUS.get(evento.estado_destino or "")

            # Abertura (sem estado de origem): apenas INAUGURA a passagem inicial.
            if passagem_atual is None and not setor_origem:
                if setor_destino:
                    passagem_atual = PassagemSetor.objects.create(
                        chamado=chamado,
                        setor=setor_destino,
                        chegou_em=evento.criado_em,
                        aceito_em=evento.criado_em,
                        aceito_por_id=evento.autor_id,
                    )
                continue

            if setor_origem == setor_destino:
                continue  # não trocou de setor

            # Defensivo: log antigo sem o evento de abertura mapeável.
            if passagem_atual is None and setor_origem:
                passagem_atual = PassagemSetor.objects.create(
                    chamado=chamado,
                    setor=setor_origem,
                    chegou_em=evento.criado_em,
                    aceito_em=evento.criado_em,
                    aceito_por_id=evento.autor_id,
                )

            # Fecha a passagem corrente e abre a do destino (quando houver).
            if passagem_atual is not None:
                passagem_atual.finalizado_em = evento.criado_em
                passagem_atual.finalizado_por_id = evento.autor_id
                passagem_atual.acao_saida = evento.acao
                passagem_atual.save()
                passagem_atual = None

            if setor_destino:
                passagem_atual = PassagemSetor.objects.create(
                    chamado=chamado,
                    setor=setor_destino,
                    chegou_em=evento.criado_em,
                    aceito_em=evento.criado_em,
                    aceito_por_id=evento.autor_id,
                )


def _reverter(apps, schema_editor):
    PassagemSetor = apps.get_model("chamados", "PassagemSetor")
    PassagemSetor.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0014_passagem_setor_sla"),
    ]

    operations = [
        migrations.RunPython(_backfill, _reverter),
    ]
