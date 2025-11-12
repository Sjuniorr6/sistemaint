import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Helper to ensure Antenista exists, return its id
def ensure_antenista(nome):
    n = nome.strip()
    if not n:
        return None
    cur.execute("SELECT id FROM requisicao_antenista WHERE nome = ?", (n,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO requisicao_antenista (nome, estado) VALUES (?, '')", (n,))
    conn.commit()
    return cur.lastrowid

# Find rows in antenista_card where nome_id is not null but invalid
print('Scanning requisicao_antenista_card for invalid nome_id entries...')
cur.execute("SELECT id, nome_id FROM requisicao_antenista_card WHERE nome_id IS NOT NULL")
rows = cur.fetchall()
updated = 0
for rid, raw in rows:
    if raw is None:
        continue
    s = str(raw).strip()
    # if it's purely numeric, check referential integrity
    if s.isdigit():
        cur.execute("SELECT 1 FROM requisicao_antenista WHERE id = ?", (int(s),))
        if cur.fetchone():
            continue
        else:
            # numeric but no matching antenista: skip for manual inspection
            print(f"Row id={rid} has numeric nome_id={s} but no Antenista with that id; skipping")
            continue
    # Otherwise treat as textual name -> create Antenista and update
    aid = ensure_antenista(s)
    if aid:
        print(f"Updating card id={rid}: textual '{s}' -> antenista id {aid}")
        cur.execute("UPDATE requisicao_antenista_card SET nome_id = ? WHERE id = ?", (aid, rid))
        conn.commit()
        updated += 1

print(f"Done. Updated {updated} rows.\n")
conn.close()
