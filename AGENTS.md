# Library Project - Домашний библиотекарь

## Quick Start

```powershell
cd H:\Work.Py\HomeLibrary
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Или использовать скрипт:
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
├── library.db             # SQLite database
└── requirements.txt     # Python dependencies
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

**Удаление хранилища:** При удалении хранилища удаляются все связанные книги (каскадное удаление).

**Идентификация:**
1. `catalog.json` → `id` поле (предпочтительно для съемных носителей)
2. Volume label (метка тома Windows)
3. Path fallback

**Upsert behavior:** При повторном сканировании существующие книги обновляются, а не дублируются.

## First Run (Автозапуск)

```
1. Server starts → checkSetup() в JavaScript
2. Проверка: sources=0 и DEFAULT_SOURCE_PATH настроен?
3. Если да → спросить "Автоматически просканировать?"
4. Если нет/отказ → переход к /setup
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
| `/api/sources/{id}/books` | GET | Books in source |
| `/api/sources/discover` | GET | Auto-detect Windows drives |
| `/api/setup/status` | GET | Setup status |
| `/api/setup/drives` | GET | Available drives |
| `/api/setup/select-folder` | POST | Open folder browser dialog |
| `/api/setup/save-path` | POST | Save path to config.py |
| `/api/setup/scan` | POST | Initial scan |
| `/api/setup/skip` | POST | Skip setup |
| `/api/setup/initialize` | POST | Reset library (delete all) |

## Search

- FTS5 indexes: `title`, `author`, `description`
- Search query format: `{query}*` (prefix search)
- Search results include `title_hl` and `desc_snippet`

## Configuration (config.py)

```python
import os

BOOKS_DIR = os.getenv("LIBRARY_BOOKS_DIR", "H:/Book/")
DATABASE_URL = os.getenv("LIBRARY_DB", "library.db")
SERVER_HOST = os.getenv("LIBRARY_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("LIBRARY_PORT", "8000"))

DEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", "H:/Book")
SHOW_WELCOME = os.getenv("LIBRARY_SHOW_WELCOME", "true")

SUPPORTED_FORMATS = ["pdf", "djvu", "rar", "zip", "rtf"]
SUPPORTED_METADATA_EXT = ["txt", "html"]
COVER_EXTENSIONS = ["jpg", "jpeg", "png", "gif"]
```

## Features

- **Full-text search** с использованием SQLite FTS5
- **Каскадное удаление** хранилищ и книг
- **Инициализация библиотеки** - полный сброс базы данных
- **Автосканирование** при первом запуске с конфигом
- **Метаданные** - поддержка KOI8-R, CP1251 кодировок
- **Категория** - определяется по имени папки
