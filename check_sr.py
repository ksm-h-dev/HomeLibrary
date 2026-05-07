import sqlite3
c = sqlite3.connect('library.db').cursor()
c.execute("SELECT id, name, path FROM sources")
print("=== Sources ===")
for r in c.fetchall():
    print(f"ID {r[0]}: {r[1]} - {r[2]}")