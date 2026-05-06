from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
import aiosqlite
import os
import subprocess
import platform
import logging

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
    
    if "relative_path" in update_data or "category_id" in update_data:
        export_result = await export_book_to_json(db, book_id)
        logger.info("Exported metadata to JSON for book ID %s", book_id)
        log_audit(
            "book_exported",
            {"book_id": book_id, "export_path": export_result.get("path"), "title": existing.get("title")},
            "api"
        )
    
    new_cat_id = update_data.get("category_id")
    if new_cat_id:
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

    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", file_path])
    else:
        subprocess.run(["xdg-open", file_path])

    return {"success": True, "message": "File opened"}


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
