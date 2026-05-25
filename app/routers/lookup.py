"""
Роутер для поиска метаданных по идентификаторам книг (ISBN, DOI, ISSN, UDK, BBK).

Endpoints:
  POST /api/lookup            — поиск во внешних API (OpenLibrary, CrossRef, ISSN Portal)
  GET  /api/lookup/by-classification — поиск в локальной БД по коду
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Any
import aiosqlite
import logging

from app.database import get_db
from services.lookup import lookup_code
from services.audit import log_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


# --- Pydantic модели запроса/ответа ---

class CodeLookupRequest(BaseModel):
    """Запрос на поиск кода во внешних API."""
    code: str  # Сырой код: "ISBN 978-5-12345-678-9", "DOI 10.1000/xyz" и т.д.


class CodeLookupResponse(BaseModel):
    """
    Структурированный ответ после поиска во внешнем API.

    Поля:
      detected_type — распознанный тип (isbn13/isbn10/doi/issn)
      title, author, publisher — основные метаданные
      year, pages — числовые метаданные
      isbn — нормализованный ISBN (может отличаться от запроса)
      description — краткое описание / темы
      cover_url — URL обложки (OpenLibrary)
      source_url — ссылка на страницу книги в источнике
      source — название источника ("openlibrary", "crossref", "issn")
      raw — сырой ответ API для сохранения в .lookup.json
      error — сообщение об ошибке (если поиск не удался)
    """
    detected_type: str
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    pages: Optional[int] = None
    isbn: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    source_url: Optional[str] = None
    error: Optional[str] = None
    raw: Optional[Any] = None
    source: Optional[str] = None


# --- Endpoints ---

@router.post("", response_model=CodeLookupResponse)
async def lookup(request: CodeLookupRequest):
    """
    Поиск идентификатора во внешних API.

    - Принимает код в любом формате (с префиксом ISBN:, DOI:, без него, с дефисами)
    - Серверная часть (services/lookup.py):
      1. normalize_code() — очищает код
      2. detect_code_type() — определяет тип
      3. lookup_isbn/lookup_doi/lookup_issn — запрашивает соответствующий API
    - Возвращает структурированный ответ для заполнения формы редактирования
    - «Сырой» ответ API сохраняется в raw для последующей записи в .lookup.json
    """
    result = await lookup_code(request.code)

    # Логируем факт поиска в аудит
    log_audit(
        "code_lookup",
        {"code": request.code, "detected_type": result.get("detected_type", "unknown"), "found": "error" not in result},
        "api"
    )

    return CodeLookupResponse(
        detected_type=result.get("detected_type", "unknown"),
        title=result.get("title"),
        author=result.get("author"),
        publisher=result.get("publisher"),
        year=result.get("year"),
        pages=result.get("pages"),
        isbn=result.get("isbn"),
        description=result.get("description"),
        cover_url=result.get("cover_url"),
        source_url=result.get("source_url"),
        error=result.get("error"),
        raw=result.get("raw"),
        source=result.get("source"),
    )


@router.get("/by-classification")
async def books_by_classification(
    code: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Поиск книг в локальной базе по классификационному коду (УДК, ББК, LCC и т.д.).

    - Поиск по полю isbn (в котором могут храниться не только ISBN, но и УДК/ББК)
    - Использует LIKE %code% для частичного совпадения
    - Возвращает до 50 результатов
    """
    pattern = f"%{code}%"
    cursor = await db.execute(
        "SELECT id, title, author, isbn FROM books WHERE isbn LIKE ? LIMIT 50",
        (pattern,),
    )
    rows = await cursor.fetchall()
    return {"code": code, "total": len(rows), "books": [dict(r) for r in rows]}
