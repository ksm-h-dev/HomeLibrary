from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite
import subprocess
import os
import logging
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
from services.audit import log_audit, is_enabled as audit_is_enabled

router = APIRouter(prefix="/api/setup", tags=["setup"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SetupStatus)
async def get_setup_status(db: aiosqlite.Connection = Depends(get_db)):
    """Check if this is the first run and return setup status"""
    sources = await get_all_sources(db)
    stats = await get_stats(db)

    total_books = stats.get("total_books", 0)
    total_sources = len(sources)

    # First run if: no sources AND no books
    is_first_run = total_sources == 0 and total_books == 0

    # Needs setup only on first run with no data (user can add sources from main page)
    needs_setup = is_first_run

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
                content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)
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

    log_audit(
        "initial_scan_start",
        {"path": current_path},
        "setup"
    )

    try:
        # Import with source_id=None to create new source
        result = await import_from_source(None, current_path)

        log_audit(
            "initial_scan_complete",
            {
                "path": current_path,
                "source_id": result.get("source_id", 0),
                "scanned": result.get("scanned", 0),
                "imported": result.get("imported", 0),
                "confirmed": result.get("confirmed", 0),
                "missing": result.get("missing", 0)
            },
            "setup"
        )

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
        log_audit(
            "initial_scan_error",
            {"path": current_path, "error": str(e)},
            "setup"
        )
        raise HTTPException(
            status_code=500, detail=f"Ошибка при сканировании: {str(e)}"
        )


@router.post("/skip")
async def skip_setup():
    """Skip initial setup - will have empty library"""
    return {"success": True, "message": "Настройка пропущена. Вы можете добавить хранилища позже."}


@router.post("/initialize")
async def initialize_library(db: aiosqlite.Connection = Depends(get_db)):
    """Reset library to initial state - delete all books, sources and categories"""
    try:
        # Count items before deletion for response
        cursor = await db.execute("SELECT COUNT(*) FROM books")
        books_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM sources")
        sources_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM categories")
        categories_count = (await cursor.fetchone())[0]

        log_audit(
            "library_initialize_start",
            {
                "books_count": books_count,
                "sources_count": sources_count,
                "categories_count": categories_count,
            },
            "setup"
        )

        # Disable foreign keys to avoid self-referencing constraint issues
        await db.execute("PRAGMA foreign_keys = OFF")

        # Delete child categories first (self-referencing parent_id), then all
        await db.execute("DELETE FROM categories WHERE parent_id IS NOT NULL")
        await db.execute("DELETE FROM categories")

        # Delete all books
        await db.execute("DELETE FROM books")

        # Delete all sources
        await db.execute("DELETE FROM sources")

        # Clear FTS index
        await db.execute("DELETE FROM books_fts")

        await db.commit()

        log_audit(
            "library_initialized",
            {
                "books_deleted": books_count,
                "sources_deleted": sources_count,
                "categories_deleted": categories_count,
            },
            "setup"
        )

        return {
            "success": True,
            "message": "Библиотека успешно инициализирована",
            "books_deleted": books_count,
            "sources_deleted": sources_count,
            "categories_deleted": categories_count,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize library: {str(e)}"
        )


@router.get("/audit/status")
async def get_audit_status():
    """Get current audit logging status."""
    return {"audit_enabled": audit_is_enabled()}


@router.post("/restart")
async def restart_server():
    """Restart the server to apply configuration changes."""
    import subprocess
    import sys
    from config import SERVER_HOST, SERVER_PORT
    logger.info("Restarting server by user request...")
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                      "--host", SERVER_HOST, "--port", str(SERVER_PORT), "--reload"])
    import os
    os._exit(0)


@router.post("/audit/toggle")
async def toggle_audit(enable: bool = Query(...)):
    """Enable or disable detailed audit logging and save to config."""
    from services.audit import toggle

    new_state = toggle(enable)

    # Save to config.py - write as string for os.getenv compatibility
    config_path = Path(__file__).parent.parent.parent / "config.py"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace AUDIT_ENABLED line - write as string "true" or "false"
        import re
        str_value = "true" if new_state else "false"
        pattern = r"AUDIT_ENABLED\s*=\s*.*$"
        replacement = f'AUDIT_ENABLED = os.getenv("LIBRARY_AUDIT_ENABLED", "{str_value}").lower() == "true"  # Updated by setup'

        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)
        else:
            content += f'\nAUDIT_ENABLED = os.getenv("LIBRARY_AUDIT_ENABLED", "{str_value}").lower() == "true"  # Added by setup\n'

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

    log_audit(
        "audit_toggled",
        {"enabled": new_state, "previous": not new_state},
        "setup"
    )

    # Restart server to apply new config
    import subprocess
    import sys
    from config import SERVER_PORT
    logger.info("Restarting server to apply AUDIT_ENABLED=%s", new_state)
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                      "--host", "0.0.0.0", "--port", str(SERVER_PORT), "--reload"])
    import os
    os._exit(0)
