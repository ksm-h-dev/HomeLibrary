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


def find_metadata_file(book_path: str) -> str | None:
    base = Path(book_path).with_suffix("")
    for ext in [".txt", ".html", ".dusd"]:
        meta_file = str(base) + ext
        if os.path.exists(meta_file):
            return meta_file
    return None


def find_cover_file(book_path: str) -> str | None:
    base = Path(book_path).with_suffix("")
    for ext in COVER_EXTENSIONS:
        cover_file = str(base) + f".{ext}"
        if os.path.exists(cover_file):
            return cover_file
    return None


def compute_relative_path(root_path: str, file_path: str) -> str:
    rel = os.path.relpath(file_path, root_path)
    return rel.replace("\\", "/")


async def scan_directory(directory: str, source_id: int = None) -> list[dict]:
    books = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        category_name = Path(root).name
        if root == directory:
            category_name = ""

        for filename in files:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = filename.lower().split(".")[-1]

            if ext not in SUPPORTED_FORMATS:
                continue

            if ".part" in filename.lower():
                continue

            book_info = {
                "file_path": filepath,
                "relative_path": compute_relative_path(directory, filepath),
                "category_name": category_name,
                "format": ext,
                "file_size": os.path.getsize(filepath),
            }

            meta_file = find_metadata_file(filepath)
            if meta_file:
                metadata = await parse_metadata_file(meta_file)
                book_info.update(metadata)
                book_info["file_size"] = (
                    metadata.get("file_size") or book_info["file_size"]
                )

            cover_file = find_cover_file(filepath)
            if cover_file:
                book_info["cover_path"] = cover_file

            if not book_info.get("title"):
                book_info["title"] = (
                    Path(filename).stem.replace("_", " ").replace("-", " ")
                )

            if source_id:
                book_info["source_id"] = source_id

            books.append(book_info)

    return books


async def import_from_source(source_id: int, directory: str = None) -> dict:
    from app.database import (
        init_db,
        get_or_create_category,
        upsert_book,
        get_source_by_id,
        update_source_path,
        upsert_source_by_identifier,
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
        print(
            f"Source created/found: id={source_id}, catalog_id={catalog_id}, volume_label={volume_label}"
        )
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

    await init_db()

    books = await scan_directory(directory, source_id)
    scanned = len(books)
    imported = 0
    updated = 0
    skipped = 0

    for book in books:
        category_id = None
        if book.get("category_name"):
            category_id = await get_or_create_category(db, book["category_name"])

        book["category_id"] = category_id
        book["source_id"] = source_id

        cursor = await db.execute(
            "SELECT id FROM books WHERE source_id = ? AND relative_path = ?",
            (source_id, book["relative_path"]),
        )
        existing = await cursor.fetchone()

        book_id = await upsert_book(db, book)

        if existing:
            updated += 1
            print(f"  ~ Updated: {book.get('title', 'Unknown')}")
        elif book_id:
            imported += 1
            print(f"  + New: {book.get('title', 'Unknown')}")
        else:
            skipped += 1
            print(f"  - Skipped: {book.get('title', 'Unknown')}")

    await db.close()
    print(f"\nImport complete: {imported} new, {updated} updated, {skipped} skipped")

    return {
        "source_id": source_id,
        "scanned": scanned,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
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
            category_id = await get_or_create_category(db, book["category_name"])

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
