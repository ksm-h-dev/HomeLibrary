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
| cover_ext | TEXT | Расширение обложки (jpg, png, webp, bmp, tiff) |
| category_id | INTEGER | Внешний ключ на categories |
| source_id | INTEGER | Внешний ключ на sources |
| language | TEXT | Язык (ru, en) |
| source_url | TEXT | URL источника |
| is_available | INTEGER | Флаг наличия (1-в наличии, 0-отсутствует) |
| is_new_arrival | INTEGER | Флаг нового поступления (сбрасывается через 7 дней) |
| last_seen | TIMESTAMP | Время последнего подтверждения наличия |
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

- `app/main.py` - точка входа, конфигурация приложения, startup events
- `app/database.py` - SQLite + FTS5, логика доступности, новые поступления
- `app/models.py` - Pydantic модели для валидации
- `app/routers/books.py` - эндпоинты для работы с книгами (фильтр availability)
- `app/routers/search.py` - эндпоинты для поиска (фильтр availability)
- `app/routers/sources.py` - эндпоинты для хранилищ (CRUD, сканирование)
- `app/routers/welcome.py` - настройка, about page API

### 3. Импортер (services/importer.py)

**Функции:**

- `scan_directory(path, source_id)` - рекурсивное сканирование каталога
- `parse_metadata_file(filepath)` - парсинг .json или .txt файла
- `parse_metadata_json(filepath)` - парсинг .json метаданных
- `parse_metadata_txt(filepath)` - парсинг .txt метаданных
- `extract_book_info(filename)` - извлечение информации из имени файла
- `find_cover_file(book_path)` - поиск обложки (jpg, png, gif, webp, bmp, tiff)
- `import_from_source(source_id, directory)` - импорт с логикой наличия
- `export_book_to_json(book_id, directory)` - экспорт метаданных в .json при редактировании книги
- `move_book_files(book_id, new_directory)` - перемещение всех файлов книги

**Приоритет метаданных:** .json → .txt

**Алгоритм сканирования:**

1. Сброс устаревших флагов `is_new_arrival` (старше 7 дней)
2. Сканировать каталог рекурсивно
3. Для каждого файла:
   - **Существует в БД** → подтверждение наличия (обновление `is_available=1`, `last_seen`, без перезаписи данных)
   - **Новый файл** → добавление с флагом `is_new_arrival=1`
4. Книги, не найденные при сканировании → пометка `is_available=0`

### 4. Поиск (services/search.py)

**Типы поиска:**

- Полнотекстовый (FTS5) - по названию, автору, описанию
- Фильтрация - по формату, году, категории
- Комбинированный поиск

### 5. Веб-интерфейс (web/index.html)

- SPA на чистом JavaScript
- Fetch API для обращения к бэкенду
- Отображение результатов поиска
- Фильтры (формат, категория, год, хранилище, **наличие**)
- Сортировка (дата, название, автор, год, страницы)
- Цветовая индикация карточек: **зелёный** (в наличии), **красный** (отсутствует)
- Пагинация
- Вкладки: Каталог / Хранилища
- Модальные окна: настройки, редактирование книги, добавление хранилища

## Поток данных

### Импорт книги

```
C:\Book\book.pdf     ─┐
C:\Book\book.json    │──► Importer ──► Database
C:\Book\cover.jpg   ─┘
```

**Приоритет метаданных:** .json → .txt

### Поиск книги

```
User Input ─► API Request ─► Search Service ─► FTS5 Query ─► Results ─► JSON ─► UI
```

## API спецификация

### GET /api/books

**Query Parameters:**
- `limit` (int, optional): Количество записей (default: 20)
- `offset` (int, optional): Смещение (default: 0)
- `category` (string, optional): Фильтр по категории. Извлекается последняя часть пути (после `/`) и ищется по LIKE.
  Примеры: `Soft/Server 2003` → ищет `Server 2003`; `Учеба/Книги/English` → ищет `English`
- `format` (string, optional): Формат файла
- `year` (int, optional): Год издания
- `source_id` (int, optional): ID хранилища
- `sort_by` (string, optional): Сортировка (date, title, author, year, pages)
- `availability` (string, optional): Фильтр по наличию: `available`, `missing`, `new`

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
  "title": "Название книги",
  "author": "Автор",
  "publisher": "Издательство",
  "isbn": "5-94057-183-2",
  "year": 2020,
  "pages": 300,
  "format": "pdf",
  "language": "ru",
  "file_size": 5242880,
  "description": "Описание книги...",
  "file_path": "C:/Book/book.pdf",
  "cover_ext": "jpg",
  "category": "Программирование",
  "is_available": true,
  "is_new_arrival": false
}
```

### GET /api/cover?path=...

**Query Parameters:**
- `path` (string, required): URL-encoded путь к файлу книги

**Response:** Returns the cover image file (jpg, png, gif, bmp, webp, tiff)

**Notes:**
- Использует гибкий поиск обложки в папке с книгой
- Ищет изображения по частичному совпадению имени файла

### GET /api/search

**Query Parameters:**
- `q` (string, required): Поисковый запрос
- `format` (string, optional): Формат файла
- `category` (string, optional): Категория
- `year` (int, optional): Год издания
- `source_id` (int, optional): ID хранилища
- `sort_by` (string, optional): Сортировка (date, title, author, pages)
- `limit` (int, optional): Лимит результатов
- `offset` (int, optional): Смещение
- `availability` (string, optional): Фильтр по наличию: `available`, `missing`, `new`

**Response:**
```json
{
  "total": 10,
  "query": "python",
  "books": [
    {
      "id": 1,
      "title_hl": "Python <b>Programming</b>",
      "desc_snippet": "Описание книги...",
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
  "message": "Scan completed for Внешний HDD: 5 обложек найдено",
  "scanned": 50,
  "imported": 12,
  "confirmed": 35,
  "covers_found": 5,
  "missing": 3,
  "missing_books": [...]
}
```

#### GET /api/sources/{id}/books

**Response:** Список книг в хранилище с полями `is_available`, `is_new_arrival`

#### GET /api/sources/discover

Автоматическое обнаружение подключенных дисков (Windows).

**Response:**
```json
[
  {"drive_letter": "C", "label": "System", "type": "fixed", "total_size": 500000000000},
  {"drive_letter": "D", "label": "Data", "type": "removable"}
]
```

#### Setup API (первичная настройка)

- `GET /api/setup/status` - статус настройки
- `GET /api/setup/drives` - список доступных дисков
- `POST /api/setup/select-folder` - диалог выбора папки
- `POST /api/setup/save-path` - сохранение пути в config.py
- `POST /api/setup/scan` - первичное сканирование
- `POST /api/setup/skip` - пропуск настройки
- `POST /api/setup/initialize` - сброс библиотеки

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

## Интерфейс клиента

Веб-интерфейс состоит из трёх вкладок:

### Каталог
- Статистика (книг, категорий, хранилищ)
- Поиск и фильтры (формат, категория, год, хранилище, сортировка, наличие)
- Сетка карточек книг с обложками
- Пагинация
- Редактирование книги (название, автор, ISBN, год, издательство, страниц, формат, язык, описание)

### Хранилища
- Добавление хранилища (название, тип, путь)
- Список подключённых дисков
- Список хранилищ с книгами и статистикой
- Сканирование хранилищ

### Инструменты
- Настройки (путь к библиотеке)
- Инициализация библиотеки (сброс базы данных)

**Модальные окна:**
- Редактирование книги
- Просмотр обложки
- Настройки
- Инициализация библиотеки
