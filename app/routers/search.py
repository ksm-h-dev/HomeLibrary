from fastapi import APIRouter, Depends, Query
from typing import Optional
import aiosqlite
import logging

from app.database import get_db, search_books, get_categories, get_stats
from app.models import SearchResponse, CategoryResponse, StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    format: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[int] = None,
    source_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: Optional[str] = Query("date", pattern="^(date|title|author|pages)$"),
    availability: Optional[str] = Query(None, pattern="^(available|missing|new)$"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Полнотекстовый поиск с фильтрацией по наличию.

    Параметр availability:
    - "available" - только книги в наличии
    - "missing" - только отсутствующие книги
    - "new" - новые поступления (is_new_arrival=1), сортировка по last_seen DESC
    """
    logger.info("Search query: '%s', filters: format=%s, category=%s, year=%s, source_id=%s, availability=%s",
                q, format, category, year, source_id, availability)
    books, total = await search_books(
        db, q, format, category, year, source_id, limit, offset, sort_by, availability
    )
    logger.info("Search returned %s results for query: '%s'", total, q)
    return {"total": total, "query": q, "books": books}


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(db: aiosqlite.Connection = Depends(get_db)):
    return await get_categories(db)


@router.get("/stats", response_model=StatsResponse)
async def stats(db: aiosqlite.Connection = Depends(get_db)):
    return await get_stats(db)
