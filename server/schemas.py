"""Pydantic schemas for API request/response bodies."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# --- Bookshelves ---


class BookshelfCreate(BaseModel):
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BookshelfUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BookshelfOut(BaseModel):
    id: int
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class BookshelfNearest(BookshelfOut):
    distance_km: float


# --- Books ---


class BookOut(BaseModel):
    title: Optional[str]
    author: Optional[str]
    cover_url: Optional[str] = None
    isbn: Optional[str] = None
    ocr_title: Optional[str] = None
    ocr_author: Optional[str] = None

    class Config:
        from_attributes = True


class BookAdminOut(BaseModel):
    id: int
    scan_id: int
    title: Optional[str]
    author: Optional[str]
    cover_url: Optional[str] = None
    isbn: Optional[str] = None
    ocr_title: Optional[str] = None
    ocr_author: Optional[str] = None

    class Config:
        from_attributes = True


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    cover_url: Optional[str] = None
    isbn: Optional[str] = None


class BookSearchResult(BaseModel):
    id: int
    title: Optional[str]
    author: Optional[str]
    cover_url: Optional[str] = None
    isbn: Optional[str] = None
    bookshelf_id: Optional[int]
    bookshelf_name: Optional[str]

    class Config:
        from_attributes = True


class BookshelfBooksOut(BaseModel):
    bookshelf_id: int
    bookshelf_name: str
    current: List[BookOut]
    historical: List[BookOut]


# --- Scans ---


class ScanOut(BaseModel):
    id: int
    bookshelf_id: Optional[int]
    status: str
    error_message: Optional[str]
    unknown_book_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime]
    image_filename: Optional[str] = None
    books: Optional[List[BookAdminOut]] = None

    class Config:
        from_attributes = True


class ScanListItem(BaseModel):
    id: int
    bookshelf_id: Optional[int]
    bookshelf_name: Optional[str]
    image_filename: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    book_count: int
    unknown_book_count: int = 0


class ScanDeletePreview(BaseModel):
    scan_id: int
    total_books: int
    unique_books: int
    shared_books: int


class ScanCreated(BaseModel):
    scan_id: int
    status: str
    bookshelf_id: Optional[int]
    bookshelf_name: Optional[str]
