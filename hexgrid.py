"""Hex grid axial coordinate utilities."""
from __future__ import annotations
import math
from typing import Iterator, List, Tuple

SQRT3 = math.sqrt(3.0)
Coord = Tuple[int, int]


def neighbors6(q: int, r: int) -> List[Coord]:
    """Return the six axial neighbors of (q,r)."""
    return [
        (q + 1, r),
        (q + 1, r - 1),
        (q, r - 1),
        (q - 1, r),
        (q - 1, r + 1),
        (q, r + 1),
    ]

# Backwards compatibility with older helpers
neighbors_axial = neighbors6


def axial_to_pixel(q: int, r: int, hex_size: float) -> Tuple[float, float]:
    """Convert axial coords to 2D pixel coords for flat-top hexes."""
    x = 1.5 * hex_size * q
    y = SQRT3 * hex_size * (r + 0.5 * q)
    return x, y

# Alias used by worldgen/render code
axial_to_world_flat = axial_to_pixel


def hex_polygon(q: int, r: int, hex_size: float) -> List[Tuple[float, float]]:
    """Return the 6 polygon corner points for the given hex."""
    cx, cy = axial_to_pixel(q, r, hex_size)
    pts: List[Tuple[float, float]] = []
    for i in range(6):
        angle = math.radians(60 * i)
        px = cx + hex_size * math.cos(angle)
        py = cy + hex_size * math.sin(angle)
        pts.append((px, py))
    return pts


def distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Return hex distance between two axial coords."""
    s1 = -q1 - r1
    s2 = -q2 - r2
    return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))


def in_bounds(q: int, r: int, w: int, h: int) -> bool:
    """Return True if (q,r) lies within rectangular axial bounds."""
    return 0 <= q < w and 0 <= r < h
