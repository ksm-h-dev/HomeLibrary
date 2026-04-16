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

    # Needs setup if first run OR if we have default path but no sources
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
            raise HTTPException(status_code=400, detail="Path does not exist")

        # Update config.py file
        config_path = Path(__file__).parent.parent.parent / "config.py"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Escape backslashes for regex replacement
            escaped_path = path.replace("\\", "\\\\")

            # Replace DEFAULT_SOURCE_PATH line
            import re

            pattern = r"DEFAULT_SOURCE_PATH\s*=\s*os\.getenv\([^)]+\)"
            replacement = f'DEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", r"{escaped_path}")'

            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
            else:
                # Add if not exists
                content = content.replace(
                    "# First run configuration",
                    f'# First run configuration\nDEFAULT_SOURCE_PATH = os.getenv("LIBRARY_DEFAULT_SOURCE", r"{escaped_path}")  # Added by setup',
                )

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)

        return {"success": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan", response_model=InitialScanResponse)
async def perform_initial_scan(db: aiosqlite.Connection = Depends(get_db)):
    """Perform initial scan of DEFAULT_SOURCE_PATH"""
    from services.importer import import_from_source

    if not DEFAULT_SOURCE_PATH:
        raise HTTPException(
            status_code=400, detail="DEFAULT_SOURCE_PATH not configured"
        )

    if not os.path.exists(DEFAULT_SOURCE_PATH):
        raise HTTPException(
            status_code=400, detail=f"Path does not exist: {DEFAULT_SOURCE_PATH}"
        )

    try:
        # Import with source_id=None to create new source
        result = await import_from_source(None, DEFAULT_SOURCE_PATH)

        return InitialScanResponse(
            success=True,
            source_id=result.get("source_id", 0),
            scanned=result.get("scanned", 0),
            imported=result.get("imported", 0),
            updated=result.get("updated", 0),
            skipped=result.get("skipped", 0),
            message=f"Scan completed: {result.get('imported', 0)} new books imported",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skip")
async def skip_setup():
    """Skip initial setup - will have empty library"""
    return {"success": True, "message": "Setup skipped. You can add sources later."}
