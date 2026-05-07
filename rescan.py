import asyncio
import sys
sys.path.insert(0, '.')
from services.importer import scan_directory, import_from_source
from app.database import init_db

async def main():
    await init_db()
    result = await import_from_source(37, r'C:\Book')
    print(f'Imported: {result["imported"]}, Confirmed: {result["confirmed"]}')
    
    import sqlite3
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, parent_id FROM categories WHERE source_id = 37 ORDER BY id
    ''')
    print()
    print('=== RECREATED CATEGORIES ===')
    for row in cursor.fetchall():
        print(f'ID:{row[0]} name:{row[1]} parent_id:{row[2]}')
    conn.close()

asyncio.run(main())