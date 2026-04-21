import aiosqlite
import os
from config import DATABASE_URL

DATABASE_PATH = DATABASE_URL


async def get_db():
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('dvd', 'hdd', 'ssd', 'nas', 'network', 'cloud', 'local')),
                path TEXT NOT NULL,
                volume_label TEXT DEFAULT '',
                catalog_id TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                description TEXT DEFAULT '',
                last_scanned TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                availability_status TEXT DEFAULT 'available'
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES categories(id)
            );
        """)
        try:
            await db.execute(
                "ALTER TABLE sources ADD COLUMN availability_status TEXT DEFAULT 'available'"
            )
            await db.commit()
        except:
            pass
        await db.commit()


SORT_OPTIONS = {
    "date": "b.id DESC",
    "title": "b.title ASC",
    "author": "b.author ASC",
    "year": "b.year DESC",
    "pages": "b.pages DESC",
}


async def get_all_books(
    db: aiosqlite.Connection,
    limit: int = 20,
    offset: int = 0,
    category: str = None,
    format: str = None,
    year: int = None,
    source_id: int = None,
    sort_by: str = "date",
):
    query = """
        SELECT b.*, c.name as category_name, s.name as source_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
    """
    params = []
    conditions = []
    if category:
        conditions.append("c.name = ?")
        params.append(category)
    if format:
        conditions.append("b.format = ?")
        params.append(format)
    if year:
        conditions.append("b.year = ?")
        params.append(year)
    if source_id:
        conditions.append("b.source_id = ?")
        params.append(source_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    sort_clause = SORT_OPTIONS.get(sort_by, "b.id DESC")
    query += f" ORDER BY {sort_clause} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    books = []
    for row in rows:
        book = dict(row)
        book["is_available"] = os.path.exists(book.get("file_path", ""))
        books.append(book)

    count_params = params.copy()
    count_params.pop()
    count_params.pop()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM books b LEFT JOIN categories c ON b.category_id = c.id LEFT JOIN sources s ON b.source_id = s.id"
        + (" WHERE " + " AND ".join(conditions) if conditions else ""),
        count_params,
    )
    total = (await cursor.fetchone())[0]

    return books, total


async def search_books(
    db: aiosqlite.Connection,
    query: str,
    format: str = None,
    category: str = None,
    year: int = None,
    source_id: int = None,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "date",
):
    sql = """
        SELECT b.*, c.name as category_name, s.name as source_name,
               b.title as title_hl,
               substr(b.description, 1, 150) as desc_snippet
        FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE books_fts MATCH ?
    """
    sort_clause = SORT_OPTIONS.get(sort_by, "b.id DESC")
    params = [f"{query}*"]

    if format:
        sql += " AND b.format = ?"
        params.append(format)
    if category:
        sql += " AND c.name = ?"
        params.append(category)
    if year:
        sql += " AND b.year = ?"
        params.append(year)
    if source_id:
        sql += " AND b.source_id = ?"
        params.append(source_id)

    sql += f" ORDER BY {sort_clause} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    books = []
    for row in rows:
        book = dict(row)
        book["is_available"] = os.path.exists(book.get("file_path", ""))
        books.append(book)

    count_sql = """
        SELECT COUNT(*) FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE books_fts MATCH ?
    """
    count_params = [f"{query}*"]
    if format:
        count_sql += " AND b.format = ?"
        count_params.append(format)
    if category:
        count_sql += " AND c.name = ?"
        count_params.append(category)
    if year:
        count_sql += " AND b.year = ?"
        count_params.append(year)
    if source_id:
        count_sql += " AND b.source_id = ?"
        count_params.append(source_id)

    cursor = await db.execute(count_sql, count_params)
    total = (await cursor.fetchone())[0]

    return books, total


async def get_book_by_id(db: aiosqlite.Connection, book_id: int):
    cursor = await db.execute(
        """
        SELECT b.*, c.name as category_name, s.name as source_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE b.id = ?
    """,
        (book_id,),
    )
    row = await cursor.fetchone()
    if row:
        book = dict(row)
        book["is_available"] = os.path.exists(book.get("file_path", ""))
        return book
    return None


async def get_categories(db: aiosqlite.Connection):
    cursor = await db.execute("SELECT * FROM categories ORDER BY name")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_or_create_category(
    db: aiosqlite.Connection, name: str, parent_id: int = None
):
    cursor = await db.execute("SELECT id FROM categories WHERE name = ?", (name,))
    row = await cursor.fetchone()
    if row:
        return row[0]

    cursor = await db.execute(
        "INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id)
    )
    await db.commit()
    return cursor.lastrowid


async def insert_book(db: aiosqlite.Connection, book_data: dict):
    try:
        cursor = await db.execute(
            """
            INSERT INTO books (
                title, author, publisher, isbn, year, pages,
                format, file_size, description, file_path, relative_path,
                cover_path, category_id, source_id, language, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                book_data.get("title", ""),
                book_data.get("author", ""),
                book_data.get("publisher", ""),
                book_data.get("isbn", ""),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format", ""),
                book_data.get("file_size", 0),
                book_data.get("description", ""),
                book_data.get("file_path", ""),
                book_data.get("relative_path", ""),
                book_data.get("cover_path", ""),
                book_data.get("category_id"),
                book_data.get("source_id"),
                book_data.get("language", "ru"),
                book_data.get("source_url", ""),
            ),
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        return None


async def update_book(db: aiosqlite.Connection, book_id: int, book_data: dict):
    await db.execute(
        """
        UPDATE books SET
            title = COALESCE(?, title),
            author = COALESCE(?, author),
            publisher = COALESCE(?, publisher),
            year = COALESCE(?, year),
            pages = COALESCE(?, pages),
            description = COALESCE(?, description),
            category_id = COALESCE(?, category_id),
            language = COALESCE(?, language)
        WHERE id = ?
        """,
        (
            book_data.get("title"),
            book_data.get("author"),
            book_data.get("publisher"),
            book_data.get("year"),
            book_data.get("pages"),
            book_data.get("description"),
            book_data.get("category_id"),
            book_data.get("language"),
            book_id,
        ),
    )
    await db.commit()


async def upsert_book(db: aiosqlite.Connection, book_data: dict):
    source_id = book_data.get("source_id")
    relative_path = book_data.get("relative_path", "")

    cursor = await db.execute(
        "SELECT id FROM books WHERE source_id = ? AND relative_path = ?",
        (source_id, relative_path),
    )
    existing = await cursor.fetchone()

    if existing:
        book_id = existing[0]
        await db.execute(
            """
            UPDATE books SET
                title = ?, author = ?, publisher = ?, isbn = ?, year = ?, pages = ?,
                format = ?, file_size = ?, description = ?, file_path = ?,
                cover_path = ?, category_id = ?, language = ?, source_url = ?
            WHERE id = ?
            """,
            (
                book_data.get("title", ""),
                book_data.get("author", ""),
                book_data.get("publisher", ""),
                book_data.get("isbn", ""),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format", ""),
                book_data.get("file_size", 0),
                book_data.get("description", ""),
                book_data.get("file_path", ""),
                book_data.get("cover_path", ""),
                book_data.get("category_id"),
                book_data.get("language", "ru"),
                book_data.get("source_url", ""),
                book_id,
            ),
        )
        await db.commit()
        return book_id
    else:
        cursor = await db.execute(
            """
            INSERT INTO books (
                title, author, publisher, isbn, year, pages,
                format, file_size, description, file_path, relative_path,
                cover_path, category_id, source_id, language, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_data.get("title", ""),
                book_data.get("author", ""),
                book_data.get("publisher", ""),
                book_data.get("isbn", ""),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format", ""),
                book_data.get("file_size", 0),
                book_data.get("description", ""),
                book_data.get("file_path", ""),
                book_data.get("relative_path", ""),
                book_data.get("cover_path", ""),
                book_data.get("category_id"),
                book_data.get("source_id"),
                book_data.get("language", "ru"),
                book_data.get("source_url", ""),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_book_by_source_and_path(
    db: aiosqlite.Connection, source_id: int, relative_path: str
):
    cursor = await db.execute(
        "SELECT id FROM books WHERE source_id = ? AND relative_path = ?",
        (source_id, relative_path),
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def get_stats(db: aiosqlite.Connection):
    cursor = await db.execute("SELECT COUNT(*) FROM books")
    total_books = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM categories")
    total_categories = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM sources")
    total_sources = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT format, COUNT(*) as count FROM books GROUP BY format"
    )
    formats = {row[0]: row[1] for row in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT year, COUNT(*) as count FROM books WHERE year IS NOT NULL GROUP BY year ORDER BY year DESC LIMIT 10"
    )
    years = {row[0]: row[1] for row in await cursor.fetchall()}

    return {
        "total_books": total_books,
        "total_categories": total_categories,
        "total_sources": total_sources,
        "formats": formats,
        "years": years,
    }


async def get_all_sources(db: aiosqlite.Connection, active_only: bool = False):
    query = """
        SELECT s.*, COUNT(b.id) as books_count
        FROM sources s
        LEFT JOIN books b ON s.id = b.source_id
    """
    if active_only:
        query += " WHERE s.is_active = 1"
    query += " GROUP BY s.id ORDER BY s.name"

    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_source_by_id(db: aiosqlite.Connection, source_id: int):
    cursor = await db.execute(
        """
        SELECT s.*, COUNT(b.id) as books_count
        FROM sources s
        LEFT JOIN books b ON s.id = b.source_id
        WHERE s.id = ?
        GROUP BY s.id
    """,
        (source_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def insert_source(db: aiosqlite.Connection, source_data: dict):
    availability_status = check_source_availability(source_data)
    cursor = await db.execute(
        """
        INSERT INTO sources (name, type, path, volume_label, catalog_id, is_active, description, availability_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            source_data.get("name", ""),
            source_data.get("type", "local"),
            source_data.get("path", ""),
            source_data.get("volume_label", ""),
            source_data.get("catalog_id", ""),
            source_data.get("is_active", 1),
            source_data.get("description", ""),
            availability_status,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def update_source(db: aiosqlite.Connection, source_id: int, source_data: dict):
    new_path = source_data.get("path", "")

    cursor = await db.execute("SELECT path FROM sources WHERE id = ?", (source_id,))
    row = await cursor.fetchone()
    old_path = row[0] if row else ""

    if old_path and new_path and old_path != new_path:
        await db.execute(
            "UPDATE books SET file_path = REPLACE(file_path, ?, ?) WHERE source_id = ?",
            (old_path, new_path, source_id),
        )

    status = source_data.get("availability_status")
    if status:
        await db.execute(
            """
            UPDATE sources 
            SET name = COALESCE(?, name), type = COALESCE(?, type), path = COALESCE(?, path),
                volume_label = COALESCE(?, volume_label), catalog_id = COALESCE(?, catalog_id),
                is_active = COALESCE(?, is_active), description = COALESCE(?, description),
                availability_status = ?,
                last_scanned = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                source_data.get("name"),
                source_data.get("type"),
                source_data.get("path"),
                source_data.get("volume_label"),
                source_data.get("catalog_id"),
                source_data.get("is_active"),
                source_data.get("description"),
                status,
                source_id,
            ),
        )
    else:
        await db.execute(
            """
            UPDATE sources 
            SET name = COALESCE(?, name), type = COALESCE(?, type), path = COALESCE(?, path),
                volume_label = COALESCE(?, volume_label), catalog_id = COALESCE(?, catalog_id),
                is_active = COALESCE(?, is_active), description = COALESCE(?, description),
                last_scanned = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                source_data.get("name"),
                source_data.get("type"),
                source_data.get("path"),
                source_data.get("volume_label"),
                source_data.get("catalog_id"),
                source_data.get("is_active"),
                source_data.get("description"),
                source_id,
            ),
        )
    await db.commit()


def check_source_availability(source_data: dict) -> str:
    path = source_data.get("path", "")
    catalog_id = source_data.get("catalog_id", "")

    if path and os.path.exists(path):
        return "available"

    if catalog_id and os.path.exists(catalog_id):
        return "available"

    source_type = source_data.get("type", "")
    if source_type in ("dvd", "ssd"):
        return "archived"

    return "unavailable"


async def update_source_path(
    db: aiosqlite.Connection, source_id: int, new_path: str, new_volume_label: str = ""
):
    await db.execute(
        """
        UPDATE sources 
        SET path = ?, volume_label = COALESCE(?, volume_label), last_scanned = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (new_path, new_volume_label, source_id),
    )
    await db.commit()


async def find_source_by_catalog_id(db: aiosqlite.Connection, catalog_id: str):
    cursor = await db.execute(
        "SELECT id FROM sources WHERE catalog_id = ?", (catalog_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def find_source_by_volume_label(db: aiosqlite.Connection, volume_label: str):
    cursor = await db.execute(
        "SELECT id FROM sources WHERE volume_label = ?", (volume_label,)
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def upsert_source_by_identifier(db: aiosqlite.Connection, source_data: dict):
    catalog_id = source_data.get("catalog_id", "")
    volume_label = source_data.get("volume_label", "")

    existing_id = None

    if catalog_id:
        existing_id = await find_source_by_catalog_id(db, catalog_id)

    if not existing_id and volume_label:
        existing_id = await find_source_by_volume_label(db, volume_label)

    if existing_id:
        await update_source(db, existing_id, source_data)
        return existing_id
    else:
        return await insert_source(db, source_data)


async def delete_source(db: aiosqlite.Connection, source_id: int):
    # Сначала удаляем все книги, связанные с этим хранилищем
    # book_tags удалятся автоматически благодаря ON DELETE CASCADE
    # books_fts обновится автоматически благодаря триггеру books_ad
    await db.execute("DELETE FROM books WHERE source_id = ?", (source_id,))
    # Затем удаляем само хранилище
    await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    await db.commit()


async def update_source_scan_time(db: aiosqlite.Connection, source_id: int):
    await db.execute(
        "UPDATE sources SET last_scanned = CURRENT_TIMESTAMP WHERE id = ?", (source_id,)
    )
    await db.commit()


async def get_books_by_source(
    db: aiosqlite.Connection, source_id: int, limit: int = 20, offset: int = 0
):
    cursor = await db.execute(
        """
        SELECT b.*, c.name as category_name, s.name as source_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE b.source_id = ?
        ORDER BY b.id DESC LIMIT ? OFFSET ?
    """,
        (source_id, limit, offset),
    )
    rows = await cursor.fetchall()

    cursor = await db.execute(
        "SELECT COUNT(*) FROM books WHERE source_id = ?", (source_id,)
    )
    total = (await cursor.fetchone())[0]

    return [dict(row) for row in rows], total
