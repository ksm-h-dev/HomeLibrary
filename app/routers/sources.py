from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import aiosqlite
import os

from app.database import (
    get_db,
    get_all_sources,
    get_source_by_id,
    insert_source,
    update_source,
    delete_source,
    update_source_scan_time,
    get_books_by_source,
    check_source_availability,
    get_source_transfer_info,
    transfer_source,
)
from app.models import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    BookListResponse,
    DiscoveredDrive,
)
from services.drives import discover_drives

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    active_only: bool = Query(False), db: aiosqlite.Connection = Depends(get_db)
):
    return await get_all_sources(db, active_only)


@router.get("/discover", response_model=list[DiscoveredDrive])
async def discover_connected_drives():
    return await discover_drives()


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    source: SourceCreate, db: aiosqlite.Connection = Depends(get_db)
):
    source_id = await insert_source(db, source.model_dump())
    return await get_source_by_id(db, source_id)


@router.put("/{source_id}", response_model=SourceResponse)
async def edit_source(
    source_id: int, source: SourceUpdate, db: aiosqlite.Connection = Depends(get_db)
):
    existing = await get_source_by_id(db, source_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = source.model_dump(exclude_unset=True, exclude_none=True)
    update_data["is_active"] = update_data.get(
        "is_active", existing.get("is_active", True)
    )

    if update_data.get("path") or update_data.get("catalog_id"):
        status = check_source_availability(update_data)
        await update_source(
            db, source_id, {**update_data, "availability_status": status}
        )
    else:
        await update_source(db, source_id, update_data)
    return await get_source_by_id(db, source_id)


@router.post("/{source_id}/check")
async def check_source_status(
    source_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    status = check_source_availability(source)
    return {"source_id": source_id, "availability_status": status}


@router.delete("/{source_id}")
async def remove_source(source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    existing = await get_source_by_id(db, source_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Source not found")

    # Получаем количество книг перед удалением
    books_count = existing.get("books_count", 0)
    source_name = existing.get("name", "")

    await delete_source(db, source_id)

    return {
        "message": f"Source '{source_name}' and {books_count} associated books deleted successfully",
        "source_id": source_id,
        "source_name": source_name,
        "books_deleted": books_count,
    }


@router.get("/{source_id}/books", response_model=BookListResponse)
async def get_source_books(
    source_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    books, total = await get_books_by_source(db, source_id, limit, offset)
    return {"total": total, "books": books}


@router.post("/{source_id}/scan")
async def scan_source(source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    from services.importer import import_from_source

    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    directory = source.get("path", "")
    if not directory or not os.path.exists(directory):
        raise HTTPException(
            status_code=400, detail=f"Source path does not exist: {directory}"
        )

    result = await import_from_source(source_id, directory)

    return {
        "message": f"Scan completed for {source['name']}: {result.get('covers_found', 0)} обложек найдено",
        "source_id": result.get("source_id"),
        "scanned": result.get("scanned", 0),
        "imported": result.get("imported", 0),
        "confirmed": result.get("confirmed", 0),
        "covers_found": result.get("covers_found", 0),
        "missing": result.get("missing", 0),
        "missing_books": result.get("missing_books", []),
    }


@router.get("/{source_id}/transfer-info")
async def get_transfer_info(source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """Возвращает информацию о хранилище для переноса."""
    info = await get_source_transfer_info(db, source_id)
    if not info:
        raise HTTPException(status_code=404, detail="Source not found")
    return info


@router.post("/{source_id}/transfer")
async def transfer_source(
    source_id: int,
    target_path: str,
    target_source_id: Optional[int] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Переносит хранилище в новое место."""
    result = await transfer_source(
        db, source_id, target_path, target_source_id, conflict_callback=None
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result
