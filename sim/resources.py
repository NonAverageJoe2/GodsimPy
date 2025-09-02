from __future__ import annotations

"""Resource yield calculations for biome and terrain feature layers."""

from typing import Mapping, Dict

import numpy as np

from .terrain import (
    NONE,
    FOREST,
    JUNGLE,
    MARSH,
    SAND as F_SAND,
    HILLS,
    OASIS,
    FOREST_HILLS,
    JUNGLE_HILLS,
)

# --- Constants -----------------------------------------------------------------

# Default biome yield values (food, production) in float32
DEFAULT_YIELDS: Dict[int, tuple[np.float32, np.float32]] = {
    0: (np.float32(1.0), np.float32(0.6)),  # grass
    1: (np.float32(0.6), np.float32(0.3)),  # coast
    2: (np.float32(0.2), np.float32(1.2)),  # mountain
    3: (np.float32(0.2), np.float32(0.1)),  # ocean
    4: (np.float32(0.4), np.float32(0.2)),  # sand
}

# Fallback for unknown biomes
_FALLBACK_YIELD = (np.float32(0.2), np.float32(1.2))

CAPACITY_MIN: np.float32 = np.float32(50.0)
CAPACITY_MAX: np.float32 = np.float32(150.0)

# Terrain feature modifiers, stored as (food_multiplier, production_multiplier)
_base_feature_mods: Dict[int, tuple[np.float32, np.float32]] = {
    int(NONE): (np.float32(1.0), np.float32(1.0)),
    int(FOREST): (np.float32(0.90), np.float32(1.20)),
    int(JUNGLE): (np.float32(0.85), np.float32(1.25)),
    int(MARSH): (np.float32(0.70), np.float32(0.50)),
    int(F_SAND): (np.float32(1.00), np.float32(1.00)),
    int(HILLS): (np.float32(0.85), np.float32(1.30)),
    int(OASIS): (np.float32(2.00), np.float32(0.50)),
}


def _combine(a: tuple[np.float32, np.float32],
             b: tuple[np.float32, np.float32]) -> tuple[np.float32, np.float32]:
    """Elementwise multiply two modifier tuples."""
    return (np.float32(a[0] * b[0]), np.float32(a[1] * b[1]))


DEFAULT_FEATURE_MODS: Dict[int, tuple[np.float32, np.float32]] = dict(_base_feature_mods)
DEFAULT_FEATURE_MODS[int(FOREST_HILLS)] = _combine(_base_feature_mods[int(FOREST)], _base_feature_mods[int(HILLS)])
DEFAULT_FEATURE_MODS[int(JUNGLE_HILLS)] = _combine(_base_feature_mods[int(JUNGLE)], _base_feature_mods[int(HILLS)])

# Fallback for unknown features
_FEATURE_FALLBACK = (np.float32(1.0), np.float32(1.0))

# --- Helper functions -----------------------------------------------------------

def _prepare_lut(mapping: Mapping[int, tuple[float, float]],
                 fallback: tuple[float, float]) -> tuple[np.ndarray, int]:
    """Build a LUT array and return it along with the maximum key."""
    if not mapping:
        max_key = -1
    else:
        max_key = max(int(k) for k in mapping)
    lut = np.empty((max_key + 2, 2), dtype=np.float32)
    lut[:] = np.array(fallback, dtype=np.float32)
    for k, v in mapping.items():
        lut[int(k)] = np.array(v, dtype=np.float32)
    return lut, max_key


# --- Public functions -----------------------------------------------------------

def biome_yields(
    biome: np.ndarray,
    mapping: Mapping[int, tuple[float, float]] | None = None,
) -> Dict[str, np.ndarray]:
    """Compute base food and production yields for ``biome``.

    Parameters
    ----------
    biome:
        2D array of biome identifiers.
    mapping:
        Optional custom biome-to-yield mapping.

    Returns
    -------
    dict
        Mapping with keys ``"food"`` and ``"prod"``.
    """

    b_arr = np.asarray(biome)
    if b_arr.ndim != 2:
        raise ValueError("biome must be 2D")
    if not np.isfinite(b_arr).all():
        raise ValueError("biome contains NaN or Inf")
    b = b_arr.astype(np.int64, copy=False)

    m = DEFAULT_YIELDS if mapping is None else {int(k): (np.float32(v[0]), np.float32(v[1])) for k, v in mapping.items()}
    lut, max_key = _prepare_lut(m, _FALLBACK_YIELD)

    idx = np.where((b >= 0) & (b <= max_key), b, max_key + 1)
    vals = np.take(lut, idx, axis=0)
    food = np.nan_to_num(np.ascontiguousarray(vals[..., 0], dtype=np.float32))
    prod = np.nan_to_num(np.ascontiguousarray(vals[..., 1], dtype=np.float32))
    return {"food": food, "prod": prod}


def apply_feature_modifiers(
    food: np.ndarray,
    prod: np.ndarray,
    feature_map: np.ndarray,
    modifiers: Mapping[int, tuple[float, float]] | None = None,
) -> Dict[str, np.ndarray]:
    """Apply feature modifiers to ``food`` and ``prod`` arrays.

    Parameters
    ----------
    food, prod:
        Base yield arrays (float32) matching ``feature_map`` shape.
    feature_map:
        2D array of terrain feature identifiers.
    modifiers:
        Optional mapping from feature id to multipliers.
    """

    f_arr = np.asarray(food)
    p_arr = np.asarray(prod)
    fmap = np.asarray(feature_map)
    if f_arr.shape != p_arr.shape or f_arr.shape != fmap.shape:
        raise ValueError("food, prod, and feature_map must have the same shape")
    if f_arr.ndim != 2:
        raise ValueError("food/prod must be 2D")
    if not (np.isfinite(f_arr).all() and np.isfinite(p_arr).all() and np.isfinite(fmap).all()):
        raise ValueError("inputs contain NaN or Inf")

    food0 = np.ascontiguousarray(f_arr, dtype=np.float32)
    prod0 = np.ascontiguousarray(p_arr, dtype=np.float32)
    feat = fmap.astype(np.int64, copy=False)

    mods = DEFAULT_FEATURE_MODS if modifiers is None else {int(k): (np.float32(v[0]), np.float32(v[1])) for k, v in modifiers.items()}
    lut, max_key = _prepare_lut(mods, _FEATURE_FALLBACK)

    idx = np.where((feat >= 0) & (feat <= max_key), feat, max_key + 1)
    mvals = np.take(lut, idx, axis=0)

    out_food = np.nan_to_num(np.ascontiguousarray(food0 * mvals[..., 0], dtype=np.float32))
    out_prod = np.nan_to_num(np.ascontiguousarray(prod0 * mvals[..., 1], dtype=np.float32))
    return {"food": out_food, "prod": out_prod}


def yields_with_features(
    biome: np.ndarray,
    feature_map: np.ndarray | None = None,
    *,
    biome_map: Mapping[int, tuple[float, float]] | None = None,
    feature_mods: Mapping[int, tuple[float, float]] | None = None,
) -> Dict[str, np.ndarray]:
    """Return yields for ``biome`` optionally modified by ``feature_map``."""

    base = biome_yields(biome, biome_map)
    if feature_map is None:
        return base
    return apply_feature_modifiers(base["food"], base["prod"], feature_map, feature_mods)


def carrying_capacity(
    food: np.ndarray,
    *,
    k_min: float = float(CAPACITY_MIN),
    k_max: float = float(CAPACITY_MAX),
) -> np.ndarray:
    """Compute logistic growth carrying capacity from food availability.

    Parameters
    ----------
    food:
        2D array of food yields in the range ``[0, 1.2]`` approximately.
    k_min, k_max:
        Capacity range. Defaults ``[50, 150]``.
    """

    f_arr = np.asarray(food)
    if f_arr.ndim != 2:
        raise ValueError("food must be 2D")
    if not np.isfinite(f_arr).all():
        raise ValueError("food contains NaN or Inf")

    food0 = np.ascontiguousarray(f_arr, dtype=np.float32)
    clipped = np.clip(food0, 0.0, 1.2)
    k = k_min + (k_max - k_min) * clipped / 1.2
    return np.nan_to_num(np.ascontiguousarray(k, dtype=np.float32))

