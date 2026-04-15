# Архитектура системы "Домашний библиотекарь"

## Обзор

Система представляет собой веб-приложение для управления электронной библиотекой с клиент-серверной архитектурой.

```
┌─────────────────────────────────────────────────────────────┐
│                        Клиент                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Браузер (HTML/CSS/JS)                   │   │
│  │   - Поиск книг                                       │   │
│  │   - Просмотр каталога                                 │   │
│  │   - Фильтрация                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Сервер                                 │
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
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ SQL
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      База данных                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   SQLite + FTS5                     │   │
│  │   - books (основные данные)                         │   │
│  │   - categories (категории)                          │   │
│  │   - tags (теги)                                     │   │
│  │   - books_fts (полнотекстовый индекс)               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Файловая система                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              C:\Book\                               │   │
│  │   - *.pdf, *.djvu, *.rar, *.zip                    │   │
│  │   - *.txt (метаданные)                             │   │
│  │   - *.jpg (обложки)                                │   │
│  │   - Подкаталоги (категории)                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. База данных (SQLite + FTS5)

**Таблица `books`**

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Первичный ключ, автоинкремент |
| title | TEXT | Название книги |
| author | TEXT | Автор |
| publisher | TEXT | Издательство |
| isbn | TEXT | ISBN |
| year | INTEGER | Год издания |
| pages | INTEGER | Количество страниц |
| format | TEXT | Формат файла (pdf, djvu, rar, zip) |
| file_size | INTEGER | Размер файла в байтах |
| description | TEXT | Описание книги |
| file_path | TEXT | Полный путь к файлу книги |
| relative_path | TEXT | Относительный путь от корня хранилища |
| cover_path | TEXT | Путь к обложке |
| category_id | INTEGER | Внешний ключ на categories |
| source_id | INTEGER | Внешний ключ на sources |
| language | TEXT | Язык (ru, en) |
| source_url | TEXT | URL источника |
| created_at | TIMESTAMP | Дата добавления в БД |

**Уникальный индекс:** `source_id + relative_path` (не допускает дубликатов)

**Таблица `sources`** (хранилища)

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Первичный ключ |
| name | TEXT | Название хранилища |
| type | TEXT | Тип: local, hdd, ssd, dvd, nas, network, cloud |
| path | TEXT | Текущий путь к хранилищу |
| volume_label | TEXT | Метка тома (volume label) |
| catalog_id | TEXT | Идентификатор из catalog.json |
| is_active | INTEGER | Активно (1) / отключено (0) |
| description | TEXT | Описание |
| last_scanned | TIMESTAMP | Последнее сканирование |
| created_at | TIMESTAMP | Дата добавления |

**Таблица `categories`**

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Первичный ключ |
| name | TEXT | Название категории |
| parent_id | INTEGER | Родительская категория (для иерархии) |

**Таблица `tags`**

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Первичный ключ |
| name | TEXT | Название тега |

**Таблица `book_tags`** (связь многие-ко-многим)

| Поле | Тип | Описание |
|------|-----|----------|
| book_id | INTEGER | Внешний ключ на books |
| tag_id | INTEGER | Внешний ключ на tags |

**Виртуальная таблица `books_fts`** (FTS5)

```
Создается автоматически для полнотекстового поиска.
Индексирует: title, author, description
```

### 2. API (FastAPI)

**Основные модули:**

- `app/main.py` - точка входа, конфигурация приложения
- `app/routers/books.py` - эндпоинты для работы с книгами
- `app/routers/search.py` - эндпоинты для поиска
- `app/models.py` - Pydantic модели для валидации
- `app/database.py` - подключение к SQLite

### 3. Импортер (services/importer.py)

**Функции:**

- `scan_directory(path)` - рекурсивное сканирование каталога
- `parse_metadata_file(filepath)` - парсинг .txt файла
- `extract_book_info(filename)` - извлечение информации из имени файла
- `import_to_database(books)` - запись в БД

**Алгоритм импорта:**

1. Сканировать `C:\Book\` рекурсивно
2. Для каждого файла с расширением `.rar`, `.pdf`, `.djvu`, `.zip`:
   - Найти соответствующий `.txt` файл
   - Распознать категорию по родительскому каталогу
   - Извлечь обложку (`.jpg` с тем же именем)
   - Сохранить метаданные в БД

### 4. Поиск (services/search.py)

**Типы поиска:**

- Полнотекстовый (FTS5) - по названию, автору, описанию
- Фильтрация - по формату, году, категории
- Комбинированный поиск

### 5. Веб-интерфейс (web/index.html)

- SPA на чистом JavaScript
- Fetch API для обращения к бэкенду
- Отображение результатов поиска
- Фильтры и пагинация

## Поток данных

### Импорт книги

```
C:\Book\book.pdf     ─┐
C:\Book\book.txt      │──► Importer ──► Database
C:\Book\book.jpg     ─┘
```

### Поиск книги

```
User Input ─► API Request ─► Search Service ─► FTS5 Query ─► Results ─► JSON ─► UI
```

## API спецификация

### GET /api/books

**Query Parameters:**
- `limit` (int, optional): Количество записей (default: 20)
- `offset` (int, optional): Смещение (default: 0)
- `category` (string, optional): Фильтр по категории

**Response:**
```json
{
  "total": 100,
  "books": [
    {
      "id": 1,
      "title": "Название книги",
      "author": "Автор",
      "format": "pdf",
      "year": 2020
    }
  ]
}
```

### GET /api/books/{id}

**Response:**
```json
{
  "id": 1,
  "title": "Название книги",
  "author": "Автор",
  "publisher": "Издательство",
  "isbn": "5-94057-183-2",
  "year": 2020,
  "pages": 300,
  "format": "pdf",
  "file_size": 5242880,
  "description": "Описание книги...",
  "file_path": "C:/Book/book.pdf",
  "cover_url": "/api/covers/1",
  "category": "Программирование",
  "tags": ["python", "programming"]
}
```

### GET /api/search

**Query Parameters:**
- `q` (string, required): Поисковый запрос
- `format` (string, optional): Формат файла
- `category` (string, optional): Категория
- `year` (int, optional): Год издания
- `limit` (int, optional): Лимит результатов
- `offset` (int, optional): Смещение

**Response:**
```json
{
  "total": 10,
  "query": "python",
  "books": [...]
}
```

### GET /api/categories

**Response:**
```json
{
  "categories": [
    {"id": 1, "name": "Программирование"},
    {"id": 2, "name": "Психология", "parent_id": null}
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
    "name": "DVD Коллекция",
    "type": "dvd",
    "path": "D:\\",
    "is_active": true,
    "books_count": 45,
    "last_scanned": "2024-01-15T10:30:00"
  }
]
```

#### POST /api/sources

**Request:**
```json
{
  "name": "Внешний HDD",
  "type": "hdd",
  "path": "E:\\Books",
  "is_active": true
}
```

#### POST /api/sources/{id}/scan

Запускает сканирование хранилища и импорт книг.

**Response:**
```json
{
  "message": "Scan completed for Внешний HDD",
  "scanned": 50,
  "imported": 12,
  "skipped": 38
}
```

#### GET /api/sources/discover

Автоматическое обнаружение подключенных дисков (Windows).

**Response:**
```json
[
  {"drive_letter": "C", "label": "System", "type": "fixed", "total_size": 500000000000},
  {"drive_letter": "D", "label": "Data", "type": "removable"}
]
```

## Развертывание

### Локальный запуск

```bash
cd C:\Library
uvicorn app.main:app --reload
```

### LAN запуск

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Файрвол (Windows)

```powershell
netsh advfirewall firewall add rule name="Library Server" ^
    dir=in action=allow protocol=tcp localport=8000
```

## Безопасность

- API не требует аутентификации (локальная сеть)
- CORS настроен для любых источников
- Пути к файлам передаются клиенту для открытия в проводнике
