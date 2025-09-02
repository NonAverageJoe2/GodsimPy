# worldgen.py - one-shot pipeline to build heightmap & biomes
from __future__ import annotations
import numpy as np
from typing import Tuple
from noise import value_noise
from plates import generate_plates, apply_plate_forces

def build_world(w: int, h: int, seed: int,
                plate_count: int,
                hex_radius: float,
                sea_level_percentile: float = 0.50,
                mountain_h: float = 0.80) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    base = value_noise(w, h, scale=24, octaves=5, persistence=0.55, lacunarity=2.1, seed=seed)
    plate_map, vels, XZ = generate_plates(w, h, plate_count, hex_radius, seed)
    height = base.copy()
    apply_plate_forces(height, plate_map, vels, XZ, w, h, seed)

    # smooth a bit (simple neighbor avg)
    src = height.copy(); dst = src.copy()
    for _ in range(2):
        for r in range(h):
            for q in range(w):
                s = src[r, q]; c = 1.0
                for dq, dr in ((+1,0),(+1,-1),(0,-1),(-1,0),(-1,+1),(0,+1)):
                    nq, nr = q + dq, r + dr
                    if 0 <= nq < w and 0 <= nr < h:
                        s += src[nr, nq]; c += 1.0
                dst[r, q] = s / c
        src, dst = dst, src

    height = src
    # normalize 0..1
    mn, mx = float(height.min()), float(height.max())
    span = max(mx - mn, 1e-6)
    height = (height - mn) / span
    sea = float(np.quantile(height, sea_level_percentile))
    return height.astype(np.float32), plate_map.astype(np.int32), sea, XZ
