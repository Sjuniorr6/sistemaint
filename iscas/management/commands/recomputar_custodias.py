"""Reconstrói os ponteiros de projeção da Unidade a partir do livro-razão.

É a mitigação prometida no ISC-ADR-04: `custodia_atual`, `custodia_desde` e
`ultima_movimentacao` são cache de algo que o livro já sabe. Se divergirem —
por bug, migração de dados ou intervenção manual no banco —, este command
recalcula tudo. O livro continua sendo a autoridade.

Uso:
    python manage.py recomputar_custodias            # aplica as correções
    python manage.py recomputar_custodias --dry-run  # só relata divergências
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from iscas.models.custodia import MovimentacaoUnidade, Unidade


class Command(BaseCommand):
    help = "Reconstrói os ponteiros de custódia das unidades a partir do livro-razão."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas relata as divergências, sem gravar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # O último lançamento de cada unidade define onde ela está. Ordenamos
        # por (ocorrido_em, id) e deixamos a última escrita vencer — o mesmo
        # critério que `registrar_movimentacao` aplica ao gravar.
        esperado = {}
        linhas = (
            MovimentacaoUnidade.objects.select_related("movimentacao")
            .order_by("movimentacao__ocorrido_em", "movimentacao_id")
        )
        for linha in linhas.iterator(chunk_size=2000):
            movimentacao = linha.movimentacao
            esperado[linha.unidade_id] = (
                movimentacao.destino_id,
                movimentacao.ocorrido_em,
                movimentacao.pk,
            )

        divergentes = []
        sem_lancamento = []

        for unidade in Unidade.objects.all().iterator(chunk_size=2000):
            if unidade.pk not in esperado:
                sem_lancamento.append(unidade)
                continue
            destino, desde, movimentacao_id = esperado[unidade.pk]
            atual = (
                unidade.custodia_atual_id,
                unidade.custodia_desde,
                unidade.ultima_movimentacao_id,
            )
            if atual != (destino, desde, movimentacao_id):
                unidade.custodia_atual_id = destino
                unidade.custodia_desde = desde
                unidade.ultima_movimentacao_id = movimentacao_id
                divergentes.append(unidade)

        if sem_lancamento:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(sem_lancamento)} unidade(s) sem nenhum lançamento no "
                    "livro — não deveria acontecer, toda unidade nasce com uma "
                    "movimentação de entrada. Verifique: "
                    + ", ".join(u.identificador for u in sem_lancamento[:10])
                )
            )

        if not divergentes:
            self.stdout.write(
                self.style.SUCCESS("Todos os ponteiros conferem com o livro-razão.")
            )
            return

        for unidade in divergentes[:20]:
            self.stdout.write(f"  {unidade.identificador} → custódia {unidade.custodia_atual_id}")
        if len(divergentes) > 20:
            self.stdout.write(f"  … e mais {len(divergentes) - 20}.")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(divergentes)} divergência(s) encontrada(s). "
                    "Nada gravado (--dry-run)."
                )
            )
            return

        with transaction.atomic():
            Unidade.objects.bulk_update(
                divergentes,
                ["custodia_atual", "custodia_desde", "ultima_movimentacao"],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(f"{len(divergentes)} ponteiro(s) reconstruído(s).")
        )
