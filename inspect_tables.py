import sqlite3
import os
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(DB)
cur = conn.cursor()
for t in ['requisicao_estoque_antenista','requisicao_antenista_card','requisicao_antenista']:
    print('\nTable:', t)
    try:
        cur.execute(f"PRAGMA table_info('{t}')")
        for row in cur.fetchall():
            print(row)
    except Exception as e:
        print('  ERROR:', e)
conn.close()
