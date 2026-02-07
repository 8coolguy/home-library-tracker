"""Title vs. author classification for a group of text blocks."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .ocr import TextBlock

# Pattern that catches "by <Author>" (case-insensitive, with optional whitespace)
_BY_RE = re.compile(r"^by\s+", re.IGNORECASE)


def _font_size_proxy(block: TextBlock) -> float:
    """Estimate relative font size from the block's height (the cross-reading
    dimension for horizontal text).  For vertical text the proxy is width."""
    if abs(block.angle) > 45:
        return block.width
    return block.height


def parse_book(blocks: List[TextBlock]) -> Dict[str, Optional[str]]:
    """Classify text blocks from one book cluster into title and author.

    Heuristics (applied in order):
        1. **"by" prefix** — if any block starts with "by ", treat the
           remainder as the author.
        2. **Font-size ratio** — the largest block(s) are likely the title;
           a noticeably smaller block near the top or bottom is the author.
        3. **Positional signal** — on spines the author name usually sits at
           the top or bottom of the cluster.
        4. **Fallback** — concatenate all text as the title; author is null.

    Returns:
        {"title": str, "author": str | None}
    """
    if not blocks:
        return {"title": None, "author": None}

    if len(blocks) == 1:
        text = blocks[0].text.strip()
        m = _BY_RE.match(text)
        if m:
            return {"title": None, "author": text[m.end():].strip()}
        return {"title": text, "author": None}

    # --- 1. Check for explicit "by" marker ---
    by_blocks: List[TextBlock] = []
    non_by_blocks: List[TextBlock] = []
    for b in blocks:
        if _BY_RE.match(b.text.strip()):
            by_blocks.append(b)
        else:
            non_by_blocks.append(b)

    if by_blocks:
        author = " ".join(
            _BY_RE.sub("", b.text.strip()) for b in by_blocks
        ).strip()
        title = " ".join(b.text.strip() for b in non_by_blocks).strip() or None
        return {"title": title, "author": author or None}

    # --- 2. Font-size ratio ---
    sizes = [_font_size_proxy(b) for b in blocks]
    max_size = max(sizes)
    # "Small" blocks are those at most 75 % of the largest
    small_mask = [s < max_size * 0.75 for s in sizes]

    if any(small_mask) and not all(small_mask):
        title_parts = [b for b, small in zip(blocks, small_mask) if not small]
        author_parts = [b for b, small in zip(blocks, small_mask) if small]

        # --- 3. Positional sanity: author at top or bottom of cluster ---
        cluster_center_y = sum(b.center_y for b in blocks) / len(blocks)
        author_center_y = sum(b.center_y for b in author_parts) / len(author_parts)
        title_center_y = sum(b.center_y for b in title_parts) / len(title_parts)

        # Only accept if author is away from the title center (top or bottom)
        if abs(author_center_y - cluster_center_y) >= abs(title_center_y - cluster_center_y):
            title = " ".join(b.text.strip() for b in title_parts).strip()
            author = " ".join(b.text.strip() for b in author_parts).strip()
            return {"title": title or None, "author": author or None}

    # --- 4. Fallback: everything is title ---
    title = " ".join(b.text.strip() for b in blocks).strip()
    return {"title": title or None, "author": None}
