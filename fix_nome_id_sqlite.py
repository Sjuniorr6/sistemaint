import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
print('Using DB at', DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Helper to ensure an Antenista exists and return its id
def ensure_antenista(nome):
    nome = nome.strip()
    if not nome:
        return None
    cur.execute("SELECT id FROM requisicao_antenista WHERE nome = ?", (nome,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO requisicao_antenista (nome, estado) VALUES (?, ?)", (nome, ''))
    conn.commit()
    return cur.lastrowid

# Fix table function
def fix_table(table_name, col_name):
    print('\nProcessing table:', table_name, 'column:', col_name)
    cur.execute(f"SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL")
    rows = cur.fetchall()
    print('Distinct values count:', len(rows))
    for (val,) in rows:
        if val is None:
            continue
        s = str(val).strip()
        # if s is numeric, assume it's already a FK id; skip
        if s.isdigit():
            continue
        # otherwise s is textual name stored in the column; create Antenista and update
        aid = ensure_antenista(s)
        if aid:
            print(f"Mapping textual '{s}' -> antenista id {aid}")
            cur.execute(f"UPDATE {table_name} SET {col_name} = ? WHERE {col_name} = ?", (str(aid), s))
            conn.commit()

if __name__ == '__main__':
    # Determine actual column names and call fix_table accordingly
    # For estoque_antenista the column is 'nome' (text) in the current DB snapshot.
    fix_table('requisicao_estoque_antenista', 'nome')
    # For antenista_card the column is already 'nome_id'
    fix_table('requisicao_antenista_card', 'nome_id')
    print('\nDone. Please re-run: python manage.py migrate')
    conn.close()
