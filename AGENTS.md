# Library Project - Домашний библиотекарь

## Quick Start

```powershell
cd C:\Library
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
- New fields: `cover_ext` (обложка: jpg/png/gif/webp/bmp/tiff), `is_available`, `is_new_arrival`, `last_seen`, `format`
- `extra_files` (TEXT) — JSON-массив путей multi-part архивов (.part2.rar, .7z.002)

## Storage Sources

Sources table supports: `local`, `hdd`, `ssd`, `dvd`, `nas`, `network`, `cloud`

**Удаление хранилища:** При удалении хранилища удаляются все связанные книги (каскадное удаление).

**Идентификация:**
1. `catalog.json` → `id` поле (предпочтительно для съемных носителей)
2. Volume label (метка тома Windows)
3. Path fallback

**Логика сканирования:**
- Существующие книги: подтверждение наличия (обновление `is_available`, `last_seen`) без перезаписи данных
- Новые книги: добавление с флагом `is_new_arrival = 1`
- Отсутствующие книги: пометка `is_available = 0` (красный цвет карточки)
- Флаг "Новое поступление" сбрасывается через 7 дней после подтверждения

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

## Категории

- **Структура**: иерархия через `parent_id`, full_path вычисляется через VIEW `category_paths`
- **Индивидуальность**: каждая категория привязана к `source_id`
- **Фильтр**: ищет по последней части пути (после `/`), примеры:
  - `Soft/Server 2003` → ищет `Server 2003`
  - `Учеба/Soft/Server 2003` → ищет `Server 2003`
  - `Книги/Языки/English` → ищет `English`

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

Runtime-настройки (audit_enabled) хранятся в `settings.json`, не в `config.py` — это предотвращает перезагрузку uvicorn при переключении.

## Features

- **Full-text search** с использованием SQLite FTS5
- **Каскадное удаление** хранилищ, книг и категорий
- **Инициализация библиотеки** - полная очистка БД
- **Управление хранилищами** - добавление, редактирование, удаление, перенос с прогресс-баром
- **Автосканирование при первом запуске** (по желанию)
- **Ручное сканирование** - только по кнопке, SSE-прогресс
- **Метаданные** - поддержка KOI8-R, CP1251, .json приоритет над .txt
- **Категория** - определяется по имени папки, привязана к хранилищу (source_id)
- **Подтверждение наличия** - при сканировании книги подтверждаются без перезаписи данных
- **Новые поступления** - флаг is_new_arrival (сбрасывается через 7 дней)
- **Фильтрация по наличию** - доступно/отсутствует/новые поступления
- **Цветовая индикация** - зелёный (в наличии), красный (отсутствует)
- **Экспорт метаданных** - при редактировании книги метаданные экспортируются в .json
- **Перемещение файлов** - при изменении пути перемещаются все файлы книги (.pdf + .json + .txt + обложка)
- **Поддержка многотомных архивов** - .part1.rar, .part2.rar и т.д. (extra_files)
- **Расширенные форматы обложек** - bmp, webp, tiff
- **Обложки книг** - автоматическое обнаружение при сканировании, отображение по клику
- **Прокси обложек** - `/api/cover?path=...` для безопасной загрузки изображений
- **Три вкладки интерфейса**: Каталог, Хранилища, Инструменты
- **Четыре режима отображения**: Плитка, Обложки (30 книг на странице), Список, Таблица (с сортировкой по столбцам)
- **Название хранилища на карточке** — во всех режимах отображения
- **Поиск и удаление дубликатов** — автоматическое обнаружение по (source_id + file_size + имя_файла) с выбором лучшей записи
- **Расширенное редактирование книги**: publisher, pages, format, language
- **Аудит-логи** - отслеживание действий пользователя (services/audit.py, настройка хранится в settings.json)
- **Прогресс-трекер** - SSE-события для сканирования без дублирования (services/progress.py)
- **Кастомные модальные окна** - замена alert()/confirm() на единый стиль
- **Перевод сообщений** - API возвращает сообщения на русском языке
- **Исправление статистики сканирования** - корректный подсчет imported/confirmed/covers_found
