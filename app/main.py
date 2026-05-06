from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

from app.database import init_db, get_all_sources
from app.routers import books, search, sources
from app.routers import welcome
from config import SERVER_HOST, SERVER_PORT, DEFAULT_SOURCE_PATH, DATABASE_URL
import aiosqlite

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.log")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Test log writing
logger.info("Logging system initialized")

app = FastAPI(
    title="Домашний библиотекарь",
    description="Веб-приложение для управления электронной библиотекой",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(search.router)
app.include_router(sources.router)
app.include_router(welcome.router)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


async def check_initial_setup():
    db = await aiosqlite.connect(DATABASE_URL)
    db.row_factory = aiosqlite.Row
    try:
        sources = await get_all_sources(db)
        if (
            len(sources) == 0
            and DEFAULT_SOURCE_PATH
            and os.path.exists(DEFAULT_SOURCE_PATH)
        ):
            logger.info("Auto-import from %s", DEFAULT_SOURCE_PATH)
            from services.importer import import_from_source
            result = await import_from_source(None, DEFAULT_SOURCE_PATH)
            logger.info("Auto-import complete: %s", result)
            from services.audit import log_audit
            log_audit(
                "auto_import_complete",
                {
                    "path": DEFAULT_SOURCE_PATH,
                    "source_id": result.get("source_id", 0),
                    "scanned": result.get("scanned", 0),
                    "imported": result.get("imported", 0),
                    "confirmed": result.get("confirmed", 0),
                    "missing": result.get("missing", 0)
                },
                "startup"
            )
    finally:
        await db.close()


@app.on_event("startup")
async def startup():
    # Ensure log file exists
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('')
    await init_db()
    await check_initial_setup()


@app.get("/")
async def root():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/api/cover")
async def get_cover(path: str):
    import urllib.parse
    decoded_path = urllib.parse.unquote(path)
    book_dir = os.path.dirname(decoded_path)
    book_stem = os.path.splitext(os.path.basename(decoded_path))[0]
    
    logger.info("Cover request: %s", decoded_path)
    cover_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']
    
    if os.path.isdir(book_dir):
        files = os.listdir(book_dir)
        for f in files:
            ext = f.lower().split('.')[-1]
            if ext not in cover_extensions:
                continue
            candidate_stem = os.path.splitext(f)[0]
            if book_stem in candidate_stem or candidate_stem in book_stem:
                full_path = os.path.join(book_dir, f)
                logger.debug("Found cover (match): %s", full_path)
                return FileResponse(full_path)
        for f in files:
            ext = f.lower().split('.')[-1]
            if ext in cover_extensions:
                full_path = os.path.join(book_dir, f)
                logger.debug("Found cover (fallback): %s", full_path)
                return FileResponse(full_path)
    raise HTTPException(status_code=404, detail=f"Cover not found for {book_stem}")


@app.get("/about")
async def about_page():
    return FileResponse(os.path.join(WEB_DIR, "about.html"))


@app.get("/setup")
async def setup_page():
    return FileResponse(os.path.join(WEB_DIR, "setup.html"))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join(WEB_DIR, "favicon.ico"))


@app.get("/{filename}")
async def static_files(filename: str):
    file_path = os.path.join(WEB_DIR, filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.log")

@app.get("/api/audit-log")
async def get_audit_log(lines: int = 500):
    """Get audit log content."""
    try:
        if not os.path.exists(AUDIT_LOG_FILE):
            return PlainTextResponse("Audit log file not found. Enable audit logging in Tools section.")
        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            content = f.readlines()
        last_lines = content[-lines:] if len(content) > lines else content
        return PlainTextResponse(''.join(last_lines))
    except Exception as e:
        return PlainTextResponse(f"Error: {str(e)}")


@app.get("/api/logs")
async def get_logs(lines: int = 200):
    try:
        if not os.path.exists(LOG_FILE):
            return PlainTextResponse("Лог-файл не найден")
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            content = f.readlines()
        last_lines = content[-lines:] if len(content) > lines else content
        return PlainTextResponse(''.join(last_lines))
    except Exception as e:
        return PlainTextResponse(f"Ошибка: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
