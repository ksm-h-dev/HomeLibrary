# Library Project - Домашний библиотекарь

## Quick Start

```powershell
cd C:\Library
pip install -r requirements.txt
python -m services.importer   # scan C:\Book\ and populate database
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Project Structure

```
C:\Library\
├── app/                    # FastAPI application
│   ├── main.py            # Entry point
│   ├── database.py        # SQLite + FTS5 full-text search
│   └── routers/           # API endpoints
├── services/
│   └── importer.py        # Scans C:\Book\ for books, parses .txt metadata
├── web/
│   └── index.html         # SPA frontend
└── library.db             # SQLite database (created on first run)
```

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | Books directory (`C:\Book\`), DB path, server port |
| `services/importer.py` | Scans filesystem, parses metadata (KOI8-R, CP1251 encoding), imports to DB |
| `app/database.py` | SQLite init, FTS5 triggers, CRUD helpers |
| `web/index.html` | Browser client - search, browse, open files |

## Database

- SQLite with FTS5 virtual table for full-text search
- Triggers auto-update FTS index on INSERT/UPDATE/DELETE to `books`
- Books table has unique constraint on `file_path`

## Books Source

Books directory: `C:\Book\` (configurable via `BOOKS_DIR` in `config.py`)

Expected file layout per book:
- `book.pdf` / `book.djvu` / `book.rar` / `book.zip`
- `book.txt` (metadata, KOI8-R or CP1251 encoded)
- `book.jpg` (optional cover)

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web interface |
| `GET /api/books` | List books (limit, offset, category) |
| `GET /api/books/{id}` | Book details |
| `GET /api/search?q=...` | Full-text search (FTS5) |
| `GET /api/categories` | Category list |
| `GET /api/stats` | Library statistics |

## Search

- FTS5 indexes: `title`, `author`, `description`
- Search query format: `"{query}"*` (prefix search)
- Search results include `title_hl` (highlighted) and `desc_snippet`
