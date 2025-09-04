from __future__ import annotations

import math
import os
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from worldgen.hexgrid import axial_to_world_flat

# Biome color palette: grass, coast/desert, mountain, ocean
BIOME_COLORS = [
    (int(0.20 * 255), int(0.70 * 255), int(0.20 * 255)),
    (int(0.95 * 255), int(0.85 * 255), int(0.25 * 255)),
    (int(0.60 * 255), int(0.60 * 255), int(0.60 * 255)),
    (int(0.05 * 255), int(0.15 * 255), int(0.45 * 255)),
]

# Semi-transparent ownership tints cycled by civ id
OWNER_TINTS = [
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 165, 0),
]


def _hex_points(cx: float, cz: float, radius: float) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(6):
        ang = math.radians(60 * i)
        x = cx + math.cos(ang) * radius
        z = cz + math.sin(ang) * radius
        pts.append((x, z))
    return pts


def render_topdown(world, path_png: str) -> None:
    """Render a top-down biome map with ownership tint overlay."""

    w, h = world.width_hex, world.height_hex
    radius = world.hex_size

    # Image bounds from map corners
    xs: List[float] = []
    ys: List[float] = []
    for (q, r) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        x, z = axial_to_world_flat(q, r, radius)
        xs.extend([x - radius, x + radius])
        ys.extend([z - radius, z + radius])
    pad = radius * 3
    minx, maxx = min(xs) - pad, max(xs) + pad
    miny, maxy = min(ys) - pad, max(ys) + pad
    img_w = int(maxx - minx)
    img_h = int(maxy - miny)

    img = Image.new("RGBA", (img_w, img_h), (16, 18, 24, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    for t in world.tiles:
        cx, cz = axial_to_world_flat(t.q, t.r, radius)
        pts = _hex_points(cx, cz, radius)
        pts = [(x - minx, z - miny) for (x, z) in pts]
        b = int(t.biome)
        b = 0 if b < 0 or b >= len(BIOME_COLORS) else b
        draw.polygon(pts, fill=BIOME_COLORS[b])
        if t.owner is not None:
            col = OWNER_TINTS[t.owner % len(OWNER_TINTS)]
            draw.polygon(pts, fill=(col[0], col[1], col[2], 96))

    os.makedirs(os.path.dirname(path_png) or ".", exist_ok=True)
    img.save(path_png)


# ---- Isometric rendering helpers -------------------------------------------------

def _rot_y(yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float32)


def _rot_x(pit: float) -> np.ndarray:
    c, s = math.cos(pit), math.sin(pit)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float32)


def _hex_prism(x: float, z: float, radius: float, hpx: float):
    base: List[List[float]] = []
    top: List[List[float]] = []
    for i in range(6):
        ang = math.radians(60 * i)
        px = x + math.cos(ang) * radius
        pz = z + math.sin(ang) * radius
        base.append([px, 0.0, pz])
        top.append([px, hpx, pz])
    return np.array(base, np.float32), np.array(top, np.float32)


def _project(P: np.ndarray) -> np.ndarray:
    return np.stack([P[:, 0], -P[:, 1]], axis=1)


def render_isometric(
    world,
    path_png: str,
    height_pixels: float = 36.0,
    yaw_deg: float = 45.0,
    tilt_deg: float = 35.264,
    supersample: int = 1,
) -> None:
    """Render a simple corner-view isometric projection of the world."""

    H, W = world.height_hex, world.width_hex
    radius = world.hex_size

    height = np.zeros((H, W), dtype=np.float32)
    biome = np.zeros((H, W), dtype=np.int32)
    for t in world.tiles:
        height[t.r, t.q] = float(t.height)
        biome[t.r, t.q] = int(t.biome)

    R = _rot_x(math.radians(tilt_deg)) @ _rot_y(math.radians(yaw_deg))

    xs: List[float] = []
    ys: List[float] = []
    for (q, r) in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        x, z = axial_to_world_flat(q, r, radius)
        P = np.array([[x, 0.0, z], [x, height_pixels, z]], np.float32)
        Pc = (R @ P.T).T
        S = _project(Pc)
        xs += [S[0, 0], S[1, 0]]
        ys += [S[0, 1], S[1, 1]]
    pad = radius * 3
    minx, maxx = min(xs) - pad, max(xs) + pad
    miny, maxy = min(ys) - pad, max(ys) + pad
    img_w = int(math.ceil((maxx - minx))) * supersample
    img_h = int(math.ceil((maxy - miny))) * supersample
    offx, offy = minx, miny

    img = Image.new("RGBA", (img_w, img_h), (16, 18, 24, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    def to_img(pt: np.ndarray) -> Tuple[int, int]:
        x = int(round((pt[0] - offx) * supersample))
        y = int(round((pt[1] - offy) * supersample))
        return (x, y)

    def shade(color: Tuple[int, int, int], k: float) -> Tuple[int, int, int, int]:
        k = 0.0 if k < 0.0 else 1.0 if k > 1.0 else k
        r, g, b = color
        return (
            int(r * (0.55 + 0.45 * k)),
            int(g * (0.55 + 0.45 * k)),
            int(b * (0.55 + 0.45 * k)),
            255,
        )

    order = [(q + r, q, r) for r in range(H) for q in range(W)]
    order.sort()

    for _, q, r in order:
        h01 = float(max(height[r, q], 0.0))
        hpx = max(h01 * height_pixels, 1.0)
        x, z = axial_to_world_flat(q, r, radius)
        base, top = _hex_prism(x, z, radius, hpx)
        base_c = (R @ base.T).T
        top_c = (R @ top.T).T
        base_s = np.array([to_img(p) for p in _project(base_c)], np.int32)
        top_s = np.array([to_img(p) for p in _project(top_c)], np.int32)
        b = int(biome[r, q])
        b = 0 if b < 0 or b >= len(BIOME_COLORS) else b
        col = BIOME_COLORS[b]

        faceA = [tuple(top_s[5]), tuple(top_s[0]), tuple(base_s[0]), tuple(base_s[5])]
        faceB = [tuple(top_s[0]), tuple(top_s[1]), tuple(base_s[1]), tuple(base_s[0])]
        draw.polygon(faceA, fill=shade(col, 0.65))
        draw.polygon(faceB, fill=shade(col, 0.45))

        top_poly = [tuple(p) for p in top_s.tolist()]
        draw.polygon(top_poly, fill=(col[0], col[1], col[2], 255))

    if supersample > 1:
        img = img.resize((img_w // supersample, img_h // supersample), Image.BILINEAR)

    os.makedirs(os.path.dirname(path_png) or ".", exist_ok=True)
    img.save(path_png)


__all__ = ["render_topdown", "render_isometric"]
