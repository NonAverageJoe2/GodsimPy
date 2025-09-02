# hexgrid.py - Flat-top hex axial math and helpers (Python 3.10+)
from __future__ import annotations
import math
from typing import Iterator, Tuple

SQRT3 = math.sqrt(3.0)

def axial_to_world_flat(q: int, r: int, radius: float) -> Tuple[float, float]:
    """Flat-top axial spacing -> world (x,z) in pixels (orthographic)."""
    x = 1.5 * radius * q
    z = SQRT3 * radius * (r + 0.5 * q)
    return x, z

def neighbors_axial(q: int, r: int) -> Iterator[Tuple[int, int]]:
    # q,r neighbors for hex grid (flat-top orientation)
    for dq, dr in ((+1,0),(+1,-1),(0,-1),(-1,0),(-1,+1),(0,+1)):
        yield q + dq, r + dr

def in_bounds(q: int, r: int, w: int, h: int) -> bool:
    return 0 <= q < w and 0 <= r < h

def idx(q: int, r: int, w: int) -> int:
    return r * w + q
