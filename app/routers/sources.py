from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import aiosqlite
import os
import logging
import asyncio
import json
import re

from app.database import (
    get_db,
    get_all_sources,
    get_source_by_id,
    insert_source,
    update_source,
    delete_source,
    update_source_scan_time,
    get_books_by_source,
    get_books_by_source_all,
    check_source_availability,
    transfer_source as db_transfer_source,
    get_source_transfer_info,
)
from app.models import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    BookListResponse,
    DiscoveredDrive,
)
from services.drives import discover_drives
from services.progress import tracker
from services.importer import import_from_source, scan_directory
from services.audit import log_audit
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

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
    log_audit(
        "source_created",
        {
            "source_id": source_id,
            "name": source.name,
            "type": source.type,
            "path": source.path,
            "volume_label": source.volume_label or "",
            "catalog_id": source.catalog_id or ""
        },
        "api"
    )
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

    log_audit(
        "source_updated",
        {"source_id": source_id, "name": existing.get("name"), "changes": update_data},
        "api"
    )
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
        logger.error("Source not found for deletion: %s", source_id)
        raise HTTPException(status_code=404, detail="Source not found")

    books_count = existing.get("books_count", 0)
    source_name = existing.get("name", "")
    logger.warning("Удаление хранилища '%s' (ID: %s) с %s книгами", source_name, source_id, books_count)

    await delete_source(db, source_id)
    logger.info("Хранилище '%s' (ID: %s) успешно удалено", source_name, source_id)

    log_audit(
        "source_deleted",
        {
            "source_id": source_id,
            "name": source_name,
            "type": existing.get("type"),
            "path": existing.get("path"),
            "books_deleted": books_count
        },
        "api"
    )

    return {
        "message": f"Хранилище '{source_name}' и {books_count} связанных книг успешно удалены",
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
    source = await get_source_by_id(db, source_id)
    if not source:
        logger.error("Source not found: %s", source_id)
        raise HTTPException(status_code=404, detail="Source not found")

    directory = source.get("path", "")
    if not directory or not os.path.exists(directory):
        logger.error("Source path does not exist: %s", directory)
        raise HTTPException(
            status_code=400, detail=f"Source path does not exist: {directory}"
        )

    source_name = source['name']
    logger.info("Starting scan for source '%s' (ID: %s), path: %s", source_name, source_id, directory)
    log_audit(
        "source_scan_start",
        {"source_id": source_id, "name": source_name, "path": directory},
        "api"
    )

    result = await import_from_source(source_id, directory)
    logger.info("Scan completed for source '%s': imported=%s, confirmed=%s, missing=%s",
                 source_name, result.get('imported', 0), result.get('confirmed', 0), result.get('missing', 0))

    log_audit(
        "source_scan_complete",
        {
            "source_id": source_id,
            "name": source_name,
            "path": directory,
            "scanned": result.get("scanned", 0),
            "imported": result.get("imported", 0),
            "confirmed": result.get("confirmed", 0),
            "covers_found": result.get("covers_found", 0),
            "missing": result.get("missing", 0),
            "missing_books": [
                {"id": b["id"], "title": b["title"], "path": b["relative_path"]}
                for b in result.get("missing_books", [])
            ]
        },
        "api"
    )

    return {
        "message": f"Сканирование хранилища '{source_name}' завершено: найдено {result.get('covers_found', 0)} обложек",
        "source_id": result.get("source_id"),
        "scanned": result.get("scanned", 0),
        "imported": result.get("imported", 0),
        "confirmed": result.get("confirmed", 0),
        "covers_found": result.get("covers_found", 0),
        "missing": result.get("missing", 0),
        "missing_books": result.get("missing_books", []),
    }


@router.get("/{source_id}/scan-stream")
async def scan_source_stream(source_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """SSE endpoint: starts scan in background and streams real-time progress."""
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    directory = source.get("path", "")
    if not directory or not os.path.exists(directory):
        raise HTTPException(status_code=400, detail=f"Source path does not exist: {directory}")

    try:
        books_preview = await scan_directory(directory, source_id)
        total_files = len(books_preview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan directory: {str(e)}")

    async def progress_handler(stats: dict):
        event = stats.get("event", "update")
        if event in ("update", "finalizing"):
            await tracker.update(
                source_id,
                processed=stats.get("processed", 0),
                imported=stats.get("imported", 0),
                confirmed=stats.get("confirmed", 0),
                covers_found=stats.get("covers_found", 0),
                current_file=stats.get("current_file", ""),
                log_message=stats.get("log_message", ""),
                status=stats.get("status", ""),
            )
        elif event == "complete":
            await tracker.complete(
                source_id,
                missing=stats.get("missing", 0),
                missing_books=stats.get("missing_books", []),
                imported=stats.get("imported", 0),
                confirmed=stats.get("confirmed", 0),
                covers_found=stats.get("covers_found", 0),
            )

    await tracker.start(source_id, source["name"], total_files)

    async def run_scan():
        source_name = source["name"]
        log_audit(
            "source_scan_start",
            {"source_id": source_id, "name": source_name, "path": directory, "mode": "stream"},
            "api"
        )
        try:
            result = await import_from_source(source_id, directory, progress_callback=progress_handler)
            logger.info("Stream scan completed for source '%s': %s", source_name, result)
            await tracker.complete(
                source_id,
                missing=result.get("missing", 0),
                missing_books=result.get("missing_books", []),
                imported=result.get("imported", 0),
                confirmed=result.get("confirmed", 0),
                covers_found=result.get("covers_found", 0),
            )
            log_audit(
                "source_scan_complete",
                {
                    "source_id": source_id,
                    "name": source_name,
                    "path": directory,
                    "scanned": result.get("scanned", 0),
                    "imported": result.get("imported", 0),
                    "confirmed": result.get("confirmed", 0),
                    "covers_found": result.get("covers_found", 0),
                    "missing": result.get("missing", 0),
                    "missing_books": [
                        {"id": b["id"], "title": b["title"], "path": b["relative_path"]}
                        for b in result.get("missing_books", [])
                    ],
                    "mode": "stream"
                },
                "api"
            )
        except Exception as e:
            logger.error("Stream scan error for source %d: %s", source_id, e)
            log_audit(
                "source_scan_error",
                {"source_id": source_id, "name": source_name, "path": directory, "error": str(e)},
                "api"
            )
            await tracker.error(source_id, str(e))
        finally:
            await asyncio.sleep(5)
            await tracker.cleanup(source_id)

    asyncio.create_task(run_scan())

    async def event_generator():
        try:
            async for event in tracker.event_stream(source_id):
                yield event
        except asyncio.CancelledError:
            await tracker.cleanup(source_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    source = await get_source_by_id(db, source_id)
    source_name = source.get("name", "unknown") if source else "unknown"

    logger.warning("Starting transfer of source '%s' (ID: %s) to path: %s", source_name, source_id, target_path)
    log_audit(
        "source_transfer_start",
        {"source_id": source_id, "name": source_name, "old_path": source.get("path") if source else "", "target_path": target_path},
        "api"
    )

    result = await db_transfer_source(
        db, source_id, target_path, target_source_id, conflict_callback=None
    )
    if not result.get("success"):
        logger.error("Transfer failed for source '%s' (ID: %s): %s", source_name, source_id, result.get("message"))
        log_audit(
            "source_transfer_error",
            {"source_id": source_id, "name": source_name, "target_path": target_path, "error": result.get("message")},
            "api"
        )
        raise HTTPException(status_code=400, detail=result.get("message"))

    logger.info("Transfer completed for source '%s' (ID: %s): %s books transferred",
                 source_name, source_id, result.get("transferred_count", 0))
    log_audit(
        "source_transferred",
        {
            "source_id": source_id,
            "name": source_name,
            "old_path": source.get("path") if source else "",
            "target_path": target_path,
            "transferred": result.get("transferred_count", 0),
            "deleted_originals": result.get("deleted_originals", 0),
            "errors_count": result.get("errors_count", 0),
            "errors": result.get("errors", []),
            "operation_log": result.get("operation_log", [])
        },
        "api"
    )
    return result


@router.post("/{source_id}/anomalies")
async def find_source_anomalies(
    source_id: int, db: aiosqlite.Connection = Depends(get_db)
):
    """Сканирование хранилища на аномалии: файлы не в БД, артефакты, мусор."""
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    directory = source.get("path", "")
    if not directory or not os.path.exists(directory):
        raise HTTPException(
            status_code=400, detail=f"Source path does not exist: {directory}"
        )

    source_name = source.get("name", "unknown")

    # Collect all known DB paths and stems
    db_books = await get_books_by_source_all(db, source_id)
    db_paths = set()
    known_extra = set()
    db_stems = set()

    for book in db_books:
        rel = book.get("relative_path", "")
        if rel:
            rel = rel.replace("\\", "/")
            db_paths.add(rel)
            stem = os.path.splitext(rel)[0]
            db_stems.add(stem)
            stem_clean = re.sub(r"\.part\d+$", "", stem)
            if stem_clean != stem:
                db_stems.add(stem_clean)

        extra = book.get("extra_files", "")
        if extra:
            try:
                for ef in json.loads(extra):
                    known_extra.add(ef.replace("\\", "/"))
            except (json.JSONDecodeError, TypeError):
                pass

    from config import SUPPORTED_FORMATS, COVER_EXTENSIONS

    metadata_exts = {"txt", "json", "html", "dusd"}
    all_known_exts = set(SUPPORTED_FORMATS) | metadata_exts | set(COVER_EXTENSIONS)

    anomalies = []
    empty_dirs = []
    scanned_files = 0

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        rel_dir = os.path.relpath(root, directory).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        # Check empty directories
        if not files and not dirs and rel_dir:
            empty_dirs.append(rel_dir)

        for filename in files:
            if filename.startswith("."):
                continue

            scanned_files += 1
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, directory).replace("\\", "/")

            # Skip known books and extra files
            if rel_path in db_paths or rel_path in known_extra:
                continue

            size = os.path.getsize(filepath)
            file_lower = filename.lower()

            # Multi-part orphan: .z01, .z02 ...
            if re.search(r'\.z\d{2}$', file_lower):
                anomalies.append({
                    "type": "multi_part_orphan",
                    "type_label": "Фрагмент многотомного архива",
                    "path": rel_path, "size": size,
                    "description": "Файл .zxx — часть многотомного архива без основного тома"
                })
                continue

            # RAR multi-part orphan: .part2.rar, .part3.rar ...
            if ".part" in file_lower and file_lower.endswith(".rar"):
                anomalies.append({
                    "type": "multi_part_orphan",
                    "type_label": "Фрагмент многотомного RAR",
                    "path": rel_path, "size": size,
                    "description": "Файл .partN.rar без основного .part1.rar"
                })
                continue

            # 7z split orphan: .7z.002, .7z.003 ...
            m_7z = re.match(r'^(.+\.7z)\.(\d{3})$', file_lower)
            if m_7z and m_7z.group(2) != '001':
                anomalies.append({
                    "type": "multi_part_orphan",
                    "type_label": "Фрагмент многотомного 7z",
                    "path": rel_path, "size": size,
                    "description": f"Файл .7z.{m_7z.group(2)} без основного .7z.001"
                })
                continue

            ext = file_lower.split(".")[-1]

            # Unlisted supported format (book file not in DB)
            if ext in SUPPORTED_FORMATS:
                anomalies.append({
                    "type": "unlisted_supported",
                    "type_label": "Неучтённая книга",
                    "path": rel_path, "size": size,
                    "description": f"Файл формата .{ext} есть в хранилище, но отсутствует в базе данных"
                })
                continue

            # Metadata files (.txt, .json, .html, .dusd)
            if ext in metadata_exts:
                base = os.path.splitext(rel_path)[0]
                base2 = os.path.splitext(base)[0]
                has_book = base in db_stems or base2 in db_stems

                if not has_book:
                    is_double = any(base.endswith(f".{f}") for f in SUPPORTED_FORMATS)
                    if is_double:
                        anomalies.append({
                            "type": "double_ext_metadata",
                            "type_label": "Метаданные с двойным расширением",
                            "path": rel_path, "size": size,
                            "description": f"Файл метаданных с двойным расширением (.{ext}) — вероятно, остался после перемещения книги"
                        })
                    else:
                        anomalies.append({
                            "type": "metadata_orphan",
                            "type_label": "Метаданные без книги",
                            "path": rel_path, "size": size,
                            "description": f"Файл метаданных (.{ext}) не имеет соответствующей книги в базе"
                        })
                continue

            # .dusd files
            if ext == "dusd":
                anomalies.append({
                    "type": "dusd_file",
                    "type_label": "Файл Download Master",
                    "path": rel_path, "size": size,
                    "description": "Файл .dusd — артефакт программы Download Master"
                })
                continue

            # Cover files without matching book
            if ext in COVER_EXTENSIONS:
                anomalies.append({
                    "type": "orphan_cover",
                    "type_label": "Обложка без книги",
                    "path": rel_path, "size": size,
                    "description": f"Файл обложки (.{ext}) не имеет соответствующей книги в базе"
                })
                continue

            # Unknown / unrecognized file type
            if ext not in all_known_exts:
                anomalies.append({
                    "type": "unknown_type",
                    "type_label": "Неизвестный тип",
                    "path": rel_path, "size": size,
                    "description": f"Файл неизвестного типа (.{ext}) не относится к поддерживаемым форматам"
                })

    # Aggregate summary
    summary = {}
    for a in anomalies:
        t = a["type"]
        summary[t] = summary.get(t, 0) + 1

    return {
        "success": True,
        "source_id": source_id,
        "source_name": source_name,
        "directory": directory,
        "scanned_files": scanned_files,
        "db_books_count": len(db_paths),
        "anomalies": anomalies,
        "empty_directories": sorted(empty_dirs),
        "summary": summary,
        "total_anomalies": len(anomalies),
    }
