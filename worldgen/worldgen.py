# worldgen.py - one-shot pipeline to build heightmap & biomes
from __future__ import annotations

import numpy as np
from typing import Tuple

from .noise import value_noise
from .plates import generate_plates, apply_plate_forces
from .hexgrid import neighbors_axial


def generate_height(width: int, height: int, seed: int,
                    plate_count: int = 11, hex_radius: float = 1.0) -> np.ndarray:
    """Return a normalized height map in the range [0,1].

    The base terrain is value noise with a few octaves.  We then sample a
    handful of tectonic plate centers with random velocities and perturb the
    terrain by signed dot products along plate boundaries.  A small smoothing
    pass is applied before the result is normalized to ``[0,1]``.  All
    randomness is derived from ``seed`` to keep determinism.
    """

    base = value_noise(width, height, scale=24, octaves=5,
                       persistence=0.55, lacunarity=2.1, seed=seed)
    plate_map, vels, XZ = generate_plates(width, height, plate_count, hex_radius, seed)
    height_map = base.copy()
    apply_plate_forces(height_map, plate_map, vels, XZ, width, height, seed)

    # Smooth via simple neighbour averaging for a couple of iterations
    src = height_map.copy()
    dst = src.copy()
    for _ in range(2):
        for r in range(height):
            for q in range(width):
                s = src[r, q]
                c = 1.0
                for dq, dr in ((+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)):
                    nq, nr = q + dq, r + dr
                    if 0 <= nq < width and 0 <= nr < height:
                        s += src[nr, nq]
                        c += 1.0
                dst[r, q] = s / c
        src, dst = dst, src

    height_map = src

    mn, mx = float(height_map.min()), float(height_map.max())
    span = max(mx - mn, 1e-6)
    height_map = (height_map - mn) / span
    return height_map.astype(np.float32)


def classify_biomes(height: np.ndarray, sea_level: float, mountain_h: float) -> np.ndarray:
    """Classify height map into simple biomes.

    ``height`` is assumed to be normalized to ``[0,1]``.  Tiles at or below
    ``sea_level`` are oceans, tiles at or above ``mountain_h`` are mountains.
    The remainder are grass unless they neighbour an ocean tile (6-way), in
    which case they become coast.
    """

    H, W = height.shape
    out = np.empty((H, W), dtype=object)
    for r in range(H):
        for q in range(W):
            h0 = float(height[r, q])
            if h0 <= sea_level:
                out[r, q] = "ocean"
            elif h0 >= mountain_h:
                out[r, q] = "mountain"
            else:
                out[r, q] = "grass"

    for r in range(H):
        for q in range(W):
            if out[r, q] == "ocean":
                continue
            for nq, nr in neighbors_axial(q, r):
                if 0 <= nq < W and 0 <= nr < H and out[nr, nq] == "ocean":
                    out[r, q] = "coast"
                    break
    return out


def apply_worldgen(engine, sea_percentile: float = 0.35,
                   mountain_thresh: float = 0.8) -> Tuple[np.ndarray, np.ndarray]:
    """Populate ``engine.world`` with heights and biome strings.

    ``sea_percentile`` is used to pick the sea level threshold from the height
    distribution. ``mountain_thresh`` is interpreted against the normalized
    height map.  The function returns the raw height map and biome map for
    convenience.
    """

    w = engine.world.width_hex
    h = engine.world.height_hex
    seed = engine.world.seed
    height = generate_height(w, h, seed)
    sea = float(np.quantile(height, sea_percentile))
    biomes = classify_biomes(height, sea, mountain_thresh)

    engine.world.sea_level = sea
    idx = 0
    for r in range(h):
        for q in range(w):
            t = engine.world.tiles[idx]
            t.height = float(height[r, q])
            t.biome = str(biomes[r, q])
            idx += 1

    return height, biomes


def build_world(w: int, h: int, seed: int,
                plate_count: int,
                hex_radius: float,
                sea_level_percentile: float = 0.50,
                mountain_h: float = 0.80) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    height = generate_height(w, h, seed, plate_count, hex_radius)
    sea = float(np.quantile(height, sea_level_percentile))
    plate_map, vels, XZ = generate_plates(w, h, plate_count, hex_radius, seed)
    # ``plate_map`` and ``XZ`` are retained for compatibility with older API
    return height.astype(np.float32), plate_map.astype(np.int32), sea, XZ
