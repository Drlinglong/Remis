
import sqlite3
import os

appdata = os.getenv('APPDATA')
db_path = os.path.join(appdata, "RemisModFactoryDev", "remis.sqlite")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT project_id, name, source_path FROM projects")
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]} | Name: {row[1]}")
    print(f"Path: {row[2]}")
    print("-" * 20)
conn.close()
