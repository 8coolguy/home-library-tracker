"""Background OCR worker thread."""

from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime

from .config import UPLOADS_DIR, OCR_MIN_CONFIDENCE
from .database import SessionLocal
from .models import Scan, Book

logger = logging.getLogger(__name__)

job_queue: queue.Queue = queue.Queue()


def _process_scan(scan_id: int) -> None:
    """Run OCR on a single scan and persist results."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            logger.error("Scan %d not found", scan_id)
            return

        scan.status = "processing"
        db.commit()

        image_path = os.path.join(UPLOADS_DIR, scan.image_filename)

        # Import here to avoid loading PaddleOCR at module import time
        from home_library import scan_books

        results = scan_books(image_path, min_confidence=OCR_MIN_CONFIDENCE)

        for entry in results:
            db.add(Book(
                scan_id=scan.id,
                title=entry.get("title"),
                author=entry.get("author"),
            ))

        scan.status = "completed"
        scan.completed_at = datetime.utcnow()
        db.commit()
        logger.info("Scan %d completed: %d books found", scan_id, len(results))

    except Exception:
        logger.exception("Scan %d failed", scan_id)
        db.rollback()
        scan = db.get(Scan, scan_id)
        if scan:
            scan.status = "failed"
            scan.error_message = "OCR processing failed"
            db.commit()
    finally:
        db.close()


def _worker_loop() -> None:
    """Continuously pull scan IDs from the queue and process them."""
    logger.info("OCR worker started")
    while True:
        scan_id = job_queue.get()
        if scan_id is None:
            logger.info("OCR worker shutting down")
            break
        _process_scan(scan_id)
        job_queue.task_done()


_worker_thread: threading.Thread | None = None


def start_worker() -> None:
    """Start the background worker thread (idempotent)."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(
        target=_worker_loop, daemon=True, name="ocr-worker"
    )
    _worker_thread.start()


def stop_worker() -> None:
    """Signal the worker to stop (for graceful shutdown)."""
    job_queue.put(None)


def enqueue_scan(scan_id: int) -> None:
    """Add a scan to the processing queue."""
    job_queue.put(scan_id)


def recover_pending_scans() -> None:
    """Re-queue any scans stuck in pending/processing (crash recovery on startup)."""
    db = SessionLocal()
    try:
        stuck = db.query(Scan).filter(Scan.status.in_(["pending", "processing"])).all()
        for scan in stuck:
            scan.status = "pending"
            logger.info("Re-queuing stuck scan %d", scan.id)
            job_queue.put(scan.id)
        db.commit()
    finally:
        db.close()
