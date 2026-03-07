"""Scan upload and polling endpoints."""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import Bookshelf, Scan
from ..schemas import BookOut, ScanCreated, ScanOut
from ..worker import enqueue_scan

router = APIRouter(prefix="/scans", tags=["scans"])


def _find_nearest_shelf(
    db: Session, lat: float, lng: float
) -> Optional[Bookshelf]:
    """Return the nearest bookshelf, or None."""
    shelves = (
        db.query(Bookshelf)
        .filter(Bookshelf.latitude.isnot(None), Bookshelf.longitude.isnot(None))
        .all()
    )
    if not shelves:
        return None
    return min(
        shelves,
        key=lambda s: (s.latitude - lat) ** 2 + (s.longitude - lng) ** 2,
    )


@router.post("", response_model=ScanCreated, status_code=202)
def upload_scan(
    image: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    bookshelf_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    # Validate bookshelf if provided
    shelf_name = None
    if bookshelf_id is not None:
        shelf = db.get(Bookshelf, bookshelf_id)
        if not shelf:
            raise HTTPException(404, "Bookshelf not found")
        shelf_name = shelf.name

    # Auto-suggest nearest shelf if no bookshelf_id but has GPS
    if bookshelf_id is None and latitude is not None and longitude is not None:
        nearest = _find_nearest_shelf(db, latitude, longitude)
        if nearest:
            bookshelf_id = nearest.id
            shelf_name = nearest.name

    # Save image file
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    timestamp = int(time.time() * 1000)
    ext = os.path.splitext(image.filename or "photo.jpg")[1] or ".jpg"
    filename = f"scan_{timestamp}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(image.file.read())

    # Create scan record
    scan = Scan(
        bookshelf_id=bookshelf_id,
        image_filename=filename,
        latitude=latitude,
        longitude=longitude,
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    enqueue_scan(scan.id)

    return ScanCreated(
        scan_id=scan.id,
        status=scan.status,
        bookshelf_id=bookshelf_id,
        bookshelf_name=shelf_name,
    )


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")

    books = None
    if scan.status == "completed":
        books = [BookOut.model_validate(b) for b in scan.books]

    return ScanOut(
        id=scan.id,
        bookshelf_id=scan.bookshelf_id,
        status=scan.status,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        books=books,
    )
