import sqlite3
import os

# Delete existing database
if os.path.exists("library.db"):
    os.remove("library.db")
    print("Database deleted")

# Create fresh database
conn = sqlite3.connect("library.db")
cursor = conn.cursor()

# Create tables
cursor.executescript("""
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_books_source_relpath ON books(source_id, relative_path);

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

conn.commit()
conn.close()

print("Fresh database created - ready for first-run test")
