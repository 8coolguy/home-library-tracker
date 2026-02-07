"""home-library: detect and identify books on shelves using PaddleOCR."""

from __future__ import annotations

from typing import Dict, List, Optional

from .grouping import group_blocks
from .ocr import run_ocr
from .parsing import parse_book


def scan_books(
    image_path: str,
    min_confidence: float = 0.5,
) -> List[Dict[str, Optional[str]]]:
    """Scan a bookshelf image and return a list of detected books.

    Args:
        image_path: path to a bookshelf photo.
        min_confidence: OCR confidence threshold (0-1).

    Returns:
        List of dicts, each with "title" and "author" keys.
    """
    blocks = run_ocr(image_path, min_confidence=min_confidence)
    groups = group_blocks(blocks)
    return [parse_book(g) for g in groups]


def scan_cover(
    image_path: str,
    min_confidence: float = 0.5,
) -> Dict[str, Optional[str]]:
    """Scan a single book-cover image and return its title and author.

    Args:
        image_path: path to a book cover photo.
        min_confidence: OCR confidence threshold (0-1).

    Returns:
        Dict with "title" and "author" keys.
    """
    blocks = run_ocr(image_path, min_confidence=min_confidence)
    return parse_book(blocks)


__all__ = ["scan_books", "scan_cover"]
