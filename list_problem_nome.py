import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()
print('Distinct non-numeric nomes in estoque_antenista:')
for row in cur.execute("SELECT DISTINCT nome FROM requisicao_estoque_antenista WHERE nome IS NOT NULL"):
    val = row[0]
    if val is None: continue
    s = str(val).strip()
    if not s.isdigit():
        print(repr(val))
print('\nDistinct non-numeric nome_id in antenista_card:')
for row in cur.execute("SELECT DISTINCT nome_id FROM requisicao_antenista_card WHERE nome_id IS NOT NULL"):
    val = row[0]
    if val is None: continue
    s = str(val).strip()
    if not s.isdigit():
        print(repr(val))
conn.close()
