import aiosqlite
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
                is_active INTEGER DEFAULT 1,
                description TEXT DEFAULT '',
                last_scanned TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT DEFAULT '',
                publisher TEXT DEFAULT '',
                isbn TEXT DEFAULT '',
                year INTEGER,
                pages INTEGER,
                format TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                description TEXT DEFAULT '',
                file_path TEXT NOT NULL,
                cover_path TEXT DEFAULT '',
                category_id INTEGER,
                source_id INTEGER,
                language TEXT DEFAULT 'ru',
                source_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (source_id) REFERENCES sources(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_books_file_path ON books(file_path);

            CREATE TABLE IF NOT EXISTS book_tags (
                book_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (book_id, tag_id),
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
                title,
                author,
                description,
                content='books',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN
                INSERT INTO books_fts(rowid, title, author, description)
                VALUES (new.id, new.title, new.author, new.description);
            END;

            CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN
                INSERT INTO books_fts(books_fts, rowid, title, author, description)
                VALUES ('delete', old.id, old.title, old.author, old.description);
            END;

            CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN
                INSERT INTO books_fts(books_fts, rowid, title, author, description)
                VALUES ('delete', old.id, old.title, old.author, old.description);
                INSERT INTO books_fts(rowid, title, author, description)
                VALUES (new.id, new.title, new.author, new.description);
            END;
        """)
        await db.commit()


async def get_all_books(
    db: aiosqlite.Connection, limit: int = 20, offset: int = 0, category: str = None
):
    query = """
        SELECT b.*, c.name as category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
    """
    params = []
    if category:
        query += " WHERE c.name = ?"
        params.append(category)
    query += " ORDER BY b.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    cursor = await db.execute(
        "SELECT COUNT(*) FROM books"
        + (
            " WHERE category_id = (SELECT id FROM categories WHERE name = ?)"
            if category
            else ""
        )
    )
    total = (await cursor.fetchone())[0]

    return [dict(row) for row in rows], total


async def get_book_by_id(db: aiosqlite.Connection, book_id: int):
    cursor = await db.execute(
        """
        SELECT b.*, c.name as category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.id = ?
    """,
        (book_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def search_books(
    db: aiosqlite.Connection,
    query: str,
    format: str = None,
    category: str = None,
    year: int = None,
    limit: int = 20,
    offset: int = 0,
):
    sql = """
        SELECT b.*, c.name as category_name,
               highlight(books_fts, 0, '<b>', '</b>') as title_hl,
               snippet(books_fts, 2, '...', '...', 30) as desc_snippet
        FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE books_fts MATCH ?
    """
    params = [f'"{query}"*']

    if format:
        sql += " AND b.format = ?"
        params.append(format)
    if category:
        sql += " AND c.name = ?"
        params.append(category)
    if year:
        sql += " AND b.year = ?"
        params.append(year)

    sql += " ORDER BY rank LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    count_sql = """
        SELECT COUNT(*) FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE books_fts MATCH ?
    """
    count_params = [f'"{query}"*']
    if format:
        count_sql += " AND b.format = ?"
        count_params.append(format)
    if category:
        count_sql += " AND c.name = ?"
        count_params.append(category)
    if year:
        count_sql += " AND b.year = ?"
        count_params.append(year)

    cursor = await db.execute(count_sql, count_params)
    total = (await cursor.fetchone())[0]

    return [dict(row) for row in rows], total


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
                format, file_size, description, file_path,
                cover_path, category_id, language, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        return None


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
    cursor = await db.execute(
        """
        INSERT INTO sources (name, type, path, is_active, description)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            source_data.get("name", ""),
            source_data.get("type", "local"),
            source_data.get("path", ""),
            source_data.get("is_active", 1),
            source_data.get("description", ""),
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def update_source(db: aiosqlite.Connection, source_id: int, source_data: dict):
    await db.execute(
        """
        UPDATE sources 
        SET name = ?, type = ?, path = ?, is_active = ?, description = ?,
            last_scanned = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (
            source_data.get("name", ""),
            source_data.get("type", "local"),
            source_data.get("path", ""),
            source_data.get("is_active", 1),
            source_data.get("description", ""),
            source_id,
        ),
    )
    await db.commit()


async def delete_source(db: aiosqlite.Connection, source_id: int):
    await db.execute(
        "UPDATE books SET source_id = NULL WHERE source_id = ?", (source_id,)
    )
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
