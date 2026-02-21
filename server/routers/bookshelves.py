"""Bookshelf CRUD and book query endpoints."""

from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Book, Bookshelf, Scan
from ..schemas import (
    BookOut,
    BookshelfBooksOut,
    BookshelfCreate,
    BookshelfNearest,
    BookshelfOut,
    BookshelfUpdate,
    ScanOut,
)

router = APIRouter(prefix="/bookshelves", tags=["bookshelves"])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.post("", response_model=BookshelfOut, status_code=201)
def create_bookshelf(data: BookshelfCreate, db: Session = Depends(get_db)):
    shelf = Bookshelf(name=data.name, latitude=data.latitude, longitude=data.longitude)
    db.add(shelf)
    db.commit()
    db.refresh(shelf)
    return shelf


@router.get("", response_model=List[BookshelfOut])
def list_bookshelves(db: Session = Depends(get_db)):
    return db.query(Bookshelf).order_by(Bookshelf.name).all()


@router.get("/nearest", response_model=BookshelfNearest)
def nearest_bookshelf(
    latitude: float = Query(...),
    longitude: float = Query(...),
    db: Session = Depends(get_db),
):
    shelves = (
        db.query(Bookshelf)
        .filter(Bookshelf.latitude.isnot(None), Bookshelf.longitude.isnot(None))
        .all()
    )
    if not shelves:
        raise HTTPException(404, "No bookshelves with location data")

    best = min(
        shelves, key=lambda s: _haversine_km(latitude, longitude, s.latitude, s.longitude)
    )
    dist = _haversine_km(latitude, longitude, best.latitude, best.longitude)

    return BookshelfNearest(
        id=best.id,
        name=best.name,
        latitude=best.latitude,
        longitude=best.longitude,
        created_at=best.created_at,
        distance_km=round(dist, 3),
    )


@router.get("/{bookshelf_id}", response_model=BookshelfOut)
def get_bookshelf(bookshelf_id: int, db: Session = Depends(get_db)):
    shelf = db.get(Bookshelf, bookshelf_id)
    if not shelf:
        raise HTTPException(404, "Bookshelf not found")
    return shelf


@router.put("/{bookshelf_id}", response_model=BookshelfOut)
def update_bookshelf(
    bookshelf_id: int, data: BookshelfUpdate, db: Session = Depends(get_db)
):
    shelf = db.get(Bookshelf, bookshelf_id)
    if not shelf:
        raise HTTPException(404, "Bookshelf not found")
    if data.name is not None:
        shelf.name = data.name
    if data.latitude is not None:
        shelf.latitude = data.latitude
    if data.longitude is not None:
        shelf.longitude = data.longitude
    db.commit()
    db.refresh(shelf)
    return shelf


@router.delete("/{bookshelf_id}", status_code=204)
def delete_bookshelf(bookshelf_id: int, db: Session = Depends(get_db)):
    shelf = db.get(Bookshelf, bookshelf_id)
    if not shelf:
        raise HTTPException(404, "Bookshelf not found")
    db.delete(shelf)
    db.commit()


@router.get("/{bookshelf_id}/books", response_model=BookshelfBooksOut)
def get_bookshelf_books(bookshelf_id: int, db: Session = Depends(get_db)):
    shelf = db.get(Bookshelf, bookshelf_id)
    if not shelf:
        raise HTTPException(404, "Bookshelf not found")

    # Latest completed scan for this shelf
    latest_scan = (
        db.query(Scan)
        .filter(Scan.bookshelf_id == bookshelf_id, Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .first()
    )

    if latest_scan is None:
        return BookshelfBooksOut(
            bookshelf_id=shelf.id,
            bookshelf_name=shelf.name,
            current=[],
            historical=[],
        )

    # Current books = books from latest scan
    current_books = db.query(Book).filter(Book.scan_id == latest_scan.id).all()
    current_set = {(b.title or "", b.author or "") for b in current_books}

    # Historical = distinct books from older completed scans NOT in current
    older_scan_ids = [
        s.id
        for s in db.query(Scan.id)
        .filter(
            Scan.bookshelf_id == bookshelf_id,
            Scan.status == "completed",
            Scan.id != latest_scan.id,
        )
        .all()
    ]

    historical = []
    if older_scan_ids:
        older_books = db.query(Book).filter(Book.scan_id.in_(older_scan_ids)).all()
        seen = set()
        for b in older_books:
            key = (b.title or "", b.author or "")
            if key not in current_set and key not in seen:
                seen.add(key)
                historical.append(BookOut(title=b.title, author=b.author))

    return BookshelfBooksOut(
        bookshelf_id=shelf.id,
        bookshelf_name=shelf.name,
        current=[BookOut(title=b.title, author=b.author) for b in current_books],
        historical=historical,
    )


@router.get("/{bookshelf_id}/scans", response_model=List[ScanOut])
def list_shelf_scans(bookshelf_id: int, db: Session = Depends(get_db)):
    shelf = db.get(Bookshelf, bookshelf_id)
    if not shelf:
        raise HTTPException(404, "Bookshelf not found")
    return (
        db.query(Scan)
        .filter(Scan.bookshelf_id == bookshelf_id)
        .order_by(Scan.created_at.desc())
        .all()
    )
