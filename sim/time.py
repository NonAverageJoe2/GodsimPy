"""Minimal deterministic calendar utilities for the simulation.

This module implements simple date arithmetic without leap years. The
calendar starts at 1/1/1 (month/day/year) and uses a static 12-month
length table. All functions operate purely on supplied arguments and
return new ``(month, day, year)`` tuples, avoiding any global state.
"""

from __future__ import annotations

from typing import Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_LENGTHS: Tuple[int, ...] = (
    31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
)
"""Number of days in each month starting with January."""

VALID_SCALES = {"week", "month", "year"}
"""Recognised time step scales."""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp_min(value: int, minimum: int = 1) -> int:
    """Return ``value`` clamped so it is at least ``minimum``."""

    return value if value >= minimum else minimum


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def normalize_date(m: int, d: int, y: int) -> Tuple[int, int, int]:
    """Normalise a date tuple.

    Months beyond 12 roll into subsequent years and days beyond the
    month's length roll forward into following months. All values are
    ensured to be at least ``1``.

    Parameters
    ----------
    m, d, y:
        Month, day and year components. Values ``<1`` are clamped to ``1``.

    Returns
    -------
    tuple
        Normalised ``(month, day, year)`` tuple.
    """

    m = _clamp_min(m)
    d = _clamp_min(d)
    y = _clamp_min(y)

    # Roll months into years.
    if m > 12:
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1

    # Roll days into following months/years.
    while True:
        month_len = MONTH_LENGTHS[m - 1]
        if d <= month_len:
            break
        d -= month_len
        m += 1
        if m > 12:
            m = 1
            y += 1

    return m, d, y


def add_days(m: int, d: int, y: int, days: int) -> Tuple[int, int, int]:
    """Advance a date by ``days`` days.

    Parameters
    ----------
    m, d, y:
        Starting date components.
    days:
        Number of days to add. Must be ``>=0``.
    """

    if days < 0:
        raise ValueError("days must be >= 0")

    d += days
    return normalize_date(m, d, y)


def add_months(m: int, d: int, y: int, months: int) -> Tuple[int, int, int]:
    """Advance a date by ``months`` months.

    The day component is clamped to the target month's length if
    necessary.
    """

    if months < 0:
        raise ValueError("months must be >= 0")

    m, d, y = normalize_date(m, d, y)

    total = (y - 1) * 12 + (m - 1) + months
    new_y = total // 12 + 1
    new_m = total % 12 + 1
    new_d = d

    month_len = MONTH_LENGTHS[new_m - 1]
    if new_d > month_len:
        new_d = month_len

    return new_m, new_d, new_y


def add_years(m: int, d: int, y: int, years: int) -> Tuple[int, int, int]:
    """Advance a date by ``years`` years.

    February 29 is clamped to February 28 because the calendar contains
    no leap years.
    """

    if years < 0:
        raise ValueError("years must be >= 0")

    if m == 2 and d > 28:
        d = 28

    m, d, y = normalize_date(m, d, y)
    y += years
    return m, d, y


def step_date(
    m: int, d: int, y: int, scale: str, steps: int = 1
) -> Tuple[int, int, int]:
    """Advance a date according to ``scale``.

    Parameters
    ----------
    m, d, y:
        Starting date components.
    scale:
        One of ``"week"``, ``"month"`` or ``"year"``.
    steps:
        Number of units to advance (default ``1``). Must be ``>=0``.
    """

    if scale not in VALID_SCALES:
        raise ValueError(f"invalid scale: {scale!r}")
    if steps < 0:
        raise ValueError("steps must be >= 0")

    if scale == "week":
        return add_days(m, d, y, 7 * steps)
    if scale == "month":
        return add_months(m, d, y, steps)
    return add_years(m, d, y, steps)


def scale_to_years(scale: str) -> float:
    """Convert a time ``scale`` to its approximate length in years."""

    if scale not in VALID_SCALES:
        raise ValueError(f"invalid scale: {scale!r}")

    if scale == "week":
        return 7 / 365
    if scale == "month":
        return 30 / 365
    return 1.0

