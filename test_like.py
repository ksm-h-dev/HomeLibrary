import sqlite3
c = sqlite3.connect('library.db').cursor()

# Test the new logic: extract last part before applying
test_filters = [
    'Soft/Server 2003',
    'Учеба/Soft/Server 2003',
    'Книги/Языки/English',
    'English',
    'Server 2003',
]

print('=== NEW LOGIC: rsplit("/", 1)[-1] ===\n')
for f in test_filters:
    last_part = f.rsplit("/", 1)[-1]
    pattern = f"%{last_part}%"
    c.execute("""
        SELECT b.source_id, c.name, c.full_path 
        FROM books b 
        JOIN category_paths c ON b.category_id = c.id 
        WHERE c.full_path LIKE ?
    """, (pattern,))
    rows = c.fetchall()
    print(f'Filter: {f!r}')
    print(f'  Extracted: {last_part!r}')
    print(f'  LIKE: {pattern}')
    print(f'  Results: {len(rows)} books')
    for r in rows:
        print(f'    Src {r[0]}: {r[2]}')
    print()