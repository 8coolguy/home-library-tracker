"""Google Books API lookup for book enrichment."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode as qs_encode

from .config import GOOGLE_BOOKS_API_KEY

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/books/v1/volumes"


def _clean_ocr(text: str) -> str:
    """Scrub common OCR noise to improve Google Books match rate.

    - Keep only alphanumeric characters and spaces
    - Drop single-character tokens (likely OCR artifacts)
    - Collapse whitespace
    - Truncate to the first 6 words (longer garbled strings confuse the API)
    """
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    words = [w for w in text.split() if len(w) > 1]
    return " ".join(words[:6])


def _clean_thumbnail(url: str) -> str:
    """Strip noisy query params and force HTTPS."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=False)
    params.pop("zoom", None)
    params.pop("edge", None)
    clean_query = qs_encode({k: v[0] for k, v in params.items()})
    clean = parsed._replace(scheme="https", query=clean_query)
    return urlunparse(clean)


def lookup_book(title: str | None, author: str | None) -> dict | None:
    """Query Google Books API and return enriched book data, or None on failure.

    Returns a dict with keys: title, author, cover_url, isbn.
    Returns None if the API key is not set, no results are found, or a network
    error occurs (caller should fall back to OCR values).
    """
    if not GOOGLE_BOOKS_API_KEY:
        return None

    if not title:
        return None

    try:
        import requests
    except ImportError:
        logger.warning("requests library not available; skipping Google Books lookup")
        return None

    clean_title = _clean_ocr(title)
    if not clean_title:
        return None
    clean_author = _clean_ocr(author) if author else None

    queries = [f"intitle:{clean_title}"]
    if clean_author:
        queries[0] += f" inauthor:{clean_author}"
    # Fallback: plain text search tolerates garbled OCR better
    queries.append(clean_title)

    items = None
    for query in queries:
        params: dict = {"q": query, "maxResults": 1, "key": GOOGLE_BOOKS_API_KEY}
        try:
            response = requests.get(_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            logger.warning("Google Books API request failed for %r", title, exc_info=True)
            return None
        items = data.get("items")
        if items:
            logger.info("Google Books: got results with query %r", query)
            break
        logger.info("Google Books: no results for query %r", query)

    if not items:
        return None

    info = items[0].get("volumeInfo", {})
    logger.info("Google Books: matched %r by %r", info.get("title"), info.get("authors"))

    canonical_title = info.get("title")
    authors = info.get("authors", [])
    canonical_author = authors[0] if authors else None

    image_links = info.get("imageLinks", {})
    raw_thumbnail = image_links.get("thumbnail")
    cover_url = _clean_thumbnail(raw_thumbnail) if raw_thumbnail else None

    isbn = None
    isbn_10 = None
    for identifier in info.get("industryIdentifiers", []):
        id_type = identifier.get("type")
        if id_type == "ISBN_13":
            isbn = identifier.get("identifier")
            break
        if id_type == "ISBN_10":
            isbn_10 = identifier.get("identifier")
    if isbn is None:
        isbn = isbn_10

    logger.info("Google Books: cover_url=%r isbn=%r", cover_url, isbn)

    return {
        "title": canonical_title,
        "author": canonical_author,
        "cover_url": cover_url,
        "isbn": isbn,
    }
