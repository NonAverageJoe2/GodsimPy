# noise.py - tiny value-noise FBM for terrain
from __future__ import annotations
import numpy as np

def value_noise(width: int, height: int, scale=24, octaves=5, persistence=0.55, lacunarity=2.1, seed=0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    out = np.zeros((height, width), dtype=np.float32)
    amp = 1.0
    freq = 1.0 / float(scale)
    total = 0.0
    for _ in range(octaves):
        gw = max(2, int(width * freq) + 2)
        gh = max(2, int(height * freq) + 2)
        grid = rng.rand(gh, gw).astype(np.float32)
        y = np.linspace(0, gh - 1, height, dtype=np.float32)
        x = np.linspace(0, gw - 1, width, dtype=np.float32)
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
        x1 = np.clip(x0 + 1, 0, gw - 1); y1 = np.clip(y0 + 1, 0, gh - 1)
        xs = (x - x0)[None, :]; ys = (y - y0)[:, None]
        g00 = grid[y0[:, None], x0[None, :]]
        g10 = grid[y0[:, None], x1[None, :]]
        g01 = grid[y1[:, None], x0[None, :]]
        g11 = grid[y1[:, None], x1[None, :]]
        gx0 = g00 * (1 - xs) + g10 * xs
        gx1 = g01 * (1 - xs) + g11 * xs
        up = gx0 * (1 - ys) + gx1 * ys
        out += up * amp
        total += amp
        amp *= persistence
        freq *= lacunarity
    if total > 0:
        out /= total
    return out
