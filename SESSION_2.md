# OpenCode Session Notes

## Сессия 1: 2026-04-15 - Начальная разработка

### Что сделано

| Коммит | Описание |
|--------|----------|
| `1034d02` | Начальная структура проекта, SQLite + FTS5, веб-интерфейс |
| `f5bbc9b` | Поддержка хранилищ (HDD, DVD, SSD, NAS, network) |
| `7f3e546` | Идентификация носителей (catalog.json, volume_label), upsert логика |

### Реализованные фичи (Сессия 1)

- SQLite + FTS5 база данных
- Импорт книг из файловой системы
- Полнотекстовый поиск по названию, автору, описанию
- Управление хранилищами (UI + API)
- Автоопределение подключенных дисков
- Идентификация носителей через `catalog.json` или метку тома
- Upsert при повторном сканировании (обновление всех полей)
- Веб-интерфейс (каталог + хранилища)
- LAN доступ

---

## Сессия 2: 2026-04-16 - Первый запуск и приветствие

### Что сделано

- Исправлен баг с поиском FTS5 (функции highlight/snippet)
- Добавлена страница "О программе" (`/about`)
- Добавлен мастер первичной настройки (`/setup`)
- Добавлена конфигурация `DEFAULT_SOURCE_PATH` в `config.py`
- Автосканирование `DEFAULT_SOURCE_PATH` при первом запуске
- Диалог выбора папки через Windows FolderBrowserDialog
- Сохранение выбранного пути в `config.py`
- Кнопка "О программе" в header
- Кнопка "Настройки" в секции хранилищ

### Новые файлы

| Файл | Описание |
|------|----------|
| `app/routers/welcome.py` | Роутер первичной настройки и about |
| `web/about.html` | Страница "О программе" |
| `web/setup.html` | Мастер первичной настройки |
| `start_server.cmd` | Скрипт запуска сервера |

### Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `config.py` | + DEFAULT_SOURCE_PATH, SHOW_WELCOME |
| `app/models.py` | + SetupStatus, FolderSelectRequest/Response, InitialScanResponse, SavePathRequest |
| `app/main.py` | + startup check, /about, /setup, welcome router |
| `app/database.py` | Исправлен FTS5 search query format |
| `web/index.html` | + кнопка "О программе", "Настройки", modal, checkSetup() |

### Структура проекта (актуальная)

```
C:\Library\
├── app/
│   ├── main.py           # FastAPI точка входа, startup events
│   ├── database.py       # SQLite + FTS5
│   ├── models.py         # Pydantic модели
│   └── routers/
│       ├── books.py      # API книг
│       ├── search.py     # API поиска
│       ├── sources.py    # API хранилищ
│       └── welcome.py    # API первичной настройки + /about
├── services/
│   ├── importer.py       # Импорт + upsert логика
│   └── drives.py         # Обнаружение дисков, чтение catalog.json
├── web/
│   ├── index.html        # SPA веб-интерфейс
│   ├── about.html        # Страница "О программе"
│   └── setup.html        # Мастер первичной настройки
├── config.py             # Конфигурация
├── start_server.cmd      # Скрипт запуска
└── library.db           # SQLite БД
```

---

## API эндпоинты (полный список)

| Endpoint | Метод | Описание |
|----------|-------|---------|
| `/` | GET | Главная страница (index.html) |
| `/about` | GET | Страница "О программе" |
| `/setup` | GET | Мастер первичной настройки |
| `/api/health` | GET | Проверка работоспособности |
| `/api/books` | GET | Список книг |
| `/api/books/{id}` | GET | Детали книги |
| `/api/search` | GET | Полнотекстовый поиск |
| `/api/categories` | GET | Список категорий |
| `/api/stats` | GET | Статистика библиотеки |
| `/api/sources` | GET/POST | Список/добавление хранилищ |
| `/api/sources/{id}` | GET/PUT/DELETE | CRUD хранилища |
| `/api/sources/{id}/scan` | POST | Сканирование хранилища |
| `/api/sources/discover` | GET | Автоопределение дисков |
| `/api/setup/status` | GET | Статус первичной настройки |
| `/api/setup/drives` | GET | Список доступных дисков |
| `/api/setup/select-folder` | POST | Диалог выбора папки |
| `/api/setup/save-path` | POST | Сохранение пути в config.py |
| `/api/setup/scan` | POST | Первичное сканирование |
| `/api/setup/skip` | POST | Пропуск настройки |

---

## Первый запуск - логика

```
┌─────────────────────────────────────────────────────────┐
│ 1. Сервер запускается (startup event)                   │
│ 2. check_initial_setup() проверяет:                     │
│    - sources = 0 AND DEFAULT_SOURCE_PATH задан?        │
│    → ДА: авто-импорт из DEFAULT_SOURCE_PATH            │
│    → НЕТ: ничего не делаем                             │
│ 3. Пользователь открывает /                            │
│ 4. checkSetup() в index.html → needs_setup?            │
│    → ДА: редирект на /setup                           │
│    → НЕТ: показ главной страницы                       │
└─────────────────────────────────────────────────────────┘
```

---

## Конфигурация (config.py)

```python
BOOKS_DIR = "C:/Book/"                    # Путь для CLI импорта
DATABASE_URL = "library.db"               # Путь к БД
SERVER_HOST = "0.0.0.0"                   # Хост для LAN доступа
SERVER_PORT = 8000                        # Порт

DEFAULT_SOURCE_PATH = ""                   # Путь для авто-импорта (изменить вручную!)
SHOW_WELCOME = "true"                     # Показывать приветствие

SUPPORTED_FORMATS = ["pdf", "djvu", "rar", "zip", "rtf"]
SUPPORTED_METADATA_EXT = ["txt", "html"]
COVER_EXTENSIONS = ["jpg", "jpeg", "png", "gif"]
```

---

## Запуск

### Быстрый запуск (рекомендуется)

```powershell
cd C:\Library
.\start_server.cmd
```

### Ручной запуск

```powershell
cd C:\Library
pip install -r requirements.txt
python reset_db.py   # первый запуск
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Git

```powershell
# Статус
git status

# Последние коммиты
git log --oneline -10

# Добавить все изменения
git add -A

# Коммит
git commit -m "Описание изменений"

# Отправить
git push

# Получить
git pull
```

---

## Следующие шаги (приоритет)

| # | Фича | Описание |
|---|------|----------|
| 1 | **Исправление "Открыть файл"** | Кнопка не работает - проблема с file:// URL |
| 2 | **CLI интерфейс** | Работа с каталогом через командную строку |
| 3 | **Тегирование книг** | UI для добавления тегов к книгам |
| 4 | **Экспорт каталога** | Экспорт в JSON/CSV |
| 5 | **Backup БД** | Автоматическое резервное копирование |
