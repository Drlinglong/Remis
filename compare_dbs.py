import sqlite3
import os

db_dev = r'C:\Users\Drlin\AppData\Roaming\RemisModFactoryDev\remis.sqlite'
db_prod = r'C:\Users\Drlin\AppData\Roaming\RemisModFactory\remis.sqlite'

def get_stats(db_path):
    if not os.path.exists(db_path):
        return "Not Found"
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM entries")
        entries = cur.fetchone()[0]
        cur.execute("SELECT name FROM glossaries WHERE game_id='eu5' AND is_main=1")
        eu5_main = cur.fetchone()
        eu5_main_name = eu5_main[0] if eu5_main else "None"
        conn.close()
        return f"Entries: {entries}, EU5 Main: {eu5_main_name}"
    except Exception as e:
        return f"Error: {e}"

print(f"DEV:  {get_stats(db_dev)}")
print(f"PROD: {get_stats(db_prod)}")
