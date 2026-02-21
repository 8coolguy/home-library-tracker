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
    created_at: datetime
    completed_at: Optional[datetime]
    books: Optional[List[BookOut]] = None

    class Config:
        from_attributes = True


class ScanCreated(BaseModel):
    scan_id: int
    status: str
    bookshelf_id: Optional[int]
    bookshelf_name: Optional[str]
