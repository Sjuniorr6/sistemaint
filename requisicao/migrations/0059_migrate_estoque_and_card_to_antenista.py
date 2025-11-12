"""Migração de dados: cria registros Antenista a partir de nomes existentes em estoque_antenista
e atualiza referências em estoque_antenista e antenista_CARD para apontarem para Antenista.

Esta migration é defensiva: tenta lidar com vários formatos de dados (texto ou FK numérica)
e pode ser executada após a migração de schema que transforma os campos `nome` em FK para
`requisicao.Antenista`.

Revisar antes de aplicar. Não altera o esquema, apenas dados.
"""
from django.db import migrations, transaction
import django.db


def forwards(apps, schema_editor):
    Antenista = apps.get_model('requisicao', 'Antenista')
    Estoque = apps.get_model('requisicao', 'estoque_antenista')
    Card = apps.get_model('requisicao', 'antenista_CARD')

    # Inspect the DB schema to ensure the `nome` column exists on the
    # `requisicao_antenista_card` table; if not, skip this data migration
    # because the schema migration hasn't run yet.
    try:
        cursor = schema_editor.connection.cursor()
        cursor.execute("PRAGMA table_info('requisicao_antenista_card')")
        cols = [r[1] for r in cursor.fetchall()]
        if 'nome' not in cols:
            return
    except Exception:
        # If any error occurs (non-sqlite DB or other issue), abort the data
        # migration conservatively.
        return

    # Criar Antenista para cada nome presente em estoque_antenista.nome (quando for string)
    with transaction.atomic():
        # Primeiro, coletar todos os nomes possíveis do estoque
        nomes = set()
        for e in Estoque.objects.all():
            try:
                val = getattr(e, 'nome')
            except Exception:
                val = None
            # Se for objeto relacionado (FK) extrai seu nome quando possível
            if val is None:
                continue
            # Se val for int/PK (referenciando outro model), tente resolver para string
            if isinstance(val, int):
                # tentar buscar o registro referenciado e obter seu atributo 'nome' se existir
                try:
                    ref = Estoque.objects.filter(pk=val).first()
                    if ref:
                        nomes.add(str(getattr(ref, 'nome', '')).strip())
                except Exception:
                    pass
            else:
                nomes.add(str(val).strip())

        # Também verificar names que possam existir apenas em Card (caso haja dados não replicados)
        for c in Card.objects.all():
            try:
                val = getattr(c, 'nome')
            except Exception:
                val = None
            if val is None:
                continue
            if isinstance(val, int):
                try:
                    ref = Estoque.objects.filter(pk=val).first()
                    if ref:
                        nomes.add(str(getattr(ref, 'nome', '')).strip())
                except Exception:
                    pass
            else:
                nomes.add(str(val).strip())

        # Criar Antenista para cada nome coletado
        created_map = {}
        for nome in sorted(n for n in nomes if n):
            antenista_obj, created = Antenista.objects.get_or_create(nome=nome, defaults={'estado': ''})
            created_map[nome] = antenista_obj

        # Atualizar registros de Estoque: quando nome for texto, trocar para FK; quando nome for FK para outro
        for e in Estoque.objects.all():
            try:
                val = getattr(e, 'nome')
            except Exception:
                val = None
            target = None
            if val is None:
                continue
            if isinstance(val, int):
                # val pode ser PK referenciando um estoque anterior; tentar resolver
                try:
                    ref = Estoque.objects.filter(pk=val).first()
                    if ref:
                        candidate_name = str(getattr(ref, 'nome', '')).strip()
                        target = created_map.get(candidate_name)
                except Exception:
                    target = None
            else:
                candidate_name = str(val).strip()
                target = created_map.get(candidate_name)

            if target:
                try:
                    e.nome = target
                    e.save()
                except Exception:
                    # se não for possível atribuir (campo ainda texto), ignorar — será tratado pela migration de schema
                    pass

        # Atualizar registros de Card: mapear nome atual (texto ou FK para Estoque) para Antenista
        for c in Card.objects.all():
            try:
                val = getattr(c, 'nome')
            except Exception:
                val = None
            target = None
            if val is None:
                continue
            if isinstance(val, int):
                # valor pode ser fk para estoque_antenista
                try:
                    ref = Estoque.objects.filter(pk=val).first()
                    if ref:
                        candidate_name = str(getattr(ref, 'nome', '')).strip()
                        target = created_map.get(candidate_name)
                except Exception:
                    target = None
            else:
                candidate_name = str(val).strip()
                target = created_map.get(candidate_name)

            if target:
                try:
                    c.nome = target
                    c.save()
                except Exception:
                    # se não for possível atribuir agora, ignorar — será tratado pela migration de schema
                    pass

    
def reverse(apps, schema_editor):
    # Esta operação é difícil de reverter automaticamente (criou registros Antenista e reatribuíu FKs).
    # Podemos optar por não reverter nada aqui.
    return


class Migration(migrations.Migration):

    dependencies = [
        # Esta migration de dados deve rodar APÓS a migration de schema que cria o modelo Antenista
        ('requisicao', '0060_antenista_alter_antenista_card_nome_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
