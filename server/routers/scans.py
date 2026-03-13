"""Scan upload and polling endpoints."""

from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, ExifTags
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import Book, Bookshelf, Scan
from ..schemas import BookAdminOut, ScanCreated, ScanDeletePreview, ScanListItem, ScanOut
from ..worker import enqueue_scan
from .bookshelves import _haversine_km

GPS_MATCH_RADIUS_M = 100

router = APIRouter(prefix="/scans", tags=["scans"])


def _extract_gps(image_bytes: bytes) -> Optional[Tuple[float, float]]:
    """Return (latitude, longitude) from image EXIF, or None."""
    try:
        import io
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif()
        if not exif:
            return None

        tag_map = {v: k for k, v in ExifTags.TAGS.items()}
        gps_tag = tag_map.get("GPSInfo")
        gps_data = exif.get(gps_tag) if gps_tag else None
        if not gps_data:
            return None

        gps_tags = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_data.items()}

        def to_decimal(dms, ref) -> float:
            d, m, s = dms
            decimal = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal

        lat = to_decimal(gps_tags["GPSLatitude"], gps_tags["GPSLatitudeRef"])
        lng = to_decimal(gps_tags["GPSLongitude"], gps_tags["GPSLongitudeRef"])
        return lat, lng
    except Exception:
        return None


def _find_or_create_shelf(
    db: Session, lat: float, lng: float
) -> Bookshelf:
    """Return the nearest bookshelf within GPS_MATCH_RADIUS_M, or create a new one."""
    shelves = (
        db.query(Bookshelf)
        .filter(Bookshelf.latitude.isnot(None), Bookshelf.longitude.isnot(None))
        .all()
    )
    if shelves:
        nearest = min(shelves, key=lambda s: _haversine_km(lat, lng, s.latitude, s.longitude))
        dist_m = _haversine_km(lat, lng, nearest.latitude, nearest.longitude) * 1000
        if dist_m <= GPS_MATCH_RADIUS_M:
            return nearest

    # No shelf within radius — create one
    count = db.query(Bookshelf).count()
    shelf = Bookshelf(
        name=f"Shelf {count + 1}",
        latitude=lat,
        longitude=lng,
    )
    db.add(shelf)
    db.commit()
    db.refresh(shelf)
    return shelf


@router.get("", response_model=List[ScanListItem])
def list_scans(bookshelf_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Scan)
    if bookshelf_id is not None:
        q = q.filter(Scan.bookshelf_id == bookshelf_id)
    scans = q.order_by(Scan.created_at.desc()).all()
    result = []
    for scan in scans:
        shelf = scan.bookshelf
        result.append(
            ScanListItem(
                id=scan.id,
                bookshelf_id=scan.bookshelf_id,
                bookshelf_name=shelf.name if shelf else None,
                image_filename=scan.image_filename,
                status=scan.status,
                created_at=scan.created_at,
                completed_at=scan.completed_at,
                book_count=len(scan.books),
            )
        )
    return result


@router.post("", response_model=ScanCreated, status_code=202)
def upload_scan(
    image: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    bookshelf_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    # Read image bytes once so we can inspect EXIF and then save
    image_bytes = image.file.read()

    # Fill in GPS from EXIF if not provided
    if latitude is None or longitude is None:
        coords = _extract_gps(image_bytes)
        if coords:
            latitude, longitude = coords

    # Validate bookshelf if explicitly provided
    shelf_name = None
    if bookshelf_id is not None:
        shelf = db.get(Bookshelf, bookshelf_id)
        if not shelf:
            raise HTTPException(404, "Bookshelf not found")
        shelf_name = shelf.name

    # Auto-assign or create shelf from GPS when no bookshelf_id given
    if bookshelf_id is None and latitude is not None and longitude is not None:
        shelf = _find_or_create_shelf(db, latitude, longitude)
        bookshelf_id = shelf.id
        shelf_name = shelf.name

    # Save image file
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    timestamp = int(time.time() * 1000)
    ext = os.path.splitext(image.filename or "photo.jpg")[1] or ".jpg"
    filename = f"scan_{timestamp}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(image_bytes)

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
        books = [BookAdminOut.model_validate(b) for b in scan.books]

    return ScanOut(
        id=scan.id,
        bookshelf_id=scan.bookshelf_id,
        status=scan.status,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        image_filename=scan.image_filename,
        books=books,
    )


@router.get("/{scan_id}/delete-preview", response_model=ScanDeletePreview)
def delete_scan_preview(scan_id: int, db: Session = Depends(get_db)):
    """Return a preview of what will be deleted before committing."""
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")

    total = len(scan.books)
    # A book is "shared" if a book with the same title+author exists in another scan
    shared = 0
    for book in scan.books:
        duplicate = (
            db.query(Book)
            .filter(
                Book.scan_id != scan_id,
                Book.title == book.title,
                Book.author == book.author,
                Book.title.isnot(None),
            )
            .first()
        )
        if duplicate:
            shared += 1

    return ScanDeletePreview(
        scan_id=scan_id,
        total_books=total,
        unique_books=total - shared,
        shared_books=shared,
    )


@router.delete("/{scan_id}", status_code=204)
def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """Delete a scan and all its books. The image file is also removed."""
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")

    image_path = os.path.join(UPLOADS_DIR, scan.image_filename)

    db.delete(scan)
    db.commit()

    if os.path.exists(image_path):
        os.remove(image_path)
