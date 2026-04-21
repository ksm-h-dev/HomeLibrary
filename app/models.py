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
    relative_path: str = ""
    cover_path: str = ""
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    language: str = "ru"
    source_url: str = ""


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    pages: Optional[int] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    language: Optional[str] = None


class BookResponse(BookBase):
    id: int
    category_name: Optional[str] = None
    source_name: Optional[str] = None
    is_available: bool = True

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
    volume_label: str = ""
    catalog_id: str = ""
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
    volume_label: Optional[str] = None
    catalog_id: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    availability_status: Optional[Literal["available", "unavailable", "archived"]] = (
        None
    )


class SourceResponse(SourceBase):
    id: int
    books_count: int = 0
    last_scanned: Optional[datetime] = None
    created_at: Optional[datetime] = None
    availability_status: Literal["available", "unavailable", "archived"] = "available"

    class Config:
        from_attributes = True


class CatalogInfo(BaseModel):
    id: str
    name: str = ""
    version: str = "1.0"
    created: str = ""


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


class SetupStatus(BaseModel):
    is_first_run: bool
    default_source_path: str
    has_books: bool
    total_books: int
    total_sources: int
    needs_setup: bool


class FolderSelectRequest(BaseModel):
    drive_letter: str = ""


class FolderSelectResponse(BaseModel):
    selected_path: str
    success: bool
    message: str


class InitialScanResponse(BaseModel):
    success: bool
    source_id: int
    scanned: int
    imported: int
    updated: int
    skipped: int
    message: str


class SavePathRequest(BaseModel):
    path: str


class InitializeLibraryResponse(BaseModel):
    success: bool
    message: str
    books_deleted: int
    sources_deleted: int
