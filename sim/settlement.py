from __future__ import annotations

"""Seeding of background population across world tiles."""

import numpy as np
from numpy.typing import NDArray

from sim.state import WorldState
from sim.resources import yields_with_features, carrying_capacity


# -----------------------------------------------------------------------------
# Helpers


def _land_mask(biome: np.ndarray) -> np.ndarray:
    """Return boolean mask for land tiles (not mountain or ocean)."""
    return (biome != 2) & (biome != 3)


# -----------------------------------------------------------------------------
# Public API


def seed_background_population(
    ws: WorldState,
    feature_map: np.ndarray | None = None,
    *,
    seed: int = 0,
    max_fraction_of_capacity: float = 0.08,
    min_people_per_tile: float = 50.0,
    noise_strength: float = 0.25,
) -> WorldState:
    """Populate ``ws.pop_map`` with unaffiliated locals on land tiles.

    The function computes carrying capacity from biome/feature yields and uses
    it to determine a deterministic background population with random jitter.
    Existing populations are only increased – never reduced – and ownership
    information remains unchanged.

    Parameters
    ----------
    ws:
        World state to modify in place.
    feature_map:
        Optional terrain feature identifiers; must match the biome map shape.
    seed:
        Seed for the deterministic random number generator.
    max_fraction_of_capacity:
        Maximum fraction of the carrying capacity to use for the base
        population. Must be within ``[0, 0.5]``.
    min_people_per_tile:
        Minimum population on land tiles after seeding. Must be non-negative.
    noise_strength:
        Magnitude of random jitter applied to the base population. Must be
        within ``[0, 1]``.

    Returns
    -------
    WorldState
        The same ``ws`` instance with ``pop_map`` updated.
    """

    # --- Parameter validation -------------------------------------------------
    if not (0.0 <= max_fraction_of_capacity <= 0.5):
        raise ValueError("max_fraction_of_capacity must be in [0, 0.5]")
    if not (0.0 <= noise_strength <= 1.0):
        raise ValueError("noise_strength must be in [0, 1]")
    if min_people_per_tile < 0.0:
        raise ValueError("min_people_per_tile must be >= 0")

    biome: NDArray[np.uint8] = np.asarray(ws.biome_map)
    pop: NDArray[np.float32] = np.asarray(ws.pop_map)

    if biome.ndim != 2 or pop.ndim != 2:
        raise ValueError("biome_map and pop_map must be 2D")
    if biome.shape != pop.shape:
        raise ValueError("biome_map and pop_map must have the same shape")
    if not (np.isfinite(biome).all() and np.isfinite(pop).all()):
        raise ValueError("biome_map and pop_map must be finite")
    if (pop < 0).any():
        raise ValueError("pop_map cannot contain negative values")

    fmap: NDArray[np.int32] | None
    if feature_map is not None:
        fmap = np.asarray(feature_map)
        if fmap.shape != biome.shape:
            raise ValueError("feature_map shape must match biome_map")
        if fmap.ndim != 2:
            raise ValueError("feature_map must be 2D")
        if not np.isfinite(fmap).all():
            raise ValueError("feature_map must be finite")
    else:
        fmap = None

    # --- Carrying capacity and base population -------------------------------
    food = yields_with_features(biome, fmap)["food"]
    K = carrying_capacity(food)
    base = np.ascontiguousarray(
        K * np.float32(max_fraction_of_capacity), dtype=np.float32
    )

    rng = np.random.default_rng(seed)
    noise = rng.random(base.shape, dtype=np.float32) * np.float32(2.0) - np.float32(1.0)
    jitter = base * (np.float32(noise_strength) * noise)
    target = base + jitter
    target = np.clip(
        target, 0.0, base * (np.float32(1.0) + np.float32(noise_strength))
    )

    land = _land_mask(biome)
    target = np.where(
        land, np.maximum(target, np.float32(min_people_per_tile)), np.float32(0.0)
    )
    target = np.ascontiguousarray(target, dtype=np.float32)

    ws.pop_map = np.ascontiguousarray(np.maximum(pop, target), dtype=np.float32)
    return ws
