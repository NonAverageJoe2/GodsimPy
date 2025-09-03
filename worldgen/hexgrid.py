# hexgrid.py - Flat-top hex axial math and helpers (Python 3.10+)
from __future__ import annotations
import math
from typing import Iterator, Tuple, List

SQRT3 = math.sqrt(3.0)

def axial_to_world_flat(q: int, r: int, radius: float) -> Tuple[float, float]:
    """Flat-top axial spacing -> world (x,z) in pixels (orthographic)."""
    x = 1.5 * radius * q
    z = SQRT3 * radius * (r + 0.5 * q)
    return x, z

def axial_to_world_pointy(q: int, r: int, radius: float) -> Tuple[float, float]:
    """Pointy-top axial spacing -> world (x,z) in pixels (orthographic)."""
    x = SQRT3 * radius * (q + 0.5 * r)
    z = 1.5 * radius * r
    return x, z

def neighbors_axial(q: int, r: int) -> Iterator[Tuple[int, int]]:
    # q,r neighbors for hex grid (flat-top orientation)
    for dq, dr in ((+1,0),(+1,-1),(0,-1),(-1,0),(-1,+1),(0,+1)):
        yield q + dq, r + dr

def in_bounds(q: int, r: int, w: int, h: int) -> bool:
    return 0 <= q < w and 0 <= r < h

def idx(q: int, r: int, w: int) -> int:
    return r * w + q

def distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Calculate hexagonal distance between two axial coordinates."""
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def neighbors6(q: int, r: int) -> Iterator[Tuple[int, int]]:
    """Alias for neighbors_axial for backwards compatibility."""
    return neighbors_axial(q, r)

def axial_to_pixel(q: int, r: int, size: float) -> Tuple[float, float]:
    """Convert axial hex coordinates to pixel coordinates (flat-top)."""
    x = size * (3.0 / 2.0 * q)
    y = size * (SQRT3 / 2.0 * q + SQRT3 * r)
    return x, y

def pixel_to_axial(x: float, y: float, size: float) -> Tuple[int, int]:
    """Convert pixel coordinates to axial hex coordinates (flat-top)."""
    q = (2.0 / 3.0 * x) / size
    r = (-1.0 / 3.0 * x + SQRT3 / 3.0 * y) / size
    return axial_round(q, r)

def axial_round(q: float, r: float) -> Tuple[int, int]:
    """Round fractional axial coordinates to nearest hex."""
    s = -q - r
    rq = round(q)
    rr = round(r)
    rs = round(s)
    
    q_diff = abs(rq - q)
    r_diff = abs(rr - r)
    s_diff = abs(rs - s)
    
    if q_diff > r_diff and q_diff > s_diff:
        rq = -rr - rs
    elif r_diff > s_diff:
        rr = -rq - rs
    
    return int(rq), int(rr)

def hex_polygon(q: int, r: int, size: float) -> List[Tuple[float, float]]:
    """Generate vertices of a hex polygon centered at (q,r) with given size."""
    cx, cy = axial_to_pixel(q, r, size)
    points = []
    for i in range(6):
        angle = math.radians(60 * i)  # flat-top hexagon
        px = cx + size * math.cos(angle)
        py = cy + size * math.sin(angle)
        points.append((px, py))
    return points

def axial_to_offset_flat(q: int, r: int) -> Tuple[int, int]:
    """Convert axial coordinates to offset coordinates (flat-top)."""
    col = q
    row = r + (q - (q & 1)) // 2
    return col, row

def offset_to_axial_flat(col: int, row: int) -> Tuple[int, int]:
    """Convert offset coordinates back to axial coordinates (flat-top)."""
    q = col
    r = row - (col - (col & 1)) // 2
    return q, r
