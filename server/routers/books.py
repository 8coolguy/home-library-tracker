"""Book search endpoint."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Book, Scan
from ..schemas import BookAdminOut, BookSearchResult, BookUpdate

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search", response_model=List[BookSearchResult])
def search_books(q: str, db: Session = Depends(get_db)):
    """Search for a book by title or author across all bookshelves.

    Returns all matching books from completed scans, including which
    bookshelf each copy was found on.
    """
    if not q or not q.strip():
        raise HTTPException(400, "Query parameter 'q' must not be empty")

    term = f"%{q.strip()}%"
    matches = (
        db.query(Book)
        .join(Book.scan)
        .filter(
            Scan.status == "completed",
            or_(
                func.lower(Book.title).like(func.lower(term)),
                func.lower(Book.author).like(func.lower(term)),
                func.lower(Book.ocr_title).like(func.lower(term)),
                func.lower(Book.ocr_author).like(func.lower(term)),
            ),
        )
        .all()
    )

    results = []
    for book in matches:
        shelf = book.scan.bookshelf
        results.append(
            BookSearchResult(
                id=book.id,
                title=book.title,
                author=book.author,
                cover_url=book.cover_url,
                isbn=book.isbn,
                bookshelf_id=shelf.id if shelf else None,
                bookshelf_name=shelf.name if shelf else None,
            )
        )
    return results


@router.patch("/{book_id}", response_model=BookAdminOut)
def update_book(book_id: int, body: BookUpdate, db: Session = Depends(get_db)):
    """Manually correct a book's metadata."""
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(book, field, value)

    db.commit()
    db.refresh(book)
    return BookAdminOut.model_validate(book)
