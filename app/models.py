from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


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
    source_id: Optional[int] = None
    language: str = "ru"
    source_url: str = ""


class BookCreate(BookBase):
    pass


class BookResponse(BookBase):
    id: int
    category_name: Optional[str] = None
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None


class SourceType(BaseModel):
    dvd: Literal["dvd"]
    hdd: Literal["hdd"]
    ssd: Literal["ssd"]
    nas: Literal["nas"]
    network: Literal["network"]
    cloud: Literal["cloud"]
    local: Literal["local"]


class SourceBase(BaseModel):
    name: str
    type: Literal["dvd", "hdd", "ssd", "nas", "network", "cloud", "local"]
    path: str
    is_active: bool = True
    description: str = ""


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["dvd", "hdd", "ssd", "nas", "network", "cloud", "local"]] = (
        None
    )
    path: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class SourceResponse(SourceBase):
    id: int
    books_count: int = 0
    last_scanned: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DiscoveredDrive(BaseModel):
    drive_letter: str
    label: Optional[str] = None
    type: Literal["removable", "fixed", "network", "cdrom", "unknown"]
    total_size: Optional[int] = None
    free_space: Optional[int] = None


class SearchResponse(BaseModel):
    total: int
    query: str
    books: list


class StatsResponse(BaseModel):
    total_books: int
    total_categories: int
    total_sources: int
    formats: dict
    years: dict


class BookListResponse(BaseModel):
    total: int
    books: list
