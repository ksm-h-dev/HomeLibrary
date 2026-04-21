from fastapi import FastAPI
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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/about")
async def about_page():
    return FileResponse(os.path.join(WEB_DIR, "about.html"))


@app.get("/setup")
async def setup_page():
    return FileResponse(os.path.join(WEB_DIR, "setup.html"))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join(WEB_DIR, "favicon.ico"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
