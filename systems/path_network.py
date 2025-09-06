"""Path network and trade route mechanics.

This module provides a lightweight system that allows settlements to
construct paths between each other and compute travel times for trade
shipments.  The first path type implemented is a simple "dirt path"
which reduces travel time between connected settlements.

The system is intentionally decoupled from the wider game engine so that
it can be unit tested in isolation.  It exposes a small API for
managing settlements, starting path construction projects and querying
travel times and debug information.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Helper utilities

def _axial_distance(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Return hex distance between two axial coordinates."""
    aq, ar = a
    bq, br = b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


# ---------------------------------------------------------------------------
# Data classes


@dataclass
class Settlement:
    """Minimal settlement data used by the path network."""

    ident: str
    q: int
    r: int


@dataclass
class Path:
    """Represents a path construction project between two settlements."""

    a: str
    b: str
    length: int
    build_time: float
    workers: int
    progress: float = 0.0
    completed: bool = False

    def advance(self, dt: float) -> None:
        """Advance construction by ``dt`` time units."""
        if self.completed:
            return
        # progress scaled by number of workers allocated
        self.progress += dt * max(self.workers, 0)
        if self.progress >= self.build_time:
            self.completed = True


# ---------------------------------------------------------------------------
# Main path network manager


class PathNetwork:
    """Manage settlements, paths and travel time calculations."""

    def __init__(self, speed_no_path: float = 1.0, path_speed_multiplier: float = 0.5):
        self.speed_no_path = speed_no_path
        self.path_speed_multiplier = path_speed_multiplier
        self.settlements: Dict[str, Settlement] = {}
        self.paths: Dict[Tuple[str, str], Path] = {}

    # -- Settlement management -------------------------------------------------
    def add_settlement(self, ident: str, q: int, r: int) -> None:
        self.settlements[ident] = Settlement(ident, q, r)

    # -- Path construction ----------------------------------------------------
    def start_path(self, a: str, b: str, workers: int, build_time: float) -> Path:
        """Begin constructing a path between two settlements."""
        sa = self.settlements[a]
        sb = self.settlements[b]
        length = _axial_distance((sa.q, sa.r), (sb.q, sb.r))
        key = tuple(sorted((a, b)))
        path = Path(a, b, length, build_time, workers)
        self.paths[key] = path
        return path

    def advance(self, dt: float) -> None:
        for path in self.paths.values():
            path.advance(dt)

    def force_complete_path(self, a: str, b: str) -> None:
        key = tuple(sorted((a, b)))
        path = self.paths.get(key)
        if path is None:
            return
        path.progress = path.build_time
        path.completed = True

    # -- Travel calculations ---------------------------------------------------
    def travel_time(self, a: str, b: str) -> float:
        """Return travel time between two settlements."""
        sa = self.settlements[a]
        sb = self.settlements[b]
        dist = _axial_distance((sa.q, sa.r), (sb.q, sb.r))
        base_time = dist / max(self.speed_no_path, 1e-6)
        key = tuple(sorted((a, b)))
        path = self.paths.get(key)
        if path and path.completed:
            return base_time * self.path_speed_multiplier
        return base_time

    def debug_info(self, a: str, b: str) -> Dict[str, float]:
        """Return diagnostic information for the connection between ``a`` and ``b``."""
        sa = self.settlements[a]
        sb = self.settlements[b]
        dist = _axial_distance((sa.q, sa.r), (sb.q, sb.r))
        base_time = dist / max(self.speed_no_path, 1e-6)
        travel_time = self.travel_time(a, b)
        key = tuple(sorted((a, b)))
        path_exists = key in self.paths
        efficiency = base_time / travel_time if travel_time > 0 else 0.0
        return {
            "distance": dist,
            "base_time": base_time,
            "travel_time": travel_time,
            "efficiency": efficiency,
            "path_exists": path_exists,
        }
