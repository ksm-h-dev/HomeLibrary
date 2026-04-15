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
│   ├── models.py          # Pydantic models
│   └── routers/           # API endpoints
│       ├── books.py      # Books API
│       ├── search.py     # Search API
│       └── sources.py    # Storage sources API
├── services/
│   ├── importer.py        # Scans filesystem, imports to DB
│   └── drives.py          # Windows drive discovery (WMI)
├── web/
│   └── index.html         # SPA frontend
└── library.db             # SQLite database (created on first run)
```

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | Books directory, DB path, server port |
| `services/importer.py` | Scans filesystem, parses metadata (KOI8-R, CP1251), imports to DB |
| `services/drives.py` | Discovers Windows drives via WMI/PowerShell |
| `app/database.py` | SQLite init, FTS5 triggers, CRUD helpers |
| `app/routers/sources.py` | Storage management API (CRUD, scan, discover) |
| `web/index.html` | Browser client - search, browse, manage sources |

## Database

- SQLite with FTS5 virtual table for full-text search
- Triggers auto-update FTS index on INSERT/UPDATE/DELETE to `books`
- `books` table: unique index on `file_path`
- `sources` table: storage locations (HDD, SSD, DVD, NAS, network)

## Storage Sources

Sources table supports: `local`, `hdd`, `ssd`, `dvd`, `nas`, `network`, `cloud`

Each book links to a source via `source_id` foreign key.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web interface |
| `GET /api/books` | List books (limit, offset, category) |
| `GET /api/books/{id}` | Book details |
| `GET /api/search?q=...` | Full-text search (FTS5) |
| `GET /api/categories` | Category list |
| `GET /api/stats` | Library statistics |
| `GET /api/sources` | List storage sources |
| `POST /api/sources` | Add new source |
| `DELETE /api/sources/{id}` | Remove source |
| `POST /api/sources/{id}/scan` | Scan source and import books |
| `GET /api/sources/discover` | Auto-detect Windows drives |

## Search

- FTS5 indexes: `title`, `author`, `description`
- Search query format: `"{query}"*` (prefix search)
- Search results include `title_hl` (highlighted) and `desc_snippet`
