from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import aiosqlite

from app.database import get_db, get_all_books, get_book_by_id
from app.models import BookResponse, BookListResponse

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("", response_model=BookListResponse)
async def list_books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    books, total = await get_all_books(db, limit, offset, category)
    return {"total": total, "books": books}


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, db: aiosqlite.Connection = Depends(get_db)):
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book
