import asyncio
import aiosqlite
from app.database import get_all_books, get_all_sources


async def test():
    db = await aiosqlite.connect("library.db")
    db.row_factory = aiosqlite.Row

    # Test 1: Get books with default sort
    print("=== Test 1: get_all_books (default) ===")
    books, total = await get_all_books(db, limit=3, offset=0)
    print(f"Total: {total}")
    for b in books:
        print(f"  - {b['title'][:40]}")

    # Test 2: Sort by title
    print("\n=== Test 2: get_all_books (sort_by=title) ===")
    books, total = await get_all_books(db, limit=3, offset=0, sort_by="title")
    for b in books:
        print(f"  - {b['title'][:40]}")

    # Test 3: Filter by format
    print("\n=== Test 3: get_all_books (format=pdf) ===")
    books, total = await get_all_books(db, limit=3, offset=0, format="pdf")
    print(f"Total PDF: {total}")
    for b in books:
        print(f"  - {b['title'][:40]}")

    # Test 4: Filter by year
    print("\n=== Test 4: get_all_books (year=2010) ===")
    books, total = await get_all_books(db, limit=3, offset=0, year=2010)
    print(f"Total 2010: {total}")

    # Test 5: Multiple filters
    print("\n=== Test 5: get_all_books (format=pdf, sort_by=year) ===")
    books, total = await get_all_books(
        db, limit=3, offset=0, format="pdf", sort_by="year"
    )
    for b in books:
        print(f"  - {b.get('year')} {b['title'][:40]}")

    # Test 4: Filter by category
    print("\n=== Test 4: get_all_books (category=Programming) ===")
    books, total = await get_all_books(db, limit=3, offset=0, category="Programming")
    print(f"Total Programming: {total}")

    await db.close()
    print("\n=== All tests passed ===")


asyncio.run(test())
