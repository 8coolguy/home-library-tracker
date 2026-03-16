"""Database engine, session factory, and initialization."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist."""
    from . import models as _  # noqa: F401 — ensure models are registered

    Base.metadata.create_all(bind=engine)
    _migrate_books_table()


def _migrate_books_table() -> None:
    """Add new columns to an existing books table (idempotent)."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    books_columns = [
        "cover_url TEXT",
        "isbn TEXT",
        "ocr_title TEXT",
        "ocr_author TEXT",
    ]
    scans_columns = [
        "unknown_book_count INTEGER NOT NULL DEFAULT 0",
    ]
    with engine.connect() as conn:
        for col_def in books_columns:
            try:
                conn.execute(text(f"ALTER TABLE books ADD COLUMN {col_def}"))
                conn.commit()
            except OperationalError:
                pass
        for col_def in scans_columns:
            try:
                conn.execute(text(f"ALTER TABLE scans ADD COLUMN {col_def}"))
                conn.commit()
            except OperationalError:
                pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
