"""
Модуль поиска метаданных по идентификаторам книг (ISBN, DOI, ISSN) через внешние API.

Архитектура:
  normalize_code() → detect_code_type() → lookup_code() → lookup_isbn|lookup_doi|lookup_issn()

Поддерживаемые идентификаторы:
  - ISBN-10 (9 цифр + контрольная цифра/X)
  - ISBN-13 (978/979 + 10 цифр)
  - DOI (10.xxxx/xxxx)
  - ISSN (xxxx-xxxx)
"""

import re
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Константы внешних API
OPENLIBRARY_URL = "https://openlibrary.org"      # Открытая книжная база (ISBN)
CROSSREF_URL = "https://api.crossref.org"         # CrossRef для DOI научных работ
ISSN_PORTAL_URL = "https://portal.issn.org/api"   # ISSN Portal для сериальных изданий


def normalize_code(raw: str) -> str:
    """
    Приводит введённый код к нормализованному виду (без префиксов ISBN/DOI/ISSN, пробелов и дефисов).

    Примеры:
      "ISBN 978-5-12345-678-9" -> "9785123456789"
      "DOI 10.1000/xyz"        -> "10.1000/xyz"
      "ISSN 1234-5678"         -> "12345678"
    """
    code = raw.strip()
    # Удаляем префиксы ISBN:, DOI:, ISSN: (регистронезависимо)
    code = re.sub(r'^(ISBN[-:]?\s*|DOI[-:]?\s*|ISSN[-:]?\s*)', '', code, flags=re.IGNORECASE)
    # Удаляем все дефисы и пробелы
    code = re.sub(r'[-\s]', '', code)
    return code


def detect_code_type(normalized: str) -> str:
    """
    Определяет тип идентификатора по регулярному выражению.

    Возвращает: 'isbn13', 'isbn10', 'issn', 'doi', или 'unknown'
    """
    # ISBN-13: 978 или 979 + 10 цифр (всего 13)
    if re.fullmatch(r'97[89]\d{10}', normalized):
        return 'isbn13'
    # ISBN-10: 9 цифр + контрольный символ (цифра или X)
    if re.fullmatch(r'\d{9}[\dX]', normalized):
        return 'isbn10'
    # ISSN: 8 цифр (после нормализации дефисов)
    if re.fullmatch(r'\d{7}[\dX]', normalized):
        return 'issn'
    # DOI: 10.xxxx/... (префикс издателя + суффикс)
    if re.fullmatch(r'10\.\d{4,}/.+', normalized):
        return 'doi'
    return 'unknown'


async def lookup_isbn(normalized: str) -> dict:
    """
    Запрашивает OpenLibrary API по ISBN.

    API: GET https://openlibrary.org/api/books?bibkeys=ISBN:xxxxx&jscmd=data&format=json
    Извлекает: title, author(s), publisher, publish_date, pages, subjects, cover
    """
    headers = {"User-Agent": "HomeLibrary/1.0 (admin@homelibrary.local)"}
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        resp = await client.get(
            f"{OPENLIBRARY_URL}/api/books",
            params={"bibkeys": f"ISBN:{normalized}", "jscmd": "data", "format": "json"},
        )
        # API возвращает 200 даже при ненайденном ISBN — пустой объект
        if resp.status_code != 200:
            return {"error": f"OpenLibrary returned {resp.status_code}"}

        data = resp.json()
        key = f"ISBN:{normalized}"
        info = data.get(key)
        if not info:
            return {"error": "Not found in OpenLibrary", "raw": data}

        # Маппинг полей OpenLibrary → наш формат
        result = {"source": "openlibrary", "raw": info}
        if "title" in info:
            result["title"] = info["title"]
        if "authors" in info:
            # authors — массив объектов {"name": "...", "url": "..."}
            result["author"] = ", ".join(a.get("name", "") for a in info["authors"])
        if "publishers" in info:
            pub = info["publishers"][0]
            result["publisher"] = pub.get("name", "")
        if "publish_date" in info:
            # publish_date может быть "2004" или "2004-01-15"
            m = re.search(r'\d{4}', str(info["publish_date"]))
            if m:
                result["year"] = int(m.group())
        if "number_of_pages" in info:
            result["pages"] = info["number_of_pages"]
        if "subjects" in info:
            # Берём первые 10 subject'ов как описание
            result["description"] = "; ".join(
                s.get("name", "") for s in info["subjects"][:10]
            )
        if "cover" in info:
            # Приоритет: large > medium > small
            result["cover_url"] = info["cover"].get("large") or info["cover"].get("medium") or info["cover"].get("small")
        result["source_url"] = f"https://openlibrary.org/isbn/{normalized}"
        result["isbn"] = normalized
        return result


async def lookup_doi(normalized: str) -> dict:
    """
    Запрашивает CrossRef API по DOI.

    API: GET https://api.crossref.org/works/{doi}
    Извлекает: title, author(s), publisher, published-print, page, doi
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{CROSSREF_URL}/works/{normalized}")
        if resp.status_code != 200:
            return {"error": f"CrossRef returned {resp.status_code}"}

        data = resp.json()
        # Основные данные в message
        message = data.get("message", {})
        result = {"source": "crossref", "raw": message}

        if "title" in message:
            titles = message["title"]
            result["title"] = titles[0] if titles else ""
        if "author" in message:
            # author — массив объектов с given/family
            authors = []
            for a in message["author"]:
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append(f"{given} {family}".strip())
            result["author"] = "; ".join(authors)
        if "publisher" in message:
            result["publisher"] = message["publisher"]
        # Дата: published-print (print) или issued (online first)
        if "published-print" in message:
            parts = message["published-print"].get("date-parts", [])
            if parts and parts[0]:
                result["year"] = parts[0][0]
        elif "issued" in message:
            parts = message["issued"].get("date-parts", [])
            if parts and parts[0]:
                result["year"] = parts[0][0]
        if "page" in message:
            # page может быть "123-145" — берём последнее число
            try:
                pages_str = message["page"]
                pages = re.findall(r'\d+', pages_str)
                if pages:
                    result["pages"] = int(pages[-1])
            except (ValueError, TypeError):
                pass
        if "doi" in message:
            result["doi"] = message["doi"]
            result["source_url"] = f"https://doi.org/{message['doi']}"
        return result


async def lookup_issn(normalized: str) -> dict:
    """
    Запрашивает ISSN Portal по ISSN.

    API: GET https://portal.issn.org/api/issn?value={issn}
    Возвращает название сериального издания и издателя в JSON-LD формате.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{ISSN_PORTAL_URL}/issn", params={"value": normalized})
        if resp.status_code != 200:
            return {"error": f"ISSN portal returned {resp.status_code}"}

        data = resp.json()
        result = {"source": "issn", "raw": data}

        # JSON-LD: @graph[0] — основная запись
        record = (data.get("@graph") or [{}])[0]
        if record.get("identifiedBy"):
            for ident in record["identifiedBy"]:
                if ident.get("value") == normalized:
                    result["title"] = record.get("name", "")
                    result["publisher"] = record.get("publisher", "")
                    break
        return result


async def lookup_code(code: str) -> dict:
    """
    Главная точка входа — принимает сырой код, определяет тип и вызывает нужный API.

    Поток:
      1. normalize_code() — очистка от префиксов/разделителей
      2. detect_code_type() — определение типа (isbn13/isbn10/doi/issn)
      3. lookup_isbn/lookup_doi/lookup_issn — вызов соответствующего API
      4. Возвращает объединённый словарь с detected_type, title, author и т.д.
    """
    normalized = normalize_code(code)
    if not normalized:
        return {"error": "Empty code after normalization"}

    code_type = detect_code_type(normalized)

    if code_type == 'unknown':
        return {"error": "Unable to determine code type", "detected_type": code_type}

    if code_type in ('isbn13', 'isbn10'):
        result = await lookup_isbn(normalized)
        result["detected_type"] = code_type
        return result
    elif code_type == 'doi':
        result = await lookup_doi(normalized)
        result["detected_type"] = "doi"
        return result
    elif code_type == 'issn':
        result = await lookup_issn(normalized)
        result["detected_type"] = "issn"
        return result

    return {"error": "Unsupported code type", "detected_type": code_type}
