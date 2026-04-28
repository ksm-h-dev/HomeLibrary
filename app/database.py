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
                name TEXT NOT NULL,
                source_id INTEGER,
                parent_id INTEGER,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_id) REFERENCES categories(id),
                UNIQUE(name, source_id)
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
                relative_path TEXT DEFAULT '',
                cover_path TEXT DEFAULT '',
                category_id INTEGER,
                source_id INTEGER,
                language TEXT DEFAULT 'ru',
                source_url TEXT DEFAULT '',
                is_available INTEGER DEFAULT 1,
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (source_id) REFERENCES sources(id)
            );

            CREATE VIEW IF NOT EXISTS category_paths AS
            WITH RECURSIVE cat_path AS (
                SELECT id, name, source_id, parent_id, name as full_path
                FROM categories WHERE parent_id IS NULL
                UNION ALL
                SELECT c.id, c.name, c.source_id, c.parent_id, cat_path.full_path || '/' || c.name
                FROM categories c
                INNER JOIN cat_path ON c.parent_id = cat_path.id
            )
            SELECT id, name, source_id, parent_id, full_path FROM cat_path;
        """)
        try:
            await db.execute(
                "ALTER TABLE sources ADD COLUMN availability_status TEXT DEFAULT 'available'"
            )
            await db.commit()
        except:
            pass
        try:
            await db.execute("ALTER TABLE books ADD COLUMN is_available INTEGER DEFAULT 1")
            await db.commit()
        except:
            pass
        try:
            await db.execute("ALTER TABLE books ADD COLUMN last_seen TIMESTAMP")
            await db.commit()
        except:
            pass
        try:
            await db.execute("ALTER TABLE books ADD COLUMN is_new_arrival INTEGER DEFAULT 0")
            await db.commit()
        except:
            pass
        try:
            await db.execute("ALTER TABLE books ADD COLUMN cover_ext TEXT DEFAULT ''")
            await db.execute("ALTER TABLE books ADD COLUMN format TEXT DEFAULT ''")
            await db.commit()
        except:
            pass
        try:
            await db.execute("ALTER TABLE sources ADD COLUMN total_size INTEGER DEFAULT 0")
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
    availability: str = None,
):
    """Получение списка книг с фильтрацией.

    Параметр availability:
    - "available": is_available=1 (только книги в наличии)
    - "missing": is_available=0 (только отсутствующие)
    - "new": is_new_arrival=1 (новые поступления, сортировка по last_seen DESC)
    """
    query = """
        SELECT b.*, c.full_path as category_name, s.name as source_name
        FROM books b
        LEFT JOIN category_paths c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
    """
    params = []
    conditions = []
    if category:
        last_part = category.rsplit("/", 1)[-1]
        filter_pattern = f"%{last_part}%"
        conditions.append("c.full_path LIKE ?")
        params.append(filter_pattern)
    if format:
        conditions.append("b.format = ?")
        params.append(format)
    if year:
        conditions.append("b.year = ?")
        params.append(year)
    if source_id:
        conditions.append("b.source_id = ?")
        params.append(source_id)
    # Фильтрация по наличию
    if availability == "available":
        conditions.append("b.is_available = 1")
    elif availability == "missing":
        conditions.append("b.is_available = 0")
    elif availability == "new":
        conditions.append("b.is_new_arrival = 1")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    sort_clause = SORT_OPTIONS.get(sort_by, "b.id DESC")
    # Новые поступления сортируем по времени подтверждения
    if availability == "new":
        sort_clause = "b.last_seen DESC"
    query += f" ORDER BY {sort_clause} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    books = []
    for row in rows:
        book = dict(row)
        stored = book.get("is_available")
        if stored is None or stored == '':
            book["is_available"] = os.path.exists(book.get("file_path", ""))
        else:
            book["is_available"] = bool(stored)
        books.append(book)

    count_params = params.copy()
    count_params.pop()
    count_params.pop()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM books b LEFT JOIN category_paths c ON b.category_id = c.id LEFT JOIN sources s ON b.source_id = s.id"
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
    availability: str = None,
):
    """Полнотекстовый поиск с фильтрацией по наличию.

    Использует FTS5 для поиска по title, author, description.
    Параметр availability:
    - "available": только книги в наличии (is_available=1)
    - "missing": только отсутствующие (is_available=0)
    - "new": новые поступления (is_new_arrival=1), сортировка по last_seen DESC
    """
    sql = """
        SELECT b.*, c.full_path as category_name, s.name as source_name,
               b.title as title_hl,
               substr(b.description, 1, 150) as desc_snippet
        FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN category_paths c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE books_fts MATCH ?
    """
    sort_clause = SORT_OPTIONS.get(sort_by, "b.id DESC")
    params = [f"{query}*"]

    if format:
        sql += " AND b.format = ?"
        params.append(format)
    if category:
        last_part = category.rsplit("/", 1)[-1]
        filter_pattern = f"%{last_part}%"
        sql += " AND c.full_path LIKE ?"
        params.append(filter_pattern)
    if year:
        sql += " AND b.year = ?"
        params.append(year)
    if source_id:
        sql += " AND b.source_id = ?"
        params.append(source_id)
    if availability == "available":
        sql += " AND b.is_available = 1"
    elif availability == "missing":
        sql += " AND b.is_available = 0"
    elif availability == "new":
        sql += " AND b.is_new_arrival = 1"
        sort_clause = "b.last_seen DESC"

    sql += f" ORDER BY {sort_clause} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    books = []
    for row in rows:
        book = dict(row)
        stored = book.get("is_available")
        if stored is None or stored == '':
            book["is_available"] = os.path.exists(book.get("file_path", ""))
        else:
            book["is_available"] = bool(stored)
        books.append(book)

    count_sql = """
        SELECT COUNT(*) FROM books_fts
        JOIN books b ON books_fts.rowid = b.id
        LEFT JOIN category_paths c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE books_fts MATCH ?
    """
    count_params = [f"{query}*"]
    if format:
        count_sql += " AND b.format = ?"
        count_params.append(format)
    if category:
        last_part = category.rsplit("/", 1)[-1]
        filter_pattern = f"%{last_part}%"
        count_sql += " AND c.full_path LIKE ?"
        count_params.append(filter_pattern)
    if year:
        count_sql += " AND b.year = ?"
        count_params.append(year)
    if source_id:
        count_sql += " AND b.source_id = ?"
        count_params.append(source_id)
    if availability == "available":
        count_sql += " AND b.is_available = 1"
    elif availability == "missing":
        count_sql += " AND b.is_available = 0"
    elif availability == "new":
        count_sql += " AND b.is_new_arrival = 1"

    cursor = await db.execute(count_sql, count_params)
    total = (await cursor.fetchone())[0]

    return books, total


async def get_book_by_id(db: aiosqlite.Connection, book_id: int):
    cursor = await db.execute(
        """
        SELECT b.*, c.full_path as category_name, s.name as source_name
        FROM books b
        LEFT JOIN category_paths c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE b.id = ?
    """,
        (book_id,),
    )
    row = await cursor.fetchone()
    if row:
        book = dict(row)
        stored = book.get("is_available")
        if stored is None or stored == '':
            book["is_available"] = os.path.exists(book.get("file_path", ""))
        else:
            book["is_available"] = bool(stored)
        return book
    return None


async def get_categories(db: aiosqlite.Connection):
    cursor = await db.execute("""
        WITH RECURSIVE cat_path AS (
            SELECT id, name, source_id, parent_id, name as full_path
            FROM categories WHERE parent_id IS NULL
            UNION ALL
            SELECT c.id, c.name, c.source_id, c.parent_id, cat_path.full_path || '/' || c.name
            FROM categories c
            INNER JOIN cat_path ON c.parent_id = cat_path.id
        )
        SELECT id, name, source_id, parent_id, full_path FROM cat_path ORDER BY full_path
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_or_create_category(
    db: aiosqlite.Connection, full_path: str, source_id: int
):
    if not full_path:
        return None
    
    parts = [p for p in full_path.split("/") if p]
    if not parts:
        return None
    
    parent_id = None
    for i, name in enumerate(parts):
        cursor = await db.execute(
            "SELECT id FROM categories WHERE name = ? AND source_id = ?",
            (name, source_id)
        )
        row = await cursor.fetchone()
        if row:
            parent_id = row[0]
            continue
        
        cursor = await db.execute(
            "SELECT id FROM categories WHERE name = ? AND source_id = 0",
            (name,)
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE categories SET source_id = ? WHERE id = ?",
                (source_id, row[0])
            )
            await db.commit()
            parent_id = row[0]
            continue
        
        cursor = await db.execute(
            "INSERT INTO categories (name, source_id, parent_id) VALUES (?, ?, ?)",
            (name, source_id, parent_id),
        )
        await db.commit()
        parent_id = cursor.lastrowid
    
    return parent_id


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
    desc_value = book_data.get("description")
    if desc_value is not None:
        await db.execute(
            """
        UPDATE books SET
            title = COALESCE(?, title),
            author = COALESCE(?, author),
            isbn = COALESCE(?, isbn),
            publisher = COALESCE(?, publisher),
            year = COALESCE(?, year),
            pages = COALESCE(?, pages),
            format = COALESCE(?, format),
            description = ?,
            category_id = COALESCE(?, category_id),
            language = COALESCE(?, language)
        WHERE id = ?
        """,
            (
                book_data.get("title"),
                book_data.get("author"),
                book_data.get("isbn"),
                book_data.get("publisher"),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format"),
                desc_value,
                book_data.get("category_id"),
                book_data.get("language"),
                book_id,
            ),
        )
    else:
        await db.execute(
            """
        UPDATE books SET
            title = COALESCE(?, title),
            author = COALESCE(?, author),
            isbn = COALESCE(?, isbn),
            publisher = COALESCE(?, publisher),
            year = COALESCE(?, year),
            pages = COALESCE(?, pages),
            format = COALESCE(?, format),
            category_id = COALESCE(?, category_id),
            language = COALESCE(?, language)
        WHERE id = ?
        """,
            (
                book_data.get("title"),
                book_data.get("author"),
                book_data.get("isbn"),
                book_data.get("publisher"),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format"),
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
    
    # Удаляем осиротевшие книги (source_id = NULL)
    await db.execute("DELETE FROM books WHERE source_id IS NULL")
    
    # Удаляем книги с несуществующим source_id
    await db.execute("""
        DELETE FROM books 
        WHERE source_id IS NOT NULL 
        AND source_id NOT IN (SELECT id FROM sources)
    """)
    
    # Удаляем категории этого хранилища
    await db.execute("DELETE FROM categories WHERE source_id = ?", (source_id,))
    
    # Затем удаляем само хранилище
    await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    await db.commit()


async def get_source_transfer_info(db: aiosqlite.Connection, source_id: int) -> dict:
    """Возвращает информацию о хранилище для переноса."""
    source = await get_source_by_id(db, source_id)
    if not source:
        return None
    
    # Получаем категории с количеством книг
    cursor = await db.execute("""
        SELECT c.id, c.name, c.full_path, COUNT(b.id) as book_count
        FROM category_paths c
        JOIN books b ON b.category_id = c.id
        WHERE b.source_id = ?
        GROUP BY c.id
        ORDER BY c.full_path
    """, (source_id,))
    categories = await cursor.fetchall()
    
    # Получаем общее количество книг и размер
    cursor = await db.execute(
        "SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM books WHERE source_id = ?",
        (source_id,)
    )
    row = await cursor.fetchone()
    
    return {
        "id": source["id"],
        "name": source["name"],
        "path": source["path"],
        "total_size": source.get("total_size", 0),
        "book_count": row[0] if row else 0,
        "categories": [dict(c) for c in categories],
    }


async def transfer_source(
    db: aiosqlite.Connection,
    source_id: int,
    target_path: str,
    target_source_id: int = None,
    conflict_callback=None,
) -> dict:
    """Перенос хранилища.
    
    Args:
        db: Database connection
        source_id: ID исходного хранилища
        target_path: Путь для переноса
        target_source_id: ID целевого хранилища (если перенос в существующее)
        conflict_callback: функция для обработки конфликтов (принимает путь, возвращает True/False)
    
    Returns:
        dict: {success: bool, message: str, new_source_id: int, transferred_count: int}
    """
    import shutil
    
    source = await get_source_by_id(db, source_id)
    if not source:
        return {"success": False, "message": "Исходное хранилище не найдено"}
    
    source_path = source["path"]
    if not os.path.exists(source_path):
        return {"success": False, "message": f"Исходный путь не существует: {source_path}"}
    
    # Проверка свободного места
    source_size = source.get("total_size", 0)
    try:
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(target_path), None, ctypes.byref(free_bytes), None
        )
        free_space = free_bytes.value
    except Exception:
        free_space = 999999999999999  # fallback
    
    is_new_target = target_source_id is None
    
    if is_new_target and source_size > free_space:
        return {"success": False, "message": "Недостаточно места на диске"}
    
    # Получаем категории хранилища
    cursor = await db.execute("""
        SELECT DISTINCT c.id, c.name, c.full_path
        FROM category_paths c
        JOIN books b ON b.category_id = c.id
        WHERE b.source_id = ?
        ORDER BY c.full_path
    """, (source_id,))
    categories = await cursor.fetchall()
    
    # Создаём целевую директорию если нужно
    if is_new_target:
        try:
            os.makedirs(target_path, exist_ok=True)
            operation_log.append({"type": "category_create", "path": target_path, "status": "success"})
        except Exception as e:
            operation_log.append({"type": "category_create", "path": target_path, "status": "error", "error": str(e)})
    
    # Получаем все книги хранилища
    cursor = await db.execute(
        "SELECT * FROM books WHERE source_id = ?", (source_id,)
    )
    books = await cursor.fetchall()
    
    transferred = 0
    deleted_originals = 0
    errors = []
    successful_book_ids = []
    detailed_log = []  # Подробный лог
    operation_log = []  # Лог операций: копирование, удаление, категории
    
    for book_row in books:
        book = dict(book_row)
        book_log = {
            "id": book.get("id"),
            "title": book.get("title"),
            "file": os.path.basename(book.get("file_path", "")),
            "status": "pending",
            "details": ""
        }
        
        # Находим категорию книги
        for cat in categories:
            if cat["id"] == book.get("category_id"):
                category_path = cat["full_path"]
                break
        
        # Формируем целевой путь
        if is_new_target:
            target_dir = os.path.join(target_path, category_path) if category_path else target_path
        else:
            target_dir = os.path.join(target_path, category_path) if category_path else target_path
        
        try:
            os.makedirs(target_dir, exist_ok=True)
            operation_log.append({
                "type": "category_create",
                "path": target_dir,
                "status": "success"
            })
        except Exception as e:
            operation_log.append({
                "type": "category_create",
                "path": target_dir,
                "status": "error",
                "error": str(e)
            })
        
        # Переносим файл книги
        source_file = book.get("file_path", "")
        
        if not source_file:
            book_log["status"] = "skipped"
            book_log["details"] = "Пустой file_path"
            detailed_log.append(book_log)
            continue
            
        if not os.path.exists(source_file):
            book_log["status"] = "error"
            book_log["details"] = f"Файл не найден: {source_file}"
            errors.append(f"ID {book.get('id')}: Файл не найден")
            detailed_log.append(book_log)
            continue
            
        target_file = os.path.join(target_dir, os.path.basename(source_file))
        
        # Проверка конфликта
        if os.path.exists(target_file):
            if conflict_callback:
                if not conflict_callback(target_file):
                    book_log["status"] = "skipped"
                    book_log["details"] = f"Конфликт: пользователь отказался"
                    detailed_log.append(book_log)
                    continue
            else:
                book_log["status"] = "skipped"
                book_log["details"] = f"Конфликт: файл уже существует"
                errors.append(f"Конфликт: {os.path.basename(source_file)}")
                detailed_log.append(book_log)
                continue
        
        try:
            # Копируем файл на новое место
            shutil.copy2(source_file, target_file)
            operation_log.append({
                "type": "file_copy",
                "source": source_file,
                "target": target_file,
                "status": "success"
            })
            book["file_path"] = target_file
            book["relative_path"] = os.path.join(category_path, os.path.basename(source_file)) if category_path else os.path.basename(source_file)
            book["file_size"] = os.path.getsize(target_file)
        except Exception as e:
            book_log["status"] = "error"
            book_log["details"] = f"Ошибка копирования: {str(e)}"
            operation_log.append({
                "type": "file_copy",
                "source": source_file,
                "target": target_file,
                "status": "error",
                "error": str(e)
            })
            errors.append(f"Ошибка {book.get('title')}: {str(e)}")
            detailed_log.append(book_log)
            continue
        
        # Удаляем оригинал после успешного копирования
        try:
            os.remove(source_file)
            operation_log.append({
                "type": "file_delete",
                "path": source_file,
                "status": "success"
            })
            deleted_originals += 1
        except Exception as e:
            operation_log.append({
                "type": "file_delete",
                "path": source_file,
                "status": "error",
                "error": str(e)
            })
        except Exception as e:
            book_log["details"] += f" | Оригинал не удалён: {str(e)}"
        
        # Переносим обложку
        cover_path = book.get("cover_path", "")
        if cover_path and os.path.exists(cover_path):
            target_cover = os.path.join(target_dir, os.path.basename(cover_path))
            try:
                shutil.copy2(cover_path, target_cover)
                operation_log.append({
                    "type": "file_copy",
                    "source": cover_path,
                    "target": target_cover,
                    "status": "success"
                })
                book["cover_path"] = target_cover
                try:
                    os.remove(cover_path)
                    operation_log.append({
                        "type": "file_delete",
                        "path": cover_path,
                        "status": "success"
                    })
                    deleted_originals += 1
                except Exception as e:
                    operation_log.append({
                        "type": "file_delete",
                        "path": cover_path,
                        "status": "error",
                        "error": str(e)
                    })
            except Exception as e:
                operation_log.append({
                    "type": "file_copy",
                    "source": cover_path,
                    "target": target_cover,
                    "status": "error",
                    "error": str(e)
                })
        
        # Переносим метаданные .json если есть
        if source_file:
            json_path = os.path.splitext(source_file)[0] + ".json"
            if os.path.exists(json_path):
                target_json = os.path.splitext(target_file)[0] + ".json"
                try:
                    shutil.copy2(json_path, target_json)
                    operation_log.append({
                        "type": "file_copy",
                        "source": json_path,
                        "target": target_json,
                        "status": "success"
                    })
                    try:
                        os.remove(json_path)
                        operation_log.append({
                            "type": "file_delete",
                            "path": json_path,
                            "status": "success"
                        })
                        deleted_originals += 1
                    except Exception as e:
                        operation_log.append({
                            "type": "file_delete",
                            "path": json_path,
                            "status": "error",
                            "error": str(e)
                        })
                except Exception as e:
                    operation_log.append({
                        "type": "file_copy",
                        "source": json_path,
                        "target": target_json,
                        "status": "error",
                        "error": str(e)
                    })
        
        # Переносим .txt метаданные если есть
        if source_file:
            txt_path = os.path.splitext(source_file)[0] + ".txt"
            if os.path.exists(txt_path):
                target_txt = os.path.splitext(target_file)[0] + ".txt"
                try:
                    shutil.copy2(txt_path, target_txt)
                    operation_log.append({
                        "type": "file_copy",
                        "source": txt_path,
                        "target": target_txt,
                        "status": "success"
                    })
                    try:
                        os.remove(txt_path)
                        operation_log.append({
                            "type": "file_delete",
                            "path": txt_path,
                            "status": "success"
                        })
                        deleted_originals += 1
                    except Exception as e:
                        operation_log.append({
                            "type": "file_delete",
                            "path": txt_path,
                            "status": "error",
                            "error": str(e)
                        })
                except Exception as e:
                    operation_log.append({
                        "type": "file_copy",
                        "source": txt_path,
                        "target": target_txt,
                        "status": "error",
                        "error": str(e)
                    })
        
        transferred += 1
        successful_book_ids.append(book_row["id"])
        book_log["status"] = "success"
        book_log["details"] = f"Перенесён в {target_file}"
        detailed_log.append(book_log)
    
    if transferred == 0:
        return {"success": False, "message": "Не удалось перенести ни одной книги"}
    
    # Создаём новое хранилище
    new_source_id = None
    if is_new_target:
        cursor = await db.execute(
            """INSERT INTO sources (name, type, path, total_size) VALUES (?, ?, ?, ?)""",
            (source["name"], source.get("type", "local"), target_path, source_size)
        )
        await db.commit()
        new_source_id = cursor.lastrowid
    
    # Обновляем source_id и пути для успешно перенесённых книг
    for book_row in books:
        if book_row["id"] not in successful_book_ids:
            continue
        # Находим категорию
        category_path = ""
        for cat in categories:
            if cat["id"] == book_row["category_id"]:
                category_path = cat["full_path"]
                break
        
        target_dir = os.path.join(target_path, category_path) if category_path else target_path
        source_file = book_row["file_path"]
        if source_file:
            new_relative_path = os.path.join(category_path, os.path.basename(source_file)) if category_path else os.path.basename(source_file)
            new_file_path = os.path.join(target_dir, os.path.basename(source_file))
            
            await db.execute(
                """UPDATE books SET source_id = ?, file_path = ?, relative_path = ?, is_available = 1 WHERE id = ?""",
                (new_source_id if is_new_target else target_source_id, new_file_path, new_relative_path, book_row["id"])
            )
    await db.commit()
    
    # Удаляем книги из старого хранилища, которые не удалось перенести
    if is_new_target:
        for book_row in books:
            if book_row["id"] not in successful_book_ids:
                await db.execute("DELETE FROM books WHERE id = ?", (book_row["id"],))
        await db.commit()
    
    # Удаляем старое хранилище из БД
    await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    await db.commit()
    
    # Удаляем осиротевшие книги (source_id = NULL или несуществующий source_id)
    await db.execute("DELETE FROM books WHERE source_id IS NULL")
    await db.execute("""
        DELETE FROM books 
        WHERE source_id IS NOT NULL 
        AND source_id NOT IN (SELECT id FROM sources)
    """)
    await db.commit()
    
    # Пытаемся удалить пустые папки категорий старого хранилища
    category_delete_errors = []
    try:
        for cat in categories:
            cat_full_path = os.path.join(source_path, cat["full_path"]) if cat["full_path"] else source_path
            if os.path.exists(cat_full_path) and not os.listdir(cat_full_path):
                try:
                    os.rmdir(cat_full_path)
                    operation_log.append({
                        "type": "category_delete",
                        "path": cat_full_path,
                        "status": "success"
                    })
                except Exception as e:
                    operation_log.append({
                        "type": "category_delete",
                        "path": cat_full_path,
                        "status": "error",
                        "error": str(e)
                    })
                    category_delete_errors.append(cat["full_path"])
        # Удаляем саму директорию хранилища если она пустая
        if os.path.exists(source_path) and not os.listdir(source_path):
            try:
                os.rmdir(source_path)
                operation_log.append({
                    "type": "category_delete",
                    "path": source_path,
                    "status": "success"
                })
            except Exception as e:
                operation_log.append({
                    "type": "category_delete",
                    "path": source_path,
                    "status": "error",
                    "error": str(e)
                })
    except Exception as e:
        operation_log.append({
            "type": "category_cleanup",
            "path": source_path,
            "status": "error",
            "error": str(e)
        })
    
    return {
        "success": True,
        "message": f"Перенесено {transferred} книг, удалено оригиналов: {deleted_originals}",
        "new_source_id": new_source_id if is_new_target else target_source_id,
        "transferred_count": transferred,
        "deleted_originals": deleted_originals,
        "errors_count": len(errors),
        "errors": errors,
        "detailed_log": detailed_log,
        "operation_log": operation_log,
    }


async def cleanup_unavailable_books(db: aiosqlite.Connection) -> int:
    """Удаляет все недоступные книги. Возвращает количество удалённых."""
    cursor = await db.execute("SELECT COUNT(*) FROM books WHERE is_available = 0")
    count = (await cursor.fetchone())[0]
    
    if count > 0:
        await db.execute("DELETE FROM books WHERE is_available = 0")
        await db.commit()
    
    return count


async def update_source_scan_time(db: aiosqlite.Connection, source_id: int):
    await db.execute(
        "UPDATE sources SET last_scanned = CURRENT_TIMESTAMP WHERE id = ?", (source_id,)
    )
    await db.commit()


async def get_books_by_source(
    db: aiosqlite.Connection, source_id: int, limit: int = 20, offset: int = 0
):
    cursor = await db.execute(
        """SELECT b.*, c.full_path as category_name, s.name as source_name
        FROM books b
        LEFT JOIN category_paths c ON b.category_id = c.id
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

    books = []
    for row in rows:
        book = dict(row)
        stored = book.get("is_available")
        if stored is None or stored == '':
            book["is_available"] = os.path.exists(book.get("file_path", ""))
        else:
            book["is_available"] = bool(stored)
        books.append(book)

    return books, total


async def get_books_by_source_all(db: aiosqlite.Connection, source_id: int):
    cursor = await db.execute(
        """
        SELECT b.*, c.name as category_name, s.name as source_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN sources s ON b.source_id = s.id
        WHERE b.source_id = ?
        ORDER BY b.id DESC
    """,
        (source_id,),
    )
    rows = await cursor.fetchall()
    books = []
    for row in rows:
        book = dict(row)
        stored = book.get("is_available")
        if stored is None or stored == '':
            book["is_available"] = os.path.exists(book.get("file_path", ""))
        else:
            book["is_available"] = bool(stored)
        books.append(book)
    return books


async def confirm_book_presence(db: aiosqlite.Connection, book_id: int, filepath: str = None):
    """Подтверждение наличия книги при сканировании.

    Обновляет:
    - is_available = 1 (книга в наличии)
    - last_seen = CURRENT_TIMESTAMP (время последнего подтверждения)
    - cover_ext (если найдена обложка - обновляем, иначе очищаем)
    Флаг is_new_arrival НЕ сбрасывается (сбрасывается через 7 дней)
    """
    from services.importer import find_cover_file
    
    cover_file, cover_ext = find_cover_file(filepath) if filepath else (None, None)
    
    if filepath:
        await db.execute(
            "UPDATE books SET is_available = 1, last_seen = CURRENT_TIMESTAMP, cover_ext = ? WHERE id = ?",
            (cover_ext or "", book_id),
        )
    else:
        await db.execute(
            "UPDATE books SET is_available = 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
            (book_id,),
        )
    await db.commit()


async def mark_books_missing(db: aiosqlite.Connection, source_id: int, exclude_paths: list):
    """Пометка отсутствующих книг в хранилище.

    Книги, которых нет в exclude_paths, помечаются как отсутствующие:
    - is_available = 0 (красный цвет карточки в UI)

    Args:
        source_id: ID хранилища
        exclude_paths: список relative_path книг, которые ЕСТЬ в файловой системе
    """
    if not exclude_paths:
        # Все книги хранилища отсутствуют
        await db.execute(
            "UPDATE books SET is_available = 0 WHERE source_id = ?",
            (source_id,),
        )
    else:
        # Помечаем только те, которых нет в списке найденных
        placeholders = ",".join("?" * len(exclude_paths))
        await db.execute(
            f"UPDATE books SET is_available = 0 WHERE source_id = ? AND relative_path NOT IN ({placeholders})",
            (source_id, *exclude_paths),
        )
    await db.commit()


async def upsert_book_preserve(db: aiosqlite.Connection, book_data: dict):
    """Обновление или вставка книги с сохранением существующих данных.
    
    Логика:
    - Если книга существует (source_id + relative_path):
      * Подтверждает наличие (is_available=1, last_seen)
      * НЕ перезаписывает данные (использует COALESCE)
    - Если новая:
      * Создает запись с флагом is_new_arrival=1
    """
    source_id = book_data.get("source_id")
    relative_path = book_data.get("relative_path", "")

    cursor = await db.execute(
        "SELECT id FROM books WHERE source_id = ? AND relative_path = ?",
        (source_id, relative_path),
    )
    existing = await cursor.fetchone()

    if existing:
        # Книга существует - обновляем только при необходимости
        book_id = existing[0]
        await db.execute(
            """
            UPDATE books SET
                title = COALESCE(?, title),
                author = COALESCE(?, author),
                publisher = COALESCE(?, publisher),
                isbn = COALESCE(?, isbn),
                year = COALESCE(?, year),
                pages = COALESCE(?, pages),
                format = COALESCE(?, format),
                file_size = COALESCE(?, file_size),
                file_path = COALESCE(?, file_path),
                cover_path = COALESCE(?, cover_path),
                category_id = COALESCE(?, category_id),
                language = COALESCE(?, language),
                source_url = COALESCE(?, source_url),
                is_available = 1,
                last_seen = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                book_data.get("title"),
                book_data.get("author"),
                book_data.get("publisher"),
                book_data.get("isbn"),
                book_data.get("year"),
                book_data.get("pages"),
                book_data.get("format"),
                book_data.get("file_size"),
                book_data.get("file_path"),
                book_data.get("cover_path"),
                book_data.get("category_id"),
                book_data.get("language"),
                book_data.get("source_url"),
                book_id,
            ),
        )
        await db.commit()
        return book_id, False
    else:
        # Новая книга - создаем с флагом нового поступления
        cursor = await db.execute(
            """
            INSERT INTO books (
                title, author, publisher, isbn, year, pages,
                format, file_size, description, file_path, relative_path,
                cover_path, category_id, source_id, language, source_url,
                is_available, is_new_arrival, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, CURRENT_TIMESTAMP)
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
        return cursor.lastrowid, True


async def reset_stale_new_arrivals(db: aiosqlite.Connection, source_id: int):
    """Сброс флага is_new_arrival для книг старше 7 дней.

    Вызывается перед сканированием хранилища.
    Флаг сбрасывается только если книга была подтверждена более 7 дней назад.
    """
    await db.execute(
        """
        UPDATE books SET is_new_arrival = 0
        WHERE source_id = ?
          AND is_new_arrival = 1
          AND last_seen < datetime('now', '-7 days')
        """,
        (source_id,),
    )
    await db.commit()


async def export_book_to_json(db: aiosqlite.Connection, book_id: int) -> dict:
    """Экспорт данных книги в .json файл.

    Файл создаётся в той же директории, что и книга:
    {source_path}/{category}/{book_filename}.json
    """
    book = await get_book_by_id(db, book_id)
    if not book:
        return {"success": False, "message": "Book not found"}

    source_path = book.get("source_name", "")
    cursor = await db.execute("SELECT path FROM sources WHERE id = ?", (book.get("source_id"),))
    source_row = await cursor.fetchone()
    if not source_row:
        return {"success": False, "message": "Source not found"}

    source_base_path = source_row[0]

    book_relative_path = book.get("relative_path", "")
    book_dir = os.path.dirname(book_relative_path) if book_relative_path else ""
    book_filename = os.path.splitext(os.path.basename(book.get("file_path", "book")))[0]

    json_dir = os.path.join(source_base_path, book_dir) if book_dir else source_base_path
    json_path = os.path.join(json_dir, f"{book_filename}.json")

    os.makedirs(json_dir, exist_ok=True)

    json_data = {
        "version": "1.0",
        "book_id": book_id,
        "title": book.get("title", ""),
        "author": book.get("author", ""),
        "publisher": book.get("publisher", ""),
        "isbn": book.get("isbn", ""),
        "year": book.get("year"),
        "pages": book.get("pages"),
        "format": book.get("format", ""),
        "description": book.get("description", ""),
        "language": book.get("language", "ru"),
        "source_url": book.get("source_url", ""),
        "cover_ext": book.get("cover_ext", ""),
    }

    import json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return {"success": True, "path": json_path}


async def move_book_files(db: aiosqlite.Connection, book_id: int, new_category_id: int) -> dict:
    """Перемещение всех файлов книги в новую категорию.

    Перемещаемые файлы: .djvu/.pdf/.rar/.zip, .txt, .jpg/.png и .json
    Возвращает обновлённые пути книги.
    """
    book = await get_book_by_id(db, book_id)
    if not book:
        return {"success": False, "message": "Book not found", "old_path": "", "new_path": ""}

    old_relative_path = book.get("relative_path", "")
    old_file_path = book.get("file_path", "")

    if not old_file_path:
        return {"success": False, "message": "File path empty", "old_path": "", "new_path": ""}

    old_base = os.path.basename(old_file_path)
    old_ext = os.path.splitext(old_base)[1]
    old_filename = os.path.splitext(old_base)[0]
    old_dir = os.path.dirname(old_file_path)

    cursor = await db.execute("SELECT path FROM sources WHERE id = ?", (book.get("source_id"),))
    source_row = await cursor.fetchone()
    if not source_row:
        return {"success": False, "message": "Source not found", "old_path": old_file_path, "new_path": ""}

    source_base_path = source_row[0]

    cursor = await db.execute("SELECT name FROM categories WHERE id = ?", (new_category_id,))
    cat_row = await cursor.fetchone()
    new_category_name = cat_row[0] if cat_row else "Unknown"

    new_dir = os.path.join(source_base_path, new_category_name)
    os.makedirs(new_dir, exist_ok=True)

    extensions_to_move = [
        old_ext,
        ".txt",
        ".html",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".json",
    ]

    new_file_path = os.path.join(new_dir, old_base)
    new_relative_path = os.path.join(new_category_name, old_base)

    if old_file_path != new_file_path:
        if os.path.exists(old_file_path):
            os.rename(old_file_path, new_file_path)
        new_file_path = os.path.normpath(new_file_path)

    for ext in extensions_to_move:
        if ext == old_ext:
            continue
        old附属 = os.path.join(old_dir, f"{old_filename}{ext}")
        new附属 = os.path.join(new_dir, f"{old_filename}{ext}")
        if os.path.exists(old附属):
            try:
                os.rename(old附属, new附属)
            except FileExistsError:
                os.remove(new附属)
                os.rename(old附属, new附属)

    return {
        "success": True,
        "old_path": old_file_path,
        "new_path": new_file_path,
        "new_relative_path": new_relative_path,
        "new_dir": new_dir,
    }
