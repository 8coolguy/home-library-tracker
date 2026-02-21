"""Server configuration via environment variables."""

from __future__ import annotations

import os

DATABASE_URL = os.environ.get("HOME_LIBRARY_DB", "sqlite:///home_library.db")
UPLOADS_DIR = os.environ.get("HOME_LIBRARY_UPLOADS", "uploads")
OCR_MIN_CONFIDENCE = float(os.environ.get("HOME_LIBRARY_OCR_CONFIDENCE", "0.5"))
