# biomes.py - classify heightmap to simple biomes
from __future__ import annotations
import numpy as np
from enum import IntEnum
from .hexgrid import neighbors_axial, in_bounds

class Biome(IntEnum):
    GRASS = 0
    COAST = 1
    MOUNTAIN = 2
    OCEAN = 3
    DESERT = 4

# Backwards compatibility constants
GRASS, COAST, MOUNTAIN, OCEAN = Biome.GRASS, Biome.COAST, Biome.MOUNTAIN, Biome.OCEAN

def build_biomes(height: np.ndarray, sea_level: float, mountain_h: float) -> np.ndarray:
    H, W = height.shape
    out = np.zeros((H, W), dtype=np.int32)
    for r in range(H):
        for q in range(W):
            h0 = float(height[r, q])
            if h0 < sea_level:
                out[r, q] = OCEAN
            elif h0 >= mountain_h:
                out[r, q] = MOUNTAIN
            else:
                coast = False
                for nq, nr in neighbors_axial(q, r):
                    if in_bounds(nq, nr, W, H) and height[nr, nq] < sea_level:
                        coast = True; break
                out[r, q] = COAST if coast else GRASS
    return out
