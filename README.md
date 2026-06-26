[**English**](README.md) | [**Русский**](README.ru.md)

# Home Librarian

Web application for cataloging and searching an electronic library with access via local network.

## Features

- Automatic import of books from the filesystem
- Full-text search by title, author, and description (FTS5)
- Categorization and tagging of books
- **Multi-source management** (HDD, SSD, DVD, NAS, network shares)
- **Media identification** (catalog.json or volume label)
- **Availability confirmation** - during scanning, books are confirmed without overwriting data
- **New arrivals** - `is_new_arrival` flag (resets after 7 days)
- **Availability filtering** - available/missing/new arrivals
- **Color coding** - green (available), red (missing)
- **Auto-detection of connected drives**
- Web interface for browsing the catalog
- **Unified search and filtering** (Search/Filter/Sort/Reset)
- **Sorting** by date, title, author, year, pages
- **Filtering** by format, category, year, source, availability
- **Metadata export** to .json when editing a book
- **Code-based metadata lookup** — ISBN/DOI/ISSN via OpenLibrary, CrossRef, ISSN Portal
- **Auto-detection of code type** (ISBN-10, ISBN-13, DOI, ISSN, UDC, LCC, GRNTI)
- **JSON sidecar (.lookup.json)** — saves raw API data during code lookup
- **File relocation** for books (book + txt/json + cover + extra_files)
- **.json metadata priority** over .txt during import
- **Extended cover formats** (bmp, webp, tiff)
- **Multi-part archive support** (.part1.rar, .part2.rar, .7z.001, .7z.002)
- **Audit logs** - tracking user actions
- **Progress tracker** - SSE events for scanning without duplication
- **Custom modal dialogs** - replacing alert()/confirm() with a unified style
- **Message translation** - API returns messages in Russian
- **Scan statistics fix** - correct counting of imported/confirmed/covers_found
- **Three interface tabs**: Catalog, Sources, Tools
- **Library initialization** (Tools → Erase database) clearing books, sources, and categories
- Access to the library via browser on the local network

## Requirements

- Python 3.11+
- Windows or Linux
- Browser to access the web interface

## Installation

### 1. Clone or copy the project

```bash
cd C:\Library
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn aiosqlite
```

## Project Structure

```
Library/
├── library.db           # SQLite database
├── README.md            # This file
├── AGENTS.md            # Documentation for AI agents
├── ARCHITECTURE.md      # System architecture
├── config.py            # Configuration
├── requirements.txt     # Dependencies
├── reset_db.py          # Database reset
├── start_server.cmd     # Startup script
├── app/
│   ├── main.py          # FastAPI application
│   ├── database.py      # SQLite + FTS5, availability logic
│   ├── models.py        # Pydantic models
│   └── routers/
│       ├── books.py     # Books API (including save-metadata)
│       ├── lookup.py    # Code-based metadata lookup API
│       ├── search.py    # Search API
│       ├── sources.py   # Sources API
│       └── welcome.py   # Setup and About API
├── services/
│   ├── importer.py     # Import, scanning, new arrivals, multi-part archives
│   ├── lookup.py       # Code lookup (OpenLibrary, CrossRef, ISSN Portal)
│   ├── drives.py       # Drive detection (WMI)
│   ├── audit.py        # Audit logs
│   └── progress.py     # SSE progress tracker
└── web/
    ├── index.html       # SPA interface (3 tabs, custom modal dialogs)
    ├── setup.html       # First-run setup wizard
    └── about.html       # About page
```

## Quick Start

### 1. Import the library

```bash
python -m app.services.importer
```

This command scans the `C:\Book\` directory and imports all books into the database.

### 2. Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Access the library

- **Locally:** http://localhost:8000
- **On the network:** http://COMPUTER_NAME:8000

## Configuration

Settings are stored in the `config.py` file:

```python
BOOKS_DIR = "C:/Book/"           # Books directory
DATABASE_URL = "library.db"     # Database path
SERVER_HOST = "0.0.0.0"         # Host to listen on
SERVER_PORT = 8000               # Server port
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| GET | `/about` | About page |
| GET | `/setup` | First-run setup wizard |
| GET | `/api/health` | Health check |
| GET | `/api/books` | List books (params: limit, offset, category, format, year, source_id, sort_by, **availability**) |
| GET | `/api/books/{id}` | Book details |
| PUT | `/api/books/{id}` | Update book (export .json, move files) |
| GET | `/api/search` | Full-text search (parameter **availability**) |
| GET | `/api/categories` | List categories |
| GET | `/api/stats` | Library statistics |
| GET/POST | `/api/sources` | List/add storage sources |
| GET/PUT/DELETE | `/api/sources/{id}` | Source CRUD |
| POST | `/api/sources/{id}/scan` | Scan (returns: scanned, imported, confirmed, covers_found, missing, missing_books) |
| GET | `/api/sources/{id}/books` | Books in source |
| POST | `/api/sources/{id}/transfer` | Transfer source |
| GET | `/api/sources/discover` | Auto-detect drives |
| GET | `/api/setup/status` | Setup status |
| GET | `/api/setup/drives` | List available drives |
| POST | `/api/setup/select-folder` | Folder selection dialog |
| POST | `/api/setup/save-path` | Save path to config.py |
| POST | `/api/setup/scan` | Initial scan |
| POST | `/api/setup/skip` | Skip setup |
| POST | `/api/setup/initialize` | Reset library (deletes books + sources + categories) |
| POST | `/api/books/{id}/open` | Open book file |
| POST | `/api/books/{id}/save-metadata` | Save .lookup.json (code lookup result) |
| POST | `/api/lookup` | Code-based metadata lookup (ISBN/DOI/ISSN) via external APIs |
| GET | `/api/lookup/by-classification` | Search books by code in local database |
| GET | `/api/audit-log` | View audit logs (if enabled) |

### /api/books Parameters

```
GET /api/books?limit=20&offset=0&category=Programming&format=pdf&year=2020&source_id=1&sort_by=title&availability=new
```

- `limit` - result count (default 20)
- `offset` - pagination offset
- `category` - book category (filter by last path segment, e.g. `Books/English` → searches `English`)
- `format` - file format (pdf, djvu, rar, zip)
- `year` - publication year
- `source_id` - Source ID
- `sort_by` - sorting: date, title, author, year, pages
- `availability` - availability filter: `available`, `missing`, `new`

### /api/search Parameters

```
GET /api/search?q=python&format=pdf&year=2020&sort_by=title&availability=new
```

- `q` - search query
- `format` - file format
- `category` - category
- `year` - publication year
- `source_id` - Source ID
- `sort_by` - sorting: date, title, author, pages
- `limit` - result count
- `offset` - offset
- `availability` - availability filter: `available`, `missing`, `new`

## Metadata Format (.txt / .json)

The system automatically extracts metadata from `.txt` or `.json` files accompanying a book:

### Priority: .json → .txt

**`.json` (recommended):**
```json
{
  "author": "Author",
  "title": "Book Title",
  "publisher": "Publisher",
  "isbn": "5-94057-183-2",
  "year": 2004,
  "pages": 192,
  "description": "Book description..."
}
```

**`.txt` (legacy format):**

```
File: book_name.rar
URL: http://example.com/link
Size: 3.87 MB (3872237)
Date: 01.02.2006 17:55:09
Description:
Author: Author Name
Title: Book Title
Publisher: Publisher
ISBN: 5-94057-183-2
Year: 2004
Pages: 192
Format: PDF
Size: 5.11 MB
```

## Preparing DVD/Removable Media

### Directory Structure on Media

```
E:\
├── catalog.json            ← source identifier (optional)
├── programs/
│   ├── book1.pdf
│   ├── book1.txt          ← metadata
│   └── book1.jpg          ← cover
└── psychology/
    └── book2.djvu
```

### catalog.json File (recommended)

Create a `catalog.json` file in the root of the media for unique identification:

```json
{
  "id": "DVD-PROG-001",
  "name": "DVD Programming 2024",
  "version": "1.0",
  "created": "2024-01-15"
}
```

**Identification priority:**
1. `catalog.json` → `id` (most reliable)
2. Volume label of the disk
3. Fallback: file path

### Scan Behavior

**Scan logic:**
- Existing books: availability confirmation (update `is_available`, `last_seen`) without overwriting data
- New books: added with flag `is_new_arrival = 1`
- Missing books: marked `is_available = 0` (red card color)
- "New arrival" flag resets 7 days after confirmation

**Source identification:**
1. `catalog.json` → `id` (most reliable)
2. Volume label of the disk
3. Fallback: file path

## Running as a System Service (Windows)

For automatic startup at system boot:

```bash
pip install pywin32
```

Create a scheduled task or use NSSM.

## Local Network Deployment

1. Make sure the firewall allows incoming connections on port 8000
2. Start the server with `host = "0.0.0.0"`
3. Other computers on the network can access via IP or computer name

## Code-Based Metadata Lookup (lookup)

The system allows finding book metadata by identifier (ISBN, DOI, ISSN) through external APIs.

### How It Works

1. The user enters a code in the ISBN field and presses the `...` button
2. **On the client** (`detectCodeType`) the code type is detected:
   - `isbn10` / `isbn13` — 10- or 13-digit ISBN
   - `doi` — digital object identifier
   - `issn` — international serial number
   - `bbk` / `udk` / `lcc` / `grnti` — classification codes (local search only)
3. **On the server** (`services/lookup.py`) the request is proxied to the appropriate API:
   - **ISBN** → [OpenLibrary](https://openlibrary.org) (`/api/books?bibkeys=ISBN:...`)
   - **DOI** → [CrossRef](https://crossref.org) (`/works/{doi}`)
   - **ISSN** → [ISSN Portal](https://portal.issn.org) (`/api/issn?value=...`)
4. The server returns structured data (title, author, publisher, year, pages, description)
5. **On the client** the edit form fields are filled automatically
6. When saving the book, the raw API response is saved to `{book}.lookup.json` next to the book file

### .lookup.json Format

```json
{
  "lookup_source": "openlibrary",
  "lookup_code": "isbn13",
  "source_url": "https://openlibrary.org/isbn/9780596007126",
  "cover_url": "https://covers.openlibrary.org/b/id/123456-L.jpg",
  "raw": { ... },
  "looked_up_at": "2026-05-25T15:30:00"
}
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/lookup` | Search code in external APIs |
| GET | `/api/lookup/by-classification?code=...` | Search code in local database (LIKE) |

**POST /api/lookup**

Request:
```json
{"code": "ISBN 978-5-12345-678-9"}
```

Response:
```json
{
  "detected_type": "isbn13",
  "title": "Book Title",
  "author": "Author",
  "publisher": "Publisher",
  "year": 2024,
  "pages": 300,
  "isbn": "9785123456789",
  "description": "Topic; Section; ...",
  "cover_url": "https://...",
  "source_url": "https://openlibrary.org/isbn/9785123456789",
  "source": "openlibrary",
  "raw": { ... }
}
```

### Client Side

- `searchIsbn()` — entry point (button `...`)
- `normalizeCode()` — clean code from prefixes and separators
- `detectCodeType()` — auto-detect type
- `promptCodeType()` — manual selection modal for unknown types
- `fillBookFromLookup()` — fill form + save `pendingLookupMeta`
- `saveBook()` — on save, sends `pendingLookupMeta` to `/save-metadata`

## License

MIT License
