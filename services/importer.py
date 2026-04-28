import os
import re
import aiosqlite
from pathlib import Path
from config import BOOKS_DIR, SUPPORTED_FORMATS, COVER_EXTENSIONS


def parse_size_string(size_str: str) -> int:
    match = re.search(r"([\d.,]+)\s*(MB|KB|GB|Bytes)?", size_str, re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2) or "Bytes"
    multipliers = {"GB": 1024**3, "MB": 1024**2, "KB": 1024, "Bytes": 1}
    return int(value * multipliers.get(unit.upper(), 1))


def extract_year(text: str) -> int | None:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    return int(years[0]) if years else None


def extract_pages(text: str) -> int | None:
    pages = re.findall(r"(\d+)\s*(?:стр\.|страниц|pages?|с\.)", text, re.IGNORECASE)
    return int(pages[0]) if pages else None


def extract_format(filename: str, default_text: str = "") -> str:
    for fmt in SUPPORTED_FORMATS:
        if f".{fmt}" in filename.lower():
            return fmt
    formats = re.findall(r"формат[:\s]*([a-zа-я]+)", default_text.lower())
    return formats[0] if formats else ""


async def parse_metadata_file(filepath: str) -> dict:
    metadata = {
        "title": "",
        "author": "",
        "publisher": "",
        "isbn": "",
        "year": None,
        "pages": None,
        "format": "",
        "file_size": 0,
        "description": "",
        "source_url": "",
    }

    try:
        for encoding in ["utf-8", "cp1251", "koi8-r", "cp866"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        else:
            return metadata

        lines = content.split("\n")
        description_parts = []
        in_description = False

        for line in lines:
            line = line.strip()
            if not line or line.startswith("���") or len(line) < 3:
                continue

            lower_line = line.lower()

            if lower_line.startswith("файл:"):
                continue
            elif lower_line.startswith("url:"):
                metadata["source_url"] = line[4:].strip()
            elif lower_line.startswith("размер:"):
                metadata["file_size"] = parse_size_string(line)
            elif lower_line.startswith("дата:"):
                metadata["year"] = extract_year(line)
            elif "автор" in lower_line or lower_line.startswith("автор:"):
                match = re.search(r"(?:автор[:\s]*)?(.+)", line, re.IGNORECASE)
                if match:
                    metadata["author"] = match.group(1).strip()
            elif "название" in lower_line or lower_line.startswith("название:"):
                match = re.search(r"(?:название[:\s]*)?(.+)", line, re.IGNORECASE)
                if match:
                    metadata["title"] = match.group(1).strip()
            elif "издательство" in lower_line:
                match = re.search(r"издательство[:\s]*(.+)", line, re.IGNORECASE)
                if match:
                    metadata["publisher"] = match.group(1).strip()
            elif "isbn" in lower_line:
                match = re.search(r"isbn[:\s-]*([\d-]+)", line, re.IGNORECASE)
                if match:
                    metadata["isbn"] = match.group(1).strip()
            elif "год" in lower_line:
                metadata["year"] = extract_year(line)
            elif "страниц" in lower_line or "стр" in lower_line:
                metadata["pages"] = extract_pages(line)
            elif "формат" in lower_line:
                match = re.search(r"формат[:\s]*([a-zа-я]+)", line, re.IGNORECASE)
                if match:
                    metadata["format"] = match.group(1).lower()
            elif lower_line.startswith("описание:") or in_description:
                if lower_line.startswith("описание:"):
                    in_description = True
                    line = re.sub(r"^описание:\s*", "", line, flags=re.IGNORECASE)
                if line and not line.startswith("http"):
                    description_parts.append(line)

        if description_parts:
            metadata["description"] = " ".join(description_parts)

        if not metadata["title"]:
            book_filename = Path(filepath).stem.replace(".rar", "").replace("_", " ")
            metadata["title"] = book_filename

        if not metadata["format"]:
            metadata["format"] = extract_format(filepath)

    except Exception as e:
        print(f"Error parsing {filepath}: {e}")

    return metadata


def find_metadata_file(book_path: str) -> tuple[str | None, str]:
    base = str(Path(book_path).with_suffix(""))
    # Handle .part1.rar -> base should be the stem before .part1
    if ".part" in base.lower():
        match = re.match(r"(.+)\.part\d+", base, re.IGNORECASE)
        if match:
            base = match.group(1)
    for ext in [".json", ".txt", ".html", ".dusd"]:
        meta_file = base + ext
        if os.path.exists(meta_file):
            return meta_file, ext
    return None, ""


def find_cover_file(book_path: str) -> tuple[str | None, str]:
    book_dir = Path(book_path).parent
    if not book_dir.exists():
        return None, ""
    # Handle .part1.rar -> base should be the stem before .part1
    base = Path(book_path).stem
    if ".part" in base.lower():
        match = re.match(r"(.+)\.part\d+", base, re.IGNORECASE)
        if match:
            base = match.group(1)


async def parse_json_metadata_file(filepath: str) -> dict:
    import json
    metadata = {
        "title": "",
        "author": "",
        "publisher": "",
        "isbn": "",
        "year": None,
        "pages": None,
        "format": "",
        "file_size": 0,
        "description": "",
        "source_url": "",
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        metadata["title"] = data.get("title", "")
        metadata["author"] = data.get("author", "")
        metadata["publisher"] = data.get("publisher", "")
        metadata["isbn"] = data.get("isbn", "")
        metadata["year"] = data.get("year")
        metadata["pages"] = data.get("pages")
        metadata["format"] = data.get("format", "")
        metadata["description"] = data.get("description", "")
        metadata["source_url"] = data.get("source_url", "")
    except Exception as e:
        print(f"Error parsing JSON metadata {filepath}: {e}")
    return metadata


def find_cover_file(book_path: str) -> tuple[str | None, str]:
    book_dir = Path(book_path).parent
    if not book_dir.exists():
        return None, ""
    
    base_stem = Path(book_path).stem
    base_stem = re.sub(r"\.part\d+$", "", base_stem, flags=re.IGNORECASE)
    
    for ext in COVER_EXTENSIONS:
        cover_name = f"{base_stem}.{ext}"
        cover_path = book_dir / cover_name
        if cover_path.exists():
            return str(cover_path), ext
    
    return None, ""


def compute_relative_path(root_path: str, file_path: str) -> str:
    rel = os.path.relpath(file_path, root_path)
    # Handle .part1.rar -> .rar (normalize multi-part archives)
    rel = re.sub(r"\.part\d+(\.[^.]+)$", r"\1", rel, flags=re.IGNORECASE)
    return rel.replace("\\", "/")


async def scan_directory(directory: str, source_id: int = None) -> list[dict]:
    books = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        category_name = Path(root).name
        if root == directory:
            category_name = ""
        else:
            category_name = os.path.relpath(root, directory).replace("\\", "/")

        for filename in files:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = filename.lower().split(".")[-1]

            if ext not in SUPPORTED_FORMATS:
                continue

            if ".part" in filename.lower() and not re.match(r".*\.part1\.rar$", filename, re.IGNORECASE):
                continue  # Skip .part2, .part3 etc, only process .part1

            book_info = {
                "file_path": filepath,
                "relative_path": compute_relative_path(directory, filepath),
                "category_name": category_name,
                "format": ext,
                "file_size": os.path.getsize(filepath),
            }

            # NOTE: file_path keeps actual path (with .part1) for file existence checks
            # relative_path is normalized (without .part1) for DB matching

            meta_file, meta_ext = find_metadata_file(filepath)
            if meta_file:
                if meta_ext == ".json":
                    metadata = await parse_json_metadata_file(meta_file)
                else:
                    metadata = await parse_metadata_file(meta_file)
                book_info.update(metadata)
                book_info["file_size"] = (
                    metadata.get("file_size") or book_info["file_size"]
                )

            cover_file, cover_ext = find_cover_file(filepath)
            if cover_file:
                book_info["cover_path"] = cover_file
                book_info["cover_ext"] = cover_ext

            if not book_info.get("title"):
                # Normalize .part1.rar filename for title
                title_filename = re.sub(r"\.part\d+(\.[^.]+)$", r"\1", filename, flags=re.IGNORECASE)
                book_info["title"] = (
                    Path(title_filename).stem.replace("_", " ").replace("-", " ")
                )

            if source_id:
                book_info["source_id"] = source_id

            books.append(book_info)

    return books


async def import_from_source(source_id: int, directory: str = None) -> dict:
    """Сканирование хранилища с подтверждением наличия и отслеживанием новых поступлений.

    Логика:
    1. Сброс устаревших флагов is_new_arrival (старше 7 дней)
    2. Поиск идентификатора хранилища (catalog.json / volume_label)
    3. Сканирование файловой системы
    4. Обработка каждого файла:
       - Существует в БД → подтверждение наличия (confirm_book_presence)
       - Новый файл → добавление через upsert_book_preserve (is_new_arrival=1)
    5. Пометка отсутствующих книг (is_available=0)
    6. Обновление времени сканирования хранилища

    Returns:
        dict: {"scanned": int, "imported": int, "confirmed": int, "missing": int, "missing_books": list}
    """
    from app.database import (
        init_db,
        get_or_create_category,
        upsert_book_preserve,
        confirm_book_presence,
        mark_books_missing,
        get_books_by_source_all,
        get_source_by_id,
        update_source_path,
        upsert_source_by_identifier,
        reset_stale_new_arrivals,
        DATABASE_PATH,
    )
    from services.drives import get_source_identifier, get_volume_label

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row

    catalog_id, volume_label, catalog_info = await get_source_identifier(directory)

    if source_id is None:
        source_data = {
            "name": catalog_info.name
            if catalog_info
            else volume_label or os.path.basename(directory),
            "type": "local",
            "path": directory,
            "volume_label": volume_label or "",
            "catalog_id": catalog_id or "",
            "is_active": 1,
            "description": f"Импортировано {directory}",
        }
        source_id = await upsert_source_by_identifier(db, source_data)
        try:
            print(
                f"Source created/found: id={source_id}, catalog_id={catalog_id}, volume_label={volume_label}"
            )
        except UnicodeEncodeError:
            pass
    else:
        source = await get_source_by_id(db, source_id)
        if source:
            await update_source_path(db, source_id, directory, volume_label)
            if catalog_id:
                source_data = {
                    "name": source["name"],
                    "type": source["type"],
                    "path": directory,
                    "volume_label": volume_label or source.get("volume_label", ""),
                    "catalog_id": catalog_id,
                    "is_active": source.get("is_active", 1),
                    "description": source.get("description", ""),
                }
                await upsert_source_by_identifier(db, source_data)

    # Сброс устаревших флагов is_new_arrival (старше 7 дней)
    await reset_stale_new_arrivals(db, source_id)

    books = await scan_directory(directory, source_id)
    scanned = len(books)
    imported = 0
    confirmed = 0
    covers_found = 0

    found_paths = []

    for book in books:
        category_id = None
        if book.get("category_name"):
            category_id = await get_or_create_category(db, book["category_name"], source_id)
            book["category_id"] = category_id

        found_paths.append(book["relative_path"])

        cursor = await db.execute(
            "SELECT id FROM books WHERE source_id = ? AND relative_path = ?",
            (source_id, book["relative_path"]),
        )
        existing = await cursor.fetchone()

        if existing:
            # Книга существует - подтверждаем наличие (is_available=1, last_seen, cover_ext)
            book_id = existing[0]
            old_cover = await db.execute("SELECT cover_ext FROM books WHERE id = ?", (book_id,))
            old_cover_ext = await old_cover.fetchone()
            await confirm_book_presence(db, book_id, book.get("file_path"))
            
            new_cover = await db.execute("SELECT cover_ext FROM books WHERE id = ?", (book_id,))
            new_cover_ext = await new_cover.fetchone()
            if old_cover_ext and not old_cover_ext[0] and new_cover_ext and new_cover_ext[0]:
                covers_found += 1
            
            confirmed += 1
        else:
            # Новая книга - добавляем с флагом is_new_arrival=1
            book_id, is_new = await upsert_book_preserve(db, book)
            if is_new:
                imported += 1
            confirmed += 1

# Получаем все книги хранилища из БД для поиска отсутствующих
    all_source_books = await get_books_by_source_all(db, source_id)
    all_db_paths = set(book["relative_path"] for book in all_source_books)

    paths_to_include = set(found_paths)
    # Книги, которые были в БД, но не найдены при сканировании
    missing_paths = all_db_paths - paths_to_include

    if missing_paths:
        # Помечаем отсутствующие книги (is_available=0)
        placeholders = ",".join("?" * len(missing_paths))
        await db.execute(
            f"UPDATE books SET is_available = 0 WHERE source_id = ? AND relative_path IN ({placeholders})",
            (source_id, *missing_paths),
        )
        await db.commit()

    missing_books = [
        {"id": book["id"], "title": book["title"], "relative_path": book["relative_path"]}
        for book in all_source_books
        if book["relative_path"] in missing_paths
    ]
    missing = len(missing_books)

    # Подсчёт общего размера хранилища
    cursor = await db.execute(
        "SELECT COALESCE(SUM(file_size), 0) FROM books WHERE source_id = ?",
        (source_id,)
    )
    total_size = (await cursor.fetchone())[0]
    await db.execute(
        "UPDATE sources SET total_size = ? WHERE id = ?",
        (total_size, source_id)
    )
    await db.commit()

    await db.close()
    print(f"\nImport complete: {imported} new, {confirmed} confirmed, {covers_found} covers found, {missing} missing, total_size={total_size}")

    return {
        "source_id": source_id,
        "scanned": scanned,
        "imported": imported,
        "confirmed": confirmed,
        "covers_found": covers_found,
        "missing": missing,
        "missing_books": missing_books,
    }


async def import_library():
    from app.database import init_db, get_or_create_category, upsert_book, DATABASE_PATH

    print(f"Scanning directory: {BOOKS_DIR}")
    await init_db()

    books = await scan_directory(BOOKS_DIR)
    print(f"Found {len(books)} books")

    imported = 0
    updated = 0

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row

    for book in books:
        category_id = None
        if book.get("category_name"):
            category_id = await get_or_create_category(db, book["category_name"], 0)  # source_id=0 for legacy import

        book["category_id"] = category_id

        book_id = await upsert_book(db, book)
        if book_id:
            print(f"  + {book.get('title', 'Unknown')}")
            imported += 1

    await db.close()
    print(f"\nImport complete: {imported} books processed")


if __name__ == "__main__":
    import asyncio

    asyncio.run(import_library())
