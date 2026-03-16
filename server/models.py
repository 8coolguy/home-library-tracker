"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Bookshelf(Base):
    __tablename__ = "bookshelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[List[Scan]] = relationship(
        back_populates="bookshelf", cascade="all, delete-orphan"
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    bookshelf_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bookshelves.id"), nullable=True
    )
    image_filename: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unknown_book_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    bookshelf: Mapped[Optional[Bookshelf]] = relationship(back_populates="scans")
    books: Mapped[List[Book]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    isbn: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ocr_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ocr_author: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scan: Mapped[Scan] = relationship(back_populates="books")
