"""Spatial clustering of text blocks into per-book groups."""

from __future__ import annotations

from typing import List

import numpy as np

from .ocr import TextBlock


def _dominant_orientation(blocks: List[TextBlock]) -> str:
    """Decide whether the shelf text is mostly vertical (spines) or horizontal (covers).

    Returns:
        "vertical" if most text is rotated > 45° from horizontal, else "horizontal".
    """
    vertical_count = sum(1 for b in blocks if abs(b.angle) > 45)
    return "vertical" if vertical_count > len(blocks) / 2 else "horizontal"


def _cluster_1d(values: List[float], gap_threshold: float) -> List[List[int]]:
    """Greedy 1-D clustering: consecutive values within *gap_threshold* of each
    other belong to the same cluster.

    Args:
        values: one coordinate per block.
        gap_threshold: maximum gap between adjacent sorted values.

    Returns:
        List of clusters, each cluster is a list of original indices.
    """
    if not values:
        return []

    order = np.argsort(values)
    sorted_vals = np.array(values)[order]

    clusters: List[List[int]] = [[int(order[0])]]
    for i in range(1, len(sorted_vals)):
        if sorted_vals[i] - sorted_vals[i - 1] > gap_threshold:
            clusters.append([])
        clusters[-1].append(int(order[i]))

    return clusters


def group_blocks(blocks: List[TextBlock]) -> List[List[TextBlock]]:
    """Group text blocks into per-book clusters.

    Strategy:
        Books on a shelf are always separated along the X axis regardless of
        text orientation.  We cluster block center_x values using a 1-D greedy
        algorithm with an adaptive gap threshold derived from the median block
        width.

        For vertical spines the block width is small (spine thickness), giving
        a tight threshold that separates adjacent spines.  For horizontal text
        the width is larger, giving a looser threshold that still groups a
        title line with its author line on the same book.

    Returns:
        List of groups, each group a list of TextBlocks belonging to one book.
    """
    if not blocks:
        return []
    if len(blocks) == 1:
        return [blocks]

    # Always cluster along X — books sit side-by-side on shelves
    positions = [b.center_x for b in blocks]

    orientation = _dominant_orientation(blocks)
    if orientation == "vertical":
        # For vertical spines, use width (the narrow spine dimension)
        sizes = [b.width for b in blocks]
    else:
        # For horizontal text, use width (the span of the text line)
        sizes = [b.width for b in blocks]

    median_size = float(np.median(sizes)) if sizes else 50.0
    gap_threshold = median_size * 0.8

    clusters = _cluster_1d(positions, gap_threshold)
    return [[blocks[i] for i in cluster] for cluster in clusters]
