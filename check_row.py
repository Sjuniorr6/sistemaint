import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
print('antenista_card id=1 ->', cur.execute("SELECT id, nome_id FROM requisicao_antenista_card WHERE id=1").fetchall())
print('sample 10 rows ->', cur.execute("SELECT id, nome_id FROM requisicao_antenista_card LIMIT 10").fetchall())
conn.close()
