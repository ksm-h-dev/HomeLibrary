from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional, Any
from pydantic import BaseModel
import aiosqlite
import os
import json
import subprocess
import platform
import logging
from pathlib import Path
import httpx
import re

from app.database import (
    get_db,
    get_all_books,
    get_book_by_id,
    update_book,
    get_categories,
    export_book_to_json,
    move_book_files,
    cleanup_unavailable_books,
)
from app.models import BookResponse, BookListResponse, BookUpdate, CategoryResponse
from services.audit import log_audit
from config import COVER_EXTENSIONS, DATABASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("", response_model=BookListResponse)
async def list_books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    format: Optional[str] = None,
    year: Optional[int] = None,
    source_id: Optional[int] = None,
    sort_by: Optional[str] = Query("date", pattern="^(date|title|author|year|pages)$"),
    availability: Optional[str] = Query(None, pattern="^(available|missing|new)$"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Получение списка книг с фильтрацией.

    Параметр availability:
    - "available" - только книги в наличии (is_available=1)
    - "missing" - только отсутствующие (is_available=0)
    - "new" - новые поступления (is_new_arrival=1, сортировка по last_seen DESC)
    """
    books, total = await get_all_books(
        db, limit, offset, category, format, year, source_id, sort_by, availability
    )
    return {"total": total, "books": books}


@router.get("/categories")
async def list_categories(db: aiosqlite.Connection = Depends(get_db)):
    return await get_categories(db)


@router.get("/duplicates")
async def find_duplicates(db: aiosqlite.Connection = Depends(get_db)):
    """Находит потенциальные дубликаты книг в одном хранилище."""
    cursor = await db.execute("""
        SELECT id, title, author, file_path, file_size, year, pages,
               source_id, relative_path
        FROM books ORDER BY file_size, file_path
    """)
    rows = await cursor.fetchall()
    columns = [d[0] for d in cursor.description]

    groups = {}
    for row in rows:
        d = dict(zip(columns, row))
        fname = d["file_path"].split("\\")[-1].lower()
        key = (d["source_id"], d["file_size"], fname)
        groups.setdefault(key, []).append(d)

    result = []
    for key, books in groups.items():
        if len(books) > 1:
            result.append({
                "file_name": key[2],
                "file_size": key[1],
                "source_id": key[0],
                "books": books
            })

    for group in result:
        cursor = await db.execute("SELECT name FROM sources WHERE id = ?", (group["source_id"],))
        row = await cursor.fetchone()
        group["source_name"] = row[0] if row else f"ID {group['source_id']}"

    return {"groups": result, "total": len(result)}


class MergeDuplicatesRequest(BaseModel):
    decisions: list[dict]


@router.post("/duplicates/merge")
async def merge_duplicates(
    body: MergeDuplicatesRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Удаляет выбранные дубликаты книг из базы (без удаления файлов)."""
    deleted_count = 0
    for decision in body.decisions:
        delete_ids = decision.get("delete_ids", [])
        keep_id = decision.get("keep_id")
        group_key = decision.get("group_key", "")

        for bid in delete_ids:
            await db.execute("DELETE FROM books WHERE id = ?", (bid,))
            deleted_count += 1
            log_audit(
                "duplicate_removed",
                {"book_id": bid, "kept_id": keep_id, "group": group_key},
                "api"
            )

    await db.commit()
    return {
        "deleted": deleted_count,
        "message": f"Удалено {deleted_count} дубликатов"
    }


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, db: aiosqlite.Connection = Depends(get_db)):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.put("/{book_id}")
async def update_book_endpoint(
    book_id: int,
    book: BookUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    existing = await get_book_by_id(db, book_id)
    if not existing:
        logger.error("Book not found for update: %s", book_id)
        raise HTTPException(status_code=404, detail="Book not found")
    
    update_data = book.model_dump(exclude_unset=True, exclude_none=True)
    logger.info("Updating book ID %s: %s", book_id, update_data)
    
    new_cat_id = update_data.get("category_id")
    cat_changed = new_cat_id is not None and new_cat_id != existing.get("category_id")
    
    if cat_changed:
        move_result = await move_book_files(db, book_id, new_cat_id)
        logger.info("Moved book files for book ID %s", book_id)
        log_audit(
            "book_files_moved",
            {
                "book_id": book_id,
                "title": existing.get("title"),
                "old_path": move_result.get("old_path"),
                "new_path": move_result.get("new_path"),
                "success": move_result.get("success")
            },
            "api"
        )
    
    await update_book(db, book_id, update_data)
    logger.info("Book ID %s updated successfully", book_id)
    
    export_result = await export_book_to_json(db, book_id)
    logger.info("Exported metadata to JSON for book ID %s", book_id)
    log_audit(
        "book_exported",
        {"book_id": book_id, "export_path": export_result.get("path"), "title": update_data.get("title", existing.get("title"))},
        "api"
    )
    
    log_audit(
        "book_updated",
        {"book_id": book_id, "title": existing.get("title"), "changes": update_data},
        "api"
    )
    return await get_book_by_id(db, book_id)


@router.post("/{book_id}/open")
async def open_book(book_id: int, db: aiosqlite.Connection = Depends(get_db)):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    file_path = book.get("file_path", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="File path is empty")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    actual_size = os.path.getsize(file_path)
    stored_size = book.get("file_size", 0)
    warning = None
    if stored_size and actual_size != stored_size:
        logger.info("File size mismatch for book ID %s: stored=%s, actual=%s — updating", book_id, stored_size, actual_size)
        await db.execute("UPDATE books SET file_size = ? WHERE id = ?", (actual_size, book_id))
        await db.commit()
        log_audit("file_size_updated", {"book_id": book_id, "old_size": stored_size, "new_size": actual_size}, "api")
        warning = f"Размер файла изменился (был {stored_size} байт, стал {actual_size} байт). Возможно, файл был обновлён или заменён."

    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", file_path])
    else:
        subprocess.run(["xdg-open", file_path])

    result = {"success": True, "message": "Файл открыт"}
    if warning:
        result["warning"] = warning
    return result


@router.post("/cleanup")
async def cleanup_unavailable(db: aiosqlite.Connection = Depends(get_db)):
    """Удаляет все недоступные книги из базы."""
    logger.warning("Starting cleanup of unavailable books")
    count = await cleanup_unavailable_books(db)
    logger.info("Cleanup completed: %s books deleted", count)
    log_audit(
        "cleanup_unavailable",
        {"deleted_count": count},
        "api"
    )
    return {"deleted": count, "message": f"Удалено {count} недоступных книг"}


class SaveRichMetadataRequest(BaseModel):
    """Запрос на сохранение расширенных метаданных книги (результат поиска по коду).

    lookup_source — источник данных ("openlibrary", "crossref", "issn")
    lookup_code  — тип найденного кода ("isbn13", "doi", "issn")
    raw          — сырой ответ внешнего API (сохраняется в .lookup.json)
    source_url   — ссылка на страницу книги в источнике
    cover_url    — URL обложки из внешнего источника
    """
    lookup_source: Optional[str] = None
    lookup_code: Optional[str] = None
    raw: Optional[Any] = None
    source_url: Optional[str] = None
    cover_url: Optional[str] = None


async def _download_cover_background(
    book_id: int,
    cover_url: str,
    json_dir: str,
    book_filename: str,
    source_id: int,
):
    """Фоновая задача: скачивание обложки и обновление БД."""
    try:
        async with aiosqlite.connect(DATABASE_URL) as bg_db:
            bg_db.row_factory = aiosqlite.Row
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(cover_url)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    url_ext = re.search(r'\.(\w+)(?:\?.*)?$', cover_url.split("/")[-1])
                    if url_ext and url_ext.group(1).lower() in COVER_EXTENSIONS:
                        ext = url_ext.group(1).lower()
                    elif "jpeg" in content_type:
                        ext = "jpg"
                    elif "png" in content_type:
                        ext = "png"
                    elif "gif" in content_type:
                        ext = "gif"
                    elif "webp" in content_type:
                        ext = "webp"
                    else:
                        ext = "jpg"

                    cover_filename = f"{book_filename}.{ext}"
                    cover_path = os.path.join(json_dir, cover_filename)

                    with open(cover_path, "wb") as f:
                        f.write(resp.content)

                    await bg_db.execute(
                        "UPDATE books SET cover_path = ?, cover_ext = ? WHERE id = ?",
                        (cover_path, ext, book_id)
                    )
                    await bg_db.commit()
                    logger.info("Background cover downloaded to %s for book ID %s", cover_path, book_id)
                    log_audit("cover_downloaded", {"book_id": book_id, "cover_url": cover_url, "cover_path": cover_path, "status": "success"}, "api")
                else:
                    logger.warning("Background cover download failed status %s for book ID %s", resp.status_code, book_id)
                    log_audit("cover_downloaded", {"book_id": book_id, "cover_url": cover_url, "status": "http_error", "http_status": resp.status_code}, "api")
    except Exception as e:
        logger.error("Background cover download error for book ID %s: %s", book_id, e)
        log_audit("cover_downloaded", {"book_id": book_id, "cover_url": cover_url, "status": "error", "error": str(e)}, "api")


@router.post("/{book_id}/save-metadata")
async def save_book_rich_metadata(
    book_id: int,
    body: SaveRichMetadataRequest,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Сохраняет расширенные метаданные книги в .lookup.json рядом с файлом книги.
    Обложка скачивается в фоновой задаче.
    """
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    source_base_path = book.get("source_name", "")
    cursor = await db.execute("SELECT path FROM sources WHERE id = ?", (book.get("source_id"),))
    source_row = await cursor.fetchone()
    if not source_row:
        raise HTTPException(status_code=500, detail="Source not found")

    source_base_path = source_row[0]

    book_relative_path = book.get("relative_path", "")
    book_dir = os.path.dirname(book_relative_path) if book_relative_path else ""
    book_filename = os.path.splitext(os.path.basename(book.get("file_path", "book")))[0]

    json_dir = os.path.join(source_base_path, book_dir) if book_dir else source_base_path
    json_path = os.path.join(json_dir, f"{book_filename}.lookup.json")

    os.makedirs(json_dir, exist_ok=True)

    entry = {
        "lookup_source": body.lookup_source,
        "lookup_code": body.lookup_code,
        "source_url": body.source_url,
        "cover_url": body.cover_url,
        "raw": body.raw,
        "looked_up_at": __import__("datetime").datetime.now().isoformat(),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Rich metadata saved to %s for book ID %s", json_path, book_id)
    log_audit("lookup_metadata_saved", {
        "book_id": book_id,
        "lookup_path": json_path,
        "lookup_source": body.lookup_source,
        "lookup_code": body.lookup_code,
        "has_cover_url": bool(body.cover_url)
    }, "api")

    cover_downloaded = False
    if body.cover_url:
        background_tasks.add_task(
            _download_cover_background,
            book_id, body.cover_url, json_dir, book_filename, book.get("source_id")
        )
        cover_downloaded = True

    return {"success": True, "path": json_path, "cover_downloaded": cover_downloaded}

