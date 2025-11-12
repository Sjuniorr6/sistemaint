import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()
print('Rows in requisicao_antenista_card with nome_id that has no matching requisicao_antenista.id')
for row in cur.execute("SELECT c.id, c.nome_id FROM requisicao_antenista_card c LEFT JOIN requisicao_antenista a ON (CAST(c.nome_id AS INTEGER)=a.id) WHERE c.nome_id IS NOT NULL AND a.id IS NULL"):
    print(row)

print('\nRows in requisicao_estoque_antenista with nome that has no matching requisicao_antenista.id')
for row in cur.execute("SELECT e.id, e.nome FROM requisicao_estoque_antenista e LEFT JOIN requisicao_antenista a ON (CAST(e.nome AS INTEGER)=a.id) WHERE e.nome IS NOT NULL AND a.id IS NULL"):
    print(row)
conn.close()
