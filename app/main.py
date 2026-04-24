from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import init_db, get_all_sources
from app.routers import books, search, sources
from app.routers import welcome
from config import SERVER_HOST, SERVER_PORT, DEFAULT_SOURCE_PATH, DATABASE_URL
import aiosqlite

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
    """Check if we need to auto-import from DEFAULT_SOURCE_PATH"""
    db = await aiosqlite.connect(DATABASE_URL)
    db.row_factory = aiosqlite.Row
    try:
        sources = await get_all_sources(db)
        if (
            len(sources) == 0
            and DEFAULT_SOURCE_PATH
            and os.path.exists(DEFAULT_SOURCE_PATH)
        ):
            print(f"Auto-importing from DEFAULT_SOURCE_PATH: {DEFAULT_SOURCE_PATH}")
            from services.importer import import_from_source

            result = await import_from_source(None, DEFAULT_SOURCE_PATH)
            print(f"Auto-import complete: {result}")
    finally:
        await db.close()


@app.on_event("startup")
async def startup():
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
    
    print(f"Cover request: {decoded_path}")
    print(f"  book_dir: {book_dir}")
    print(f"  book_stem: {book_stem}")
    
    cover_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']
    
    if os.path.isdir(book_dir):
        files = os.listdir(book_dir)
        print(f"  files in dir: {files}")
        
        # First, try exact/substring match
        for f in files:
            ext = f.lower().split('.')[-1]
            if ext not in cover_extensions:
                continue
            
            candidate_stem = os.path.splitext(f)[0]
            if book_stem in candidate_stem or candidate_stem in book_stem:
                full_path = os.path.join(book_dir, f)
                print(f"  Found cover (match): {full_path}")
                return FileResponse(full_path)
        
        # Fallback: return first image file found
        for f in files:
            ext = f.lower().split('.')[-1]
            if ext in cover_extensions:
                full_path = os.path.join(book_dir, f)
                print(f"  Found cover (fallback): {full_path}")
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
    """Serve static files from web directory."""
    file_path = os.path.join(WEB_DIR, filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
