"""PaddleOCR wrapper and TextBlock dataclass."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import numpy as np
from paddleocr import PaddleOCR


@dataclass
class TextBlock:
    """A single detected text region."""

    text: str
    polygon: np.ndarray  # shape (4, 2) — four corner points
    confidence: float
    center_x: float
    center_y: float
    width: float
    height: float
    angle: float  # degrees, 0 = horizontal, 90 = vertical

    @staticmethod
    def from_paddle(box: list, text: str, confidence: float) -> TextBlock:
        """Build a TextBlock from raw PaddleOCR output.

        Args:
            box: list of 4 [x, y] points (top-left, top-right, bottom-right, bottom-left).
            text: recognized string.
            confidence: recognition confidence 0-1.
        """
        poly = np.array(box, dtype=np.float64)
        cx = poly[:, 0].mean()
        cy = poly[:, 1].mean()

        # Width = average of top and bottom edge lengths
        top_edge = np.linalg.norm(poly[1] - poly[0])
        bottom_edge = np.linalg.norm(poly[2] - poly[3])
        w = (top_edge + bottom_edge) / 2.0

        # Height = average of left and right edge lengths
        left_edge = np.linalg.norm(poly[3] - poly[0])
        right_edge = np.linalg.norm(poly[2] - poly[1])
        h = (left_edge + right_edge) / 2.0

        # Angle from the top edge direction
        dx = poly[1][0] - poly[0][0]
        dy = poly[1][1] - poly[0][1]
        angle = math.degrees(math.atan2(dy, dx))

        return TextBlock(
            text=text,
            polygon=poly,
            confidence=confidence,
            center_x=cx,
            center_y=cy,
            width=w,
            height=h,
            angle=angle,
        )


_ocr_instance: PaddleOCR | None = None


def _get_ocr() -> PaddleOCR:
    """Lazy-init a shared PaddleOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_instance


def run_ocr(image_path: str, min_confidence: float = 0.5) -> List[TextBlock]:
    """Run PaddleOCR on an image and return filtered TextBlocks.

    Args:
        image_path: path to an image file.
        min_confidence: discard results below this confidence.

    Returns:
        List of TextBlock sorted top-to-bottom then left-to-right.
    """
    ocr = _get_ocr()
    result = ocr.ocr(image_path, cls=True)

    blocks: List[TextBlock] = []
    if not result or not result[0]:
        return blocks

    for line in result[0]:
        box, (text, conf) = line[0], line[1]
        if conf < min_confidence:
            continue
        blocks.append(TextBlock.from_paddle(box, text, conf))

    # Sort by vertical position, then horizontal
    blocks.sort(key=lambda b: (b.center_y, b.center_x))
    return blocks
