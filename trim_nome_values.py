import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()
print('Trimming whitespace from estoque.nome entries...')
cur.execute("UPDATE requisicao_estoque_antenista SET nome = TRIM(nome) WHERE nome IS NOT NULL")
conn.commit()
print('Done trimming.')
conn.close()
