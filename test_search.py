import asyncio
import aiosqlite


async def test_search():
    db = await aiosqlite.connect("library.db")
    db.row_factory = aiosqlite.Row

    # Поиск через FTS
    query = "excel"
    cursor = await db.execute(
        """SELECT b.* FROM books_fts 
           JOIN books b ON books_fts.rowid = b.id 
           WHERE books_fts MATCH ?""",
        [f"{query}*"],
    )
    rows = await cursor.fetchall()
    print(f"Found {len(rows)} books")
    for row in rows:
        print(f"  - {row['title']}")

    await db.close()


asyncio.run(test_search())
