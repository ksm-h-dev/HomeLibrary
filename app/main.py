from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import init_db
from app.routers import books, search, sources
from config import SERVER_HOST, SERVER_PORT

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

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/")
async def root():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
