from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
import aiosqlite
import os
import subprocess
import platform

from app.database import (
    get_db,
    get_all_books,
    get_book_by_id,
    update_book,
    get_categories,
)
from app.models import BookResponse, BookListResponse, BookUpdate, CategoryResponse

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("", response_model=BookListResponse)
async def list_books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    format: Optional[str] = None,
    year: Optional[int] = None,
    source_id: Optional[int] = None,
    sort_by: Optional[str] = Query("date", regex="^(date|title|author|year|pages)$"),
    availability: Optional[str] = Query(None, regex="^(available|missing|new)$"),
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
        raise HTTPException(status_code=404, detail="Book not found")

    await update_book(db, book_id, book.model_dump(exclude_none=True))
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
