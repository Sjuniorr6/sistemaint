import sqlite3
import os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Check if column exists
cur.execute("PRAGMA table_info('requisicao_estoque_antenista')")
cols = [r[1] for r in cur.fetchall()]
print('Current columns in requisicao_estoque_antenista:', cols)
if 'nome_id' in cols:
    print('Column nome_id already present; exiting.')
else:
    print('Adding column nome_id INTEGER')
    cur.execute("ALTER TABLE requisicao_estoque_antenista ADD COLUMN nome_id INTEGER")
    conn.commit()

# Helper to find or create antenna
def find_or_create_antenista(nome):
    nome_clean = (nome or '').strip()
    if not nome_clean:
        return None
    # try exact match first
    cur.execute("SELECT id FROM requisicao_antenista WHERE nome = ?", (nome_clean,))
    r = cur.fetchone()
    if r:
        return r[0]
    # try case-insensitive
    cur.execute("SELECT id FROM requisicao_antenista WHERE lower(nome) = lower(?)", (nome_clean,))
    r = cur.fetchone()
    if r:
        return r[0]
    # create new antenista
    cur.execute("INSERT INTO requisicao_antenista (nome, estado) VALUES (?, ?)", (nome_clean, ''))
    conn.commit()
    return cur.lastrowid

# Backfill nome_id
cur.execute("SELECT id, nome FROM requisicao_estoque_antenista")
rows = cur.fetchall()
print('Rows to process in estoque_antenista:', len(rows))
updated = 0
for rid, nome in rows:
    nid = find_or_create_antenista(nome)
    if nid:
        cur.execute("UPDATE requisicao_estoque_antenista SET nome_id = ? WHERE id = ?", (nid, rid))
        updated += 1

conn.commit()
print('Updated rows with nome_id:', updated)
conn.close()
