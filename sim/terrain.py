from __future__ import annotations

"""Terrain feature layer utilities."""

from typing import Dict

import numpy as np

# Feature identifiers (uint8)
# These constants are stable and used for serialization.
NONE: np.uint8 = np.uint8(0)
FOREST: np.uint8 = np.uint8(1)
JUNGLE: np.uint8 = np.uint8(2)
MARSH: np.uint8 = np.uint8(3)
SAND: np.uint8 = np.uint8(4)
HILLS: np.uint8 = np.uint8(5)
OASIS: np.uint8 = np.uint8(6)
FOREST_HILLS: np.uint8 = np.uint8(7)
JUNGLE_HILLS: np.uint8 = np.uint8(8)

# Biome identifiers used for validation.
BIOME_GRASS = 0
BIOME_COAST = 1
BIOME_MOUNTAIN = 2
BIOME_OCEAN = 3
BIOME_SAND = 4

# Human readable descriptions for features
_DESCRIPTIONS = {
    int(NONE): "None",
    int(FOREST): "Forest",
    int(JUNGLE): "Jungle",
    int(MARSH): "Marsh",
    int(SAND): "Sand",
    int(HILLS): "Hills",
    int(OASIS): "Oasis",
    int(FOREST_HILLS): "Forest Hills",
    int(JUNGLE_HILLS): "Jungle Hills",
}

# Stable default placement probabilities
DEFAULT_P: Dict[str, float] = {
    "forest": 0.12,
    "jungle": 0.08,
    "marsh": 0.05,
    "hills": 0.20,
    "oasis": 0.02,
    "sand": 0.35,
}


def describe_feature(fid: int) -> str:
    """Return a human-readable description for ``fid``."""
    return _DESCRIPTIONS.get(int(fid), "Unknown")


def _rand_mask(rng: np.random.Generator, shape: tuple[int, int], prob: float) -> np.ndarray:
    """Helper to draw a boolean mask with probability ``prob``.

    ``prob`` is clamped to the inclusive range ``[0, 1]``.
    """
    prob = float(np.clip(prob, 0.0, 1.0))
    if prob <= 0.0:
        return np.zeros(shape, dtype=bool)
    if prob >= 1.0:
        return np.ones(shape, dtype=bool)
    return rng.random(shape) < prob


def generate_features(
    biome: np.ndarray,
    rng: np.random.Generator,
    p: Dict[str, float] | None = None,
) -> np.ndarray:
    """Generate terrain features for ``biome``.

    Parameters
    ----------
    biome:
        2D array of biome identifiers (``uint8``).
    rng:
        NumPy ``Generator`` used for randomness.
    p:
        Optional mapping from feature name to placement probability. Missing
        keys fall back to :data:`DEFAULT_P`.

    Returns
    -------
    np.ndarray
        ``uint8`` array of feature identifiers matching ``biome`` shape.
    """

    b = np.asarray(biome, dtype=np.uint8)
    if b.ndim != 2:
        raise ValueError("biome must be 2D")
    H, W = b.shape
    out = np.zeros((H, W), dtype=np.uint8)

    # Merge probabilities with defaults
    pp = {**DEFAULT_P, **(p or {})}

    # Masks for biome categories
    grass = b == BIOME_GRASS
    sand_bio = b == BIOME_SAND
    land = (b != BIOME_OCEAN) & (b != BIOME_MOUNTAIN)

    # Exclusive features on grass
    marsh_mask = grass & _rand_mask(rng, (H, W), pp["marsh"])
    out[marsh_mask] = MARSH
    available_grass = grass & ~marsh_mask

    forest_mask = available_grass & _rand_mask(rng, (H, W), pp["forest"])
    out[forest_mask] = FOREST
    available_grass &= ~forest_mask

    jungle_mask = available_grass & _rand_mask(rng, (H, W), pp["jungle"])
    out[jungle_mask] = JUNGLE

    # Exclusive features on sand biome
    oasis_mask = sand_bio & _rand_mask(rng, (H, W), pp["oasis"])
    out[oasis_mask] = OASIS
    available_sand = sand_bio & ~oasis_mask

    sand_mask = available_sand & _rand_mask(rng, (H, W), pp["sand"])
    out[sand_mask] = SAND

    # Hills - may stack with forest/jungle
    hills_mask = land & _rand_mask(rng, (H, W), pp["hills"])
    hills_mask &= (out == NONE) | (out == FOREST) | (out == JUNGLE)

    forest_hills = hills_mask & (out == FOREST)
    out[forest_hills] = FOREST_HILLS

    jungle_hills = hills_mask & (out == JUNGLE)
    out[jungle_hills] = JUNGLE_HILLS

    hills_only = hills_mask & (out == NONE)
    out[hills_only] = HILLS

    # Ensure ocean and mountain tiles have no features
    out[(b == BIOME_OCEAN) | (b == BIOME_MOUNTAIN)] = NONE

    out = np.ascontiguousarray(out, dtype=np.uint8)
    return out
