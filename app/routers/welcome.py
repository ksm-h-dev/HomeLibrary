from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
import subprocess
import os
from pathlib import Path

from app.database import get_db, get_all_sources, get_stats
from app.models import (
    SetupStatus,
    FolderSelectRequest,
    FolderSelectResponse,
    InitialScanResponse,
    SavePathRequest,
    InitializeLibraryResponse,
)
from config import DEFAULT_SOURCE_PATH
from services.drives import discover_drives

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
async def get_setup_status(db: aiosqlite.Connection = Depends(get_db)):
    """Check if this is the first run and return setup status"""
    sources = await get_all_sources(db)
    stats = await get_stats(db)

    total_books = stats.get("total_books", 0)
    total_sources = len(sources)

    # First run if: no sources AND no books
    is_first_run = total_sources == 0 and total_books == 0

    # Needs setup if first run OR if we have valid default path but no sources to scan from
    # Show setup wizard if there's a default path that could be used but no sources exist yet
    config_has_path = DEFAULT_SOURCE_PATH and os.path.exists(DEFAULT_SOURCE_PATH)
    needs_setup = is_first_run or (config_has_path and total_sources == 0)

    return SetupStatus(
        is_first_run=is_first_run,
        default_source_path=DEFAULT_SOURCE_PATH,
        has_books=total_books > 0,
        total_books=total_books,
        total_sources=total_sources,
        needs_setup=needs_setup,
    )


@router.get("/drives")
async def get_available_drives():
    """Get list of available drives for selection"""
    return await discover_drives()


@router.post("/select-folder", response_model=FolderSelectResponse)
async def select_folder(request: FolderSelectRequest):
    """Open Windows Folder Browser Dialog using PowerShell"""
    try:
        # PowerShell script to open FolderBrowserDialog
        ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Выберите папку с библиотекой"
$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer

if ("{request.drive_letter}") {{
    try {{
        $dialog.SelectedPath = "{request.drive_letter}:\\"
    }} catch {{}}
}}

$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Output $dialog.SelectedPath
}} else {{
    Write-Output "CANCELLED"
}}
'''

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            selected_path = result.stdout.strip()
            if selected_path == "CANCELLED":
                return FolderSelectResponse(
                    selected_path="",
                    success=False,
                    message="User cancelled folder selection",
                )
            if selected_path and os.path.exists(selected_path):
                return FolderSelectResponse(
                    selected_path=selected_path,
                    success=True,
                    message="Folder selected successfully",
                )

        return FolderSelectResponse(
            selected_path="",
            success=False,
            message="Failed to select folder",
        )

    except Exception as e:
        return FolderSelectResponse(
            selected_path="",
            success=False,
            message=f"Error: {str(e)}",
        )


@router.post("/save-path")
async def save_default_path(body: SavePathRequest):
    """Save the selected path as DEFAULT_SOURCE_PATH in config"""
    path = body.path
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=400, detail="Папка не существует")

        # Update config.py file
        config_path = Path(__file__).parent.parent.parent / "config.py"

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Escape backslashes for regex replacement
            escaped_path = path.replace("\\", "\\\\")

            # Replace DEFAULT_SOURCE_PATH line - match both formats
            import re

            # Try to find and replace the existing DEFAULT_SOURCE_PATH line
            pattern = r"DEFAULT_SOURCE_PATH\s*=\s*.*$"
            replacement = f'DEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", r"{escaped_path}")'

            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            else:
                # Add if not exists
                content = (
                    content
                    + f'\nDEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", r"{escaped_path}")  # Added by setup\n'
                )

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)

        return {"success": True, "path": path, "message": "Путь сохранен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")


@router.post("/scan", response_model=InitialScanResponse)
async def perform_initial_scan(
    db: aiosqlite.Connection = Depends(get_db), body: SavePathRequest = None
):
    """Perform initial scan of DEFAULT_SOURCE_PATH or provided path"""
    from services.importer import import_from_source
    import config

    # Try to use path from request body first, then fall back to config
    current_path = None

    if body and body.path:
        current_path = body.path
    else:
        # Reload config to get the latest DEFAULT_SOURCE_PATH
        import importlib

        importlib.reload(config)
        current_path = config.DEFAULT_SOURCE_PATH

    if not current_path:
        raise HTTPException(
            status_code=400,
            detail="Путь к библиотеке не настроен. Выберите папку с книгами.",
        )

    if not os.path.exists(current_path):
        raise HTTPException(
            status_code=400, detail=f"Папка не существует: {current_path}"
        )

    try:
        # Import with source_id=None to create new source
        result = await import_from_source(None, current_path)

        return InitialScanResponse(
            success=True,
            source_id=result.get("source_id", 0),
            scanned=result.get("scanned", 0),
            imported=result.get("imported", 0),
            updated=result.get("updated", 0),
            skipped=result.get("skipped", 0),
            message=f"Сканирование завершено: импортировано {result.get('imported', 0)} новых книг",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при сканировании: {str(e)}"
        )


@router.post("/skip")
async def skip_setup():
    """Skip initial setup - will have empty library"""
    return {"success": True, "message": "Setup skipped. You can add sources later."}


@router.post("/initialize")
async def initialize_library(db: aiosqlite.Connection = Depends(get_db)):
    """Reset library to initial state - delete all books and sources"""
    try:
        # Count items before deletion for response
        cursor = await db.execute("SELECT COUNT(*) FROM books")
        books_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM sources")
        sources_count = (await cursor.fetchone())[0]

        # Delete all books first (cascades to book_tags via ON DELETE CASCADE)
        await db.execute("DELETE FROM books")

        # Delete all sources
        await db.execute("DELETE FROM sources")

        # Delete all categories (optional - keeping them might be useful)
        # await db.execute("DELETE FROM categories")

        # Clear FTS index by deleting all entries (triggers will handle this but FTS table needs manual cleanup)
        await db.execute("DELETE FROM books_fts")

        await db.commit()

        return {
            "success": True,
            "message": "Library initialized successfully",
            "books_deleted": books_count,
            "sources_deleted": sources_count,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize library: {str(e)}"
        )
