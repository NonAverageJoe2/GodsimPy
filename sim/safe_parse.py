from __future__ import annotations
"""Utility helpers for safely coercing values to numbers.

These helpers are defensive – they attempt to coerce a given value to
:class:`int` or :class:`float` and fall back to a provided default when the
value cannot be interpreted as a finite number.  A small warning is logged
whenever the coercion fails so callers can diagnose malformed data without the
sim crashing.
"""

from typing import Any
import math
import logging

logger = logging.getLogger(__name__)


def to_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to ``int``.

    ``bool`` values are returned as-is.  Strings are stripped and parsed when
    they look like integers.  Non finite floats or completely invalid values
    trigger a warning and ``default`` is returned instead.
    """
    # Fast path for normal ints (but not booleans which are ints too)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    # Accept finite floats
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    # Strings that represent integers
    if isinstance(value, str):
        s = value.strip()
        if s and (s.isdigit() or (s[0] in {"+", "-"} and s[1:].isdigit())):
            try:
                return int(s)
            except Exception:  # pragma: no cover - very unlikely
                pass
    if value is None:
        return default
    logger.warning("to_int: coercing %r to default %r", value, default)
    return default


def to_float(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to ``float`` in a safe way.

    Strings are parsed using ``float`` when possible.  Non finite floats or
    invalid inputs emit a warning and ``default`` is returned.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            f = float(value)
            if math.isfinite(f):
                return f
        except Exception:  # pragma: no cover - should not happen
            pass
    if isinstance(value, str):
        s = value.strip()
        try:
            f = float(s)
        except Exception:
            logger.warning("to_float: coercing %r to default %r", value, default)
            return default
        if math.isfinite(f):
            return f
    if value is None:
        return default
    logger.warning("to_float: coercing %r to default %r", value, default)
    return default
