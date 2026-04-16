# Library Project - Домашний библиотекарь

## Quick Start

```powershell
cd C:\Library
.\start_server.cmd
```

Или вручную:
```powershell
pip install -r requirements.txt
python reset_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure

```
C:\Library\
├── app/
│   ├── main.py            # FastAPI entry point, startup events
│   ├── database.py        # SQLite + FTS5 full-text search
│   ├── models.py          # Pydantic models
│   └── routers/
│       ├── books.py      # Books API
│       ├── search.py     # Search API
│       ├── sources.py    # Storage sources API
│       └── welcome.py    # Setup wizard + About page API
├── services/
│   ├── importer.py        # Scans filesystem, imports to DB
│   └── drives.py          # Windows drive discovery (WMI)
├── web/
│   ├── index.html         # SPA frontend
│   ├── about.html         # About page
│   └── setup.html         # First-run setup wizard
├── config.py              # Configuration
├── start_server.cmd      # Quick start script
└── library.db             # SQLite database (created on first run)
```

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | Books dir, DB path, server port, DEFAULT_SOURCE_PATH |
| `services/importer.py` | Scans filesystem, parses metadata (KOI8-R, CP1251), imports to DB |
| `services/drives.py` | Discovers Windows drives via WMI/PowerShell |
| `app/database.py` | SQLite init, FTS5 triggers, CRUD helpers |
| `app/routers/sources.py` | Storage management API (CRUD, scan, discover) |
| `app/routers/welcome.py` | First-run setup, about page API |
| `web/index.html` | Browser client - search, browse, manage sources |
| `web/setup.html` | First-run setup wizard |
| `web/about.html` | About page |

## Database

- SQLite with FTS5 virtual table for full-text search
- Triggers auto-update FTS index on INSERT/UPDATE/DELETE to `books`
- `books` table: unique index on `source_id + relative_path` (no duplicates)
- `sources` table: storage locations (HDD, SSD, DVD, NAS, network)
- `sources` has `volume_label` and `catalog_id` for portable media identification

## Storage Sources

Sources table supports: `local`, `hdd`, `ssd`, `dvd`, `nas`, `network`, `cloud`

**Identification priority:**
1. `catalog.json` → `id` field (preferred for portable media)
2. Volume label (Windows drive label)
3. Path fallback

**Upsert behavior:** On rescan, existing books are updated (all fields) not duplicated.

## First Run

```
1. Server starts → check_initial_setup()
2. If sources=0 AND DEFAULT_SOURCE_PATH configured → auto-import
3. User opens / → checkSetup() in JS
4. If needs_setup → redirect to /setup
5. User selects folder → /api/setup/save-path
6. Scan runs → books imported with source_id
7. Redirect to /
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/about` | GET | About page |
| `/setup` | GET | First-run setup wizard |
| `/api/health` | GET | Health check |
| `/api/books` | GET | List books (limit, offset, category) |
| `/api/books/{id}` | GET | Book details |
| `/api/search?q=...` | GET | Full-text search (FTS5) |
| `/api/categories` | GET | Category list |
| `/api/stats` | GET | Library statistics |
| `/api/sources` | GET/POST | List/add storage sources |
| `/api/sources/{id}` | GET/PUT/DELETE | Source CRUD |
| `/api/sources/{id}/scan` | POST | Scan source and import books |
| `/api/sources/discover` | GET | Auto-detect Windows drives |
| `/api/setup/status` | GET | Setup status |
| `/api/setup/drives` | GET | Available drives |
| `/api/setup/select-folder` | POST | Open folder browser dialog |
| `/api/setup/save-path` | POST | Save path to config.py |
| `/api/setup/scan` | POST | Initial scan |
| `/api/setup/skip` | POST | Skip setup |

## Search

- FTS5 indexes: `title`, `author`, `description`
- Search query format: `{query}*` (prefix search)
- Search results include `title_hl` and `desc_snippet`

## Configuration (config.py)

```python
BOOKS_DIR = "C:/Book/"           # CLI import path
DATABASE_URL = "library.db"      # DB path
SERVER_HOST = "0.0.0.0"         # LAN access
SERVER_PORT = 8000              # Port
DEFAULT_SOURCE_PATH = ""         # Auto-import path (set manually)
SHOW_WELCOME = "true"           # Show welcome on first run
```
