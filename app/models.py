from pydantic import BaseModel
from typing import Optional


class BookBase(BaseModel):
    title: str
    author: str = ""
    publisher: str = ""
    isbn: str = ""
    year: Optional[int] = None
    pages: Optional[int] = None
    format: str = ""
    file_size: int = 0
    description: str = ""
    file_path: str = ""
    cover_path: str = ""
    category_id: Optional[int] = None
    language: str = "ru"
    source_url: str = ""


class BookCreate(BookBase):
    pass


class BookResponse(BookBase):
    id: int
    category_name: Optional[str] = None

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None


class SearchResponse(BaseModel):
    total: int
    query: str
    books: list


class StatsResponse(BaseModel):
    total_books: int
    total_categories: int
    formats: dict
    years: dict


class BookListResponse(BaseModel):
    total: int
    books: list
