[**English**](ARCHITECTURE.en.md) | [**Русский**](ARCHITECTURE.md)

# System Architecture "Home Librarian"

## Overview

The system is a web application for managing an electronic library with a client-server architecture.

```
┌─────────────────────────────────────────────────────────────┐
│                        Client                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Browser (HTML/CSS/JS)                   │   │
│  │   - Book search                                      │   │
│  │   - Catalog browsing                                 │   │
│  │   - Filtering                                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Server                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FastAPI Application                    │   │
│  │   - API Routes (/api/books, /api/search)            │   │
│  │   - Request/Response handling                       │   │
│  │   - CORS middleware                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│  ┌─────────────────────────┼───────────────────────────┐  │
│  │                         ▼                           │  │
│  │   ┌──────────────────────────────┐                   │  │
│  │   │        Search Service        │                   │  │
│  │   │   - Full-text search (FTS5)  │                   │  │
│  │   │   - Filtering                │                   │  │
│  │   └──────────────────────────────┘                   │  │
│  │   ┌──────────────────────────────┐                   │  │
│  │   │        Importer Service      │                   │  │
│  │   │   - Parse .txt metadata      │                   │  │
│  │   │   - File system scan         │                   │  │
│  │   └──────────────────────────────┘                   │  │
│  │   ┌──────────────────────────────┐                   │  │
│  │   │        Lookup Service        │                   │  │
│  │   │   - normalize_code()         │                   │  │
│  │   │   - detect_code_type()      │                   │  │
│  │   │   - lookup_isbn/doi/issn()  │                   │  │
│  │   │   - OpenLibrary / CrossRef   │                   │  │
│  │   └──────────────────────────────┘                   │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ SQL
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   SQLite + FTS5                     │   │
│  │   - books (main data)                              │   │
│  │   - categories                                     │   │
│  │   - tags                                           │   │
│  │   - books_fts (full-text index)                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────┐
│                   File System                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              C:\Book\                               │   │
│  │   - *.pdf, *.djvu, *.rar, *.zip                    │   │
│  │   - *.txt (metadata)                               │   │
│  │   - *.jpg (covers)                                 │   │
│  │   - Subdirectories (categories)                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Database (SQLite + FTS5)

**Table `books`**

| Field | Type | Description |
|------|-----|----------|
| id | INTEGER | Primary key, auto-increment |
| title | TEXT | Book title |
| author | TEXT | Author |
| publisher | TEXT | Publisher |
| isbn | TEXT | ISBN |
| year | INTEGER | Publication year |
| pages | INTEGER | Number of pages |
| format | TEXT | File format (pdf, djvu, rar, zip, rtf, 7z) |
| file_size | INTEGER | File size in bytes |
| description | TEXT | Book description |
| file_path | TEXT | Full path to the book file |
| relative_path | TEXT | Relative path from the source root |
| cover_path | TEXT | Path to the cover |
| cover_ext | TEXT | Cover extension (jpg, png, webp, bmp, tiff) |
| extra_files | TEXT | JSON array of multi-part archive paths (.part2.rar, .7z.002) |
| category_id | INTEGER | Foreign key to categories |
| source_id | INTEGER | Foreign key to sources |
| language | TEXT | Language (ru, en) |
| source_url | TEXT | Source URL |
| is_available | INTEGER | Availability flag (1-available, 0-missing) |
| is_new_arrival | INTEGER | New arrival flag (resets after 7 days) |
| last_seen | TIMESTAMP | Last availability confirmation time |
| created_at | TIMESTAMP | Date added to DB |

**Unique index:** `source_id + relative_path` (prevents duplicates)

**Table `sources`** (storage sources)

| Field | Type | Description |
|------|-----|----------|
| id | INTEGER | Primary key |
| name | TEXT | Source name |
| type | TEXT | Type: local, hdd, ssd, dvd, nas, network, cloud |
| path | TEXT | Current source path |
| volume_label | TEXT | Volume label |
| catalog_id | TEXT | Identifier from catalog.json |
| is_active | INTEGER | Active (1) / disabled (0) |
| description | TEXT | Description |
| last_scanned | TIMESTAMP | Last scan time |
| created_at | TIMESTAMP | Date added |

**Table `categories`**

| Field | Type | Description |
|------|-----|----------|
| id | INTEGER | Primary key |
| name | TEXT | Category name |
| source_id | INTEGER | Foreign key to sources (tied to storage) |
| parent_id | INTEGER | Parent category (for hierarchy) |

**Table `tags`**

| Field | Type | Description |
|------|-----|----------|
| id | INTEGER | Primary key |
| name | TEXT | Tag name |

**Table `book_tags`** (many-to-many relationship)

| Field | Type | Description |
|------|-----|----------|
| book_id | INTEGER | Foreign key to books |
| tag_id | INTEGER | Foreign key to tags |

**Virtual table `books_fts`** (FTS5)

```
Created automatically for full-text search.
Indexes: title, author, description
```

### 2. API (FastAPI)

**Main modules:**

- `app/main.py` - entry point, application configuration, startup events
- `app/database.py` - SQLite + FTS5, availability logic, new arrivals
- `app/models.py` - Pydantic models for validation
- `app/routers/books.py` - book CRUD endpoints (availability filter, save-metadata)
- `app/routers/lookup.py` - metadata lookup by code endpoints (POST /api/lookup, GET /by-classification)
- `app/routers/search.py` - search endpoints (availability filter)
- `app/routers/sources.py` - source management endpoints (CRUD, scan, transfer with progress bar)
- `app/routers/welcome.py` - setup, about page API, library initialization

### 3. Importer (services/importer.py)

**Functions:**

- `scan_directory(path, source_id)` - recursive directory scan (SUPPORTED_FORMATS filter, multi-part .rar/.7z)
- `find_extra_files(book_path)` - find multi-part archives (.partN.rar, .7z.NNN)
- `parse_metadata_file(filepath)` - parse .json or .txt file
- `parse_metadata_json(filepath)` - parse .json metadata
- `parse_metadata_txt(filepath)` - parse .txt metadata
- `extract_book_info(filename)` - extract information from filename
- `find_cover_file(book_path)` - find cover (jpg, png, gif, webp, bmp, tiff)
- `import_from_source(source_id, directory)` - import with availability logic, save extra_files

**Metadata priority:** .json → .txt

**Scan algorithm:**

1. Reset outdated `is_new_arrival` flags (older than 7 days)
2. Scan directory recursively
3. For each file:
   - **Exists in DB** → confirm availability (update `is_available=1`, `last_seen`, without overwriting data)
   - **New file** → add with `is_new_arrival=1` flag
4. Books not found during scan → mark `is_available=0`

### 4. Search (services/search.py)

**Search types:**

- Full-text (FTS5) - by title, author, description
- Filtering - by format, year, category
- Combined search

### 5. Lookup Service (services/lookup.py)

Service for searching metadata by book identifiers through external APIs.

**Architecture:**
1. `normalize_code()` — strip ISBN/DOI/ISSN prefixes and separators
2. `detect_code_type()` — determine type (isbn13, isbn10, doi, issn, unknown)
3. `lookup_code()` — main dispatcher, calls the appropriate API by type
4. `lookup_isbn()` → OpenLibrary API
5. `lookup_doi()` → CrossRef API
6. `lookup_issn()` → ISSN Portal API

**Metadata file format (.lookup.json):**
```
{source_path}/{category}/{book_filename}.lookup.json
```

Contains: lookup_source, lookup_code, source_url, cover_url, raw (raw API response), looked_up_at.

**Endpoint:** `POST /api/lookup` — server proxy (prevents CORS issues)
**Endpoint:** `POST /api/books/{id}/save-metadata` — write .lookup.json

### 6. Web Interface (web/index.html)

- SPA in pure JavaScript
- Fetch API for backend communication
- Search results display
- Filters (format, category, year, source, **availability**)
- Sorting (date, title, author, year, pages)
- Card color coding: **green** (available), **red** (missing)
- Pagination
- Three tabs: Catalog / Sources / Tools
- Modal windows: settings, book editing, add source, DB initialization, log viewer
- Custom modal dialogs (replacing alert/confirm)

## Data Flow

### Book Import

```
C:\Book\book.pdf     ─┐
C:\Book\book.json    │──► Importer ──► Database
C:\Book\cover.jpg   ─┘
```

**Metadata priority:** .json → .txt

### Book Search

```
User Input ─► API Request ─► Search Service ─► FTS5 Query ─► Results ─► JSON ─► UI
```

## API Specification

### GET /api/books

**Query Parameters:**
- `limit` (int, optional): Number of records (default: 20)
- `offset` (int, optional): Offset (default: 0)
- `category` (string, optional): Filter by category. Extracts the last part of the path (after `/`) and searches by LIKE.
  Examples: `Soft/Server 2003` → searches `Server 2003`; `Учеба/Книги/English` → searches `English`
- `format` (string, optional): File format
- `year` (int, optional): Publication year
- `source_id` (int, optional): Source ID
- `sort_by` (string, optional): Sorting (date, title, author, year, pages)
- `availability` (string, optional): Availability filter: `available`, `missing`, `new`

**Response:**
```json
{
  "total": 100,
  "books": [
    {
      "id": 1,
      "title": "Book Title",
      "author": "Author",
      "format": "pdf",
      "year": 2020,
      "is_available": true,
      "is_new_arrival": false,
      "last_seen": "2026-04-20T10:30:00"
    }
  ]
}
```

### GET /api/books/{id}

**Response:**
```json
{
  "id": 1,
  "title": "Book Title",
  "author": "Author",
  "publisher": "Publisher",
  "isbn": "5-94057-183-2",
  "year": 2020,
  "pages": 300,
  "format": "pdf",
  "language": "ru",
  "file_size": 5242880,
  "description": "Book description...",
  "file_path": "C:/Book/book.pdf",
  "cover_ext": "jpg",
  "category": "Programming",
  "is_available": true,
  "is_new_arrival": false
}
```

### GET /api/cover?path=...

**Query Parameters:**
- `path` (string, required): URL-encoded path to the book file

**Response:** Returns the cover image file (jpg, png, gif, bmp, webp, tiff)

**Notes:**
- Uses flexible cover search in the book's folder
- Searches for images by partial filename match

### GET /api/search

**Query Parameters:**
- `q` (string, required): Search query
- `format` (string, optional): File format
- `category` (string, optional): Category
- `year` (int, optional): Publication year
- `source_id` (int, optional): Source ID
- `sort_by` (string, optional): Sorting (date, title, author, pages)
- `limit` (int, optional): Result limit
- `offset` (int, optional): Offset
- `availability` (string, optional): Availability filter: `available`, `missing`, `new`

**Response:**
```json
{
  "total": 10,
  "query": "python",
  "books": [
    {
      "id": 1,
      "title_hl": "Python <b>Programming</b>",
      "desc_snippet": "Book description...",
      "is_available": true,
      "is_new_arrival": false
    }
  ]
}
```

### GET /api/categories

**Response:**
```json
{
  "categories": [
    {"id": 1, "name": "Programming"},
    {"id": 2, "name": "Psychology", "parent_id": null}
  ]
}
```

### GET /api/stats

**Response:**
```json
{
  "total_books": 100,
  "total_categories": 10,
  "total_sources": 3,
  "formats": {"pdf": 50, "djvu": 30, "rar": 20},
  "years": {"2020": 15, "2019": 12}
}
```

### Sources API

#### GET /api/sources

**Response:**
```json
[
  {
    "id": 1,
    "name": "DVD Collection",
    "type": "dvd",
    "path": "D:\\",
    "volume_label": "DVD_001",
    "catalog_id": "DVD-TEST-001",
    "is_active": true,
    "availability_status": "available",
    "books_count": 45,
    "last_scanned": "2024-01-15T10:30:00"
  }
]
```

#### POST /api/sources

**Request:**
```json
{
  "name": "External HDD",
  "type": "hdd",
  "path": "E:\\Books",
  "is_active": true
}
```

#### POST /api/sources/{id}/scan

Starts storage scan and book import.

**Response:**
```json
{
  "message": "Scan completed for External HDD: 5 covers found",
  "scanned": 50,
  "imported": 12,
  "confirmed": 35,
  "covers_found": 5,
  "missing": 3,
  "missing_books": [...]
}
```

#### GET /api/sources/{id}/books

**Response:** List of books in the source with `is_available`, `is_new_arrival` fields

#### GET /api/sources/discover

Automatic detection of connected drives (Windows).

**Response:**
```json
[
  {"drive_letter": "C", "label": "System", "type": "fixed", "total_size": 500000000000},
  {"drive_letter": "D", "label": "Data", "type": "removable"}
]
```

#### Setup API (initial setup)

- `GET /api/setup/status` - setup status
- `GET /api/setup/drives` - list of available drives
- `POST /api/setup/select-folder` - folder selection dialog
- `POST /api/setup/save-path` - save path to config.py
- `POST /api/setup/scan` - initial scan
- `POST /api/setup/skip` - skip setup
- `POST /api/setup/initialize` - reset library (deletes books + sources + categories, returns categories_deleted)

## Deployment

### Local Launch

```bash
cd C:\Library
uvicorn app.main:app --reload
```

### LAN Launch

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Firewall (Windows)

```powershell
netsh advfirewall firewall add rule name="Library Server" ^
    dir=in action=allow protocol=tcp localport=8000
```

## Security

- API does not require authentication (local network)
- CORS configured for any origin
- File paths are sent to the client for opening in explorer

## Client Interface

The web interface consists of three tabs:

### Catalog
- Statistics (books, categories, sources)
- Search and filters (format, category, year, source, sorting, availability)
- Book card grid with covers
- Pagination
- Book editing (title, author, ISBN, year, publisher, pages, format, language, description)

### Sources
- Add source (name, type, path)
- Connected drives list
- Source list with books and statistics
- Source scanning

### Tools
- Settings (library path)
- Library initialization (database reset: books + sources + categories)

**Modal windows:**
- Book editing
- Cover preview
- Settings
- Library initialization
