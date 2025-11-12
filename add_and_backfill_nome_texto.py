import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()

def has_column(table, column):
    cur.execute(f"PRAGMA table_info('{table}')")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

# Add column if missing
for table in ['requisicao_antenista_card', 'requisicao_estoque_antenista']:
    if not has_column(table, 'nome_texto'):
        print(f"Adding column nome_texto to {table}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN nome_texto TEXT")
        conn.commit()
    else:
        print(f"Table {table} already has nome_texto")

# Backfill antenista_card.nome_texto from antenista if possible
print('\nBackfilling requisicao_antenista_card.nome_texto ...')
cur.execute("SELECT id, nome_id, nome_texto FROM requisicao_antenista_card")
rows = cur.fetchall()
updated = 0
for rid, nome_id, nome_texto in rows:
    if nome_texto is not None and str(nome_texto).strip() != '':
        continue
    value = None
    if nome_id is None:
        value = None
    else:
        # try numeric id
        try:
            nid = int(str(nome_id).strip())
            cur.execute("SELECT nome FROM requisicao_antenista WHERE id = ?", (nid,))
            r = cur.fetchone()
            if r:
                value = r[0]
        except Exception:
            # treat as text
            value = str(nome_id).strip()
    if value:
        cur.execute("UPDATE requisicao_antenista_card SET nome_texto = ? WHERE id = ?", (value, rid))
        updated += 1
conn.commit()
print(f"Updated {updated} rows in requisicao_antenista_card")

# Backfill estoque_antenista.nome_texto
print('\nBackfilling requisicao_estoque_antenista.nome_texto ...')
cur.execute("SELECT id, nome, nome_texto FROM requisicao_estoque_antenista")
rows = cur.fetchall()
updated2 = 0
for rid, nome, nome_texto in rows:
    if nome_texto is not None and str(nome_texto).strip() != '':
        continue
    value = None
    if nome is None:
        value = None
    else:
        s = str(nome).strip()
        # try numeric
        if s.isdigit():
            cur.execute("SELECT nome FROM requisicao_antenista WHERE id = ?", (int(s),))
            r = cur.fetchone()
            if r:
                value = r[0]
        else:
            value = s
    if value:
        cur.execute("UPDATE requisicao_estoque_antenista SET nome_texto = ? WHERE id = ?", (value, rid))
        updated2 += 1
conn.commit()
print(f"Updated {updated2} rows in requisicao_estoque_antenista")

conn.close()
print('\nDone. Re-run the Django view/page now.')
