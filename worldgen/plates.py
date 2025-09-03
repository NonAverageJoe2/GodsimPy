# plates.py - Voronoi plates + velocities + boundary forces
from __future__ import annotations
import math, random
import numpy as np
from typing import Dict, Tuple
from .hexgrid import axial_to_world_flat

def generate_plates(w: int, h: int, plate_count: int, radius: float, seed: int):
    rng = random.Random(seed)
    sites = set()
    while len(sites) < plate_count:
        sites.add((rng.randrange(w), rng.randrange(h)))
    sites = list(sites)

    vels: Dict[int, Tuple[float,float]] = {}
    for i, _ in enumerate(sites):
        ang = rng.random() * math.tau
        mag = 0.4 + rng.random() * 0.6
        vels[i] = (math.cos(ang) * mag, math.sin(ang) * mag)

    # world positions for sites
    site_pos = [axial_to_world_flat(q, r, radius) for (q, r) in sites]
    # assign Voronoi plates
    plate_map = np.zeros((h, w), dtype=np.int32)
    XZ = np.zeros((h, w, 2), dtype=np.float32)
    for r in range(h):
        for q in range(w):
            x, z = axial_to_world_flat(q, r, radius)
            XZ[r, q, 0] = x; XZ[r, q, 1] = z
            best = 0; best_d2 = 1e18
            for k, (sx, sz) in enumerate(site_pos):
                d2 = (x - sx)**2 + (z - sz)**2
                if d2 < best_d2:
                    best = k; best_d2 = d2
            plate_map[r, q] = best
    return plate_map, vels, XZ

def apply_plate_forces(height: np.ndarray, plate_map: np.ndarray, vels, XZ: np.ndarray,
                       w: int, h: int, seed: int,
                       conv_gain=0.35, div_gain=0.12, threshold=0.06):
    rng = np.random.RandomState(seed + 9999)
    height += (rng.rand(h, w).astype(np.float32) - 0.5) * 0.02  # tiny jitter

    # Scan half the edges to avoid double-counting
    for r in range(h):
        for q in range(w):
            pid = int(plate_map[r, q]); vx, vz = vels[pid]
            x0, z0 = XZ[r, q]
            for dq, dr in ((+1,0),(0,-1),(-1,+1)):
                nq, nr = q + dq, r + dr
                if not (0 <= nq < w and 0 <= nr < h):
                    continue
                nid = int(plate_map[nr, nq])
                if nid == pid:  # same plate
                    continue
                nvx, nvz = vels[nid]
                x1, z1 = XZ[nr, nq]
                ex, ez = x1 - x0, z1 - z0
                el = math.hypot(ex, ez)
                if el == 0.0:
                    continue
                ex /= el; ez /= el
                nx, nz = -ez, ex
                rvx, rvz = vx - nvx, vz - nvz
                dot = rvx * nx + rvz * nz
                if dot > threshold:  # convergent
                    d = (dot - threshold) * conv_gain
                    height[r, q] += d * 0.5
                    height[nr, nq] += d * 0.5
                elif dot < -threshold:  # divergent
                    d = (-threshold - dot) * div_gain
                    height[r, q] -= d * 0.5
                    height[nr, nq] -= d * 0.5
