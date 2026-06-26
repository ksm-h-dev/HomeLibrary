[**English**](AGENTS.md) | [**Русский**](AGENTS.ru.md)

# Library Project - Home Librarian

## Quick Start

```powershell
cd C:\Library
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the script:
```powershell
.\start_server.cmd
```

## Project Structure

```
H:\Work.Py\HomeLibrary\
├── app/
│   ├── main.py            # FastAPI entry point, startup events
│   ├── database.py        # SQLite + FTS5 full-text search
│   ├── models.py          # Pydantic models
│   └── routers/
│       ├── books.py      # Books API (CRUD, duplicates, save-metadata)
│       ├── lookup.py     # External lookup proxy (ISBN/DOI/ISSN)
│       ├── search.py     # Search API
│       ├── sources.py    # Storage sources API
│       └── welcome.py    # Setup wizard + About page API
├── services/
│   ├── importer.py        # Scans filesystem, imports to DB
│   ├── lookup.py          # External API lookup (OpenLibrary, CrossRef, ISSN)
│   ├── drives.py          # Windows drive discovery (WMI)
│   ├── audit.py           # Audit logging system
│   └── progress.py        # Progress tracker for SSE scan events
├── web/
│   ├── index.html         # SPA frontend (3 tabs, view modes, modals)
│   ├── about.html         # About page
│   └── setup.html         # First-run setup wizard
├── config.py              # Configuration (DEFAULT_SOURCE_PATH, AUDIT_ENABLED, etc.)
├── settings.json          # Persisted runtime settings (audit_enabled)
├── start_server.cmd      # Quick start script
├── library.db             # SQLite database
└── requirements.txt     # Python dependencies
```

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | Books dir, DB path, server port, DEFAULT_SOURCE_PATH, COVER_EXTENSIONS, AUDIT_ENABLED, SUPPORTED_FORMATS (pdf/djvu/rar/zip/rtf/7z) |
| `services/importer.py` | Scans filesystem, parses metadata (.json/.txt, KOI8-R/CP1251), imports to DB, confirms availability, marks new arrivals, tracks covers_found, finds multi-part archive siblings (extra_files) |
| `services/drives.py` | Discovers Windows drives via WMI/PowerShell |
| `services/audit.py` | Audit logging system for tracking user actions |
| `services/progress.py` | Progress tracker for SSE scan events (fixes duplicate complete events) |
| `app/database.py` | SQLite init, FTS5 triggers, CRUD helpers, export_book_to_json, move_book_files, transfer_source, availability logic, new arrivals handling, extra_files support |
| `app/routers/books.py` | Book CRUD API with export/move on update, translated messages to Russian |
| `app/routers/lookup.py` | External lookup proxy (ISBN/DOI/ISSN) |
| `app/routers/sources.py` | Storage management API (CRUD, scan with scanned/imported/confirmed/covers_found stats, transfer with progress, translated messages) |
| `app/routers/welcome.py` | First-run setup, about page API, initialize library (clears books + sources + categories), translated messages |
| `web/index.html` | Browser client - search, browse, manage sources, cover preview modal, availability filters, color-coded cards, **4 view modes (tile/cover/list/table)**, custom modal dialogs (replaces alert/confirm), tools tab with DB initialize and **duplicates finder** |
| `web/setup.html` | First-run setup wizard |
| `web/about.html` | About page |

## Database

- SQLite with FTS5 virtual table for full-text search
- Triggers auto-update FTS index on INSERT/UPDATE/DELETE to `books`
- `books` table: unique index on `source_id + relative_path` (no duplicates)
- New fields: `cover_ext` (cover: jpg/png/gif/webp/bmp/tiff), `is_available`, `is_new_arrival`, `last_seen`, `format`
- `extra_files` (TEXT) — JSON array of paths to multi-part archives (.part2.rar, .7z.002)

## Storage Sources

Sources table supports: `local`, `hdd`, `ssd`, `dvd`, `nas`, `network`, `cloud`

**Deleting a source:** When a source is deleted, all associated books are also deleted (cascading deletion).

**Identification:**
1. `catalog.json` → `id` field (preferred for removable media)
2. Volume label (Windows volume label)
3. Path fallback

**Scan logic:**
- Existing books: confirmation of availability (update `is_available`, `last_seen`) without overwriting data
- New books: added with flag `is_new_arrival = 1`
- Missing books: marked `is_available = 0` (red card color)
- The "New arrival" flag is reset 7 days after confirmation

## First Run (Auto-start)

```
1. Server starts → checkSetup() in JavaScript
2. Check: sources=0 and DEFAULT_SOURCE_PATH configured?
3. If yes → ask "Auto-scan?"
4. If no/decline → redirect to /setup
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
| `/api/books` | GET | List books (limit, offset, category, format, year, source_id, sort_by, **availability**) |
| `/api/books/{id}` | GET | Book details |
| PUT | `/api/books/{id}` | Update book (exports metadata to .json, moves files) |
| `/api/search?q=...` | GET | Full-text search (FTS5) with **availability** filter |
| `/api/categories` | GET | Category list |
| `/api/stats` | GET | Library statistics |
| `/api/sources` | GET/POST | List/add storage sources |
| `/api/sources/{id}` | GET/PUT/DELETE | Source CRUD |
| `/api/sources/{id}/scan` | POST | Scan source (returns: scanned, imported, confirmed, covers_found, missing, missing_books) |
| `/api/sources/{id}/books` | GET | Books in source |
| `/api/sources/discover` | GET | Auto-detect Windows drives |
| `/api/sources/{id}/transfer` | POST | Transfer source to new location |
| `/api/books/{id}/open` | POST | Open book file |
| `/api/setup/status` | GET | Setup status |
| `/api/setup/drives` | GET | Available drives |
| `/api/setup/select-folder` | POST | Open folder browser dialog |
| `/api/setup/save-path` | POST | Save path to config.py |
| `/api/setup/scan` | POST | Initial scan |
| `/api/setup/skip` | POST | Skip setup |
| `/api/setup/initialize` | POST | Reset library (delete all books + sources + categories, returns categories_deleted) |
| `/api/cover?path=...` | GET | Serve cover image (proxy) |
| `/api/setup/audit/toggle` | POST | Toggle audit logging (persists to settings.json, no server restart) |
| `/api/books/duplicates` | GET | Find duplicate books (same source + size + filename) |
| `/api/books/duplicates/merge` | POST | Delete selected duplicate records |
| `/api/books/cleanup` | POST | Remove all unavailable books |

## Search

- FTS5 indexes: `title`, `author`, `description`
- Search query format: `{query}*` (prefix search)
- Search results include `title_hl` and `desc_snippet`
- Search supports `availability` filter: `available`, `missing`, `new`

## Categories

- **Structure**: hierarchy via `parent_id`, full_path computed through VIEW `category_paths`
- **Uniqueness**: each category is tied to a `source_id`
- **Filter**: searches by the last part of the path (after `/`), examples:
  - `Soft/Server 2003` → searches for `Server 2003`
  - `Study/Soft/Server 2003` → searches for `Server 2003`
  - `Books/Languages/English` → searches for `English`

## Configuration (config.py)

```python
import os

DATABASE_URL = os.getenv("LIBRARY_DB", "library.db")
SERVER_HOST = os.getenv("LIBRARY_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("LIBRARY_PORT", "8000"))

DEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", "H:/Book")
SHOW_WELCOME = os.getenv("LIBRARY_SHOW_WELCOME", "true")

SUPPORTED_FORMATS = ["pdf", "djvu", "rar", "zip", "rtf", "7z"]
SUPPORTED_METADATA_EXT = ["txt", "json"]
COVER_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"]

AUDIT_ENABLED = os.getenv("LIBRARY_AUDIT_ENABLED", "true").lower() == "true"
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
```

Runtime settings (audit_enabled) are stored in `settings.json`, not in `config.py` — this prevents uvicorn from restarting when toggling.

## Features

- **Full-text search** using SQLite FTS5
- **Cascading deletion** of sources, books and categories
- **Library initialization** - full database cleanup
- **Source management** - add, edit, delete, transfer with progress bar
- **Auto-scan on first run** (optional)
- **Manual scan** - button-only, SSE progress
- **Metadata** - KOI8-R, CP1251 support, .json priority over .txt
- **Category** - determined by folder name, tied to source (source_id)
- **Availability confirmation** - books are confirmed during scan without overwriting data
- **New arrivals** - is_new_arrival flag (resets after 7 days)
- **Availability filtering** - available/missing/new arrivals
- **Color indication** - green (available), red (missing)
- **Metadata export** - when editing a book, metadata is exported to .json
- **File moving** - when path changes, all book files are moved (.pdf + .json + .txt + cover)
- **Multi-part archive support** - .part1.rar, .part2.rar, etc. (extra_files)
- **Extended cover formats** - bmp, webp, tiff
- **Book covers** - automatic detection during scan, show on click
- **Cover proxy** - `/api/cover?path=...` for secure image loading
- **Three interface tabs**: Catalog, Sources, Tools
- **Four view modes**: Tile, Covers (30 books per page), List, Table (with column sorting)
- **Source name on card** - in all view modes
- **Duplicate search and removal** - automatic detection by (source_id + file_size + filename) with best record selection
- **Extended book editing**: publisher, pages, format, language
- **Audit logs** - user action tracking (services/audit.py, setting stored in settings.json)
- **Progress tracker** - SSE events for scanning without duplication (services/progress.py)
- **Custom modal dialogs** - replacing alert()/confirm() with a unified style
- **Message translation** - API returns messages in Russian
- **Scan statistics fix** - correct counting of imported/confirmed/covers_found
