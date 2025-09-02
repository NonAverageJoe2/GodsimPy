# render_topdown.py - simple top-down (2D) hex fill
from __future__ import annotations
from typing import Tuple
import numpy as np
from PIL import Image, ImageDraw
from hexgrid import axial_to_world_flat

COLORS = [
    (int(0.20*255), int(0.70*255), int(0.20*255)),  # Grass
    (int(0.95*255), int(0.85*255), int(0.25*255)),  # Coast/Desert
    (int(0.60*255), int(0.60*255), int(0.60*255)),  # Mountain
    (int(0.05*255), int(0.15*255), int(0.45*255)),  # Ocean
]

def hex_points_flat(cx: float, cz: float, radius: float):
    import math
    pts = []
    for i in range(6):
        ang = math.radians(60*i)
        x = cx + math.cos(ang) * radius
        z = cz + math.sin(ang) * radius
        pts.append((x, z))
    return pts

def render_topdown(biome: np.ndarray, radius: float, scale: int = 4) -> Image.Image:
    H, W = biome.shape
    # bounds
    xs, ys = [], []
    for (q, r) in ((0,0),(W-1,0),(0,H-1),(W-1,H-1)):
        x, z = axial_to_world_flat(q, r, radius)
        xs.extend([x-radius, x+radius]); ys.extend([z-radius, z+radius])
    pad = radius * 3
    minx, maxx = min(xs)-pad, max(xs)+pad
    miny, maxy = min(ys)-pad, max(ys)+pad
    img_w = int((maxx-minx)); img_h = int((maxy-miny))
    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img)
    for r in range(H):
        for q in range(W):
            cx, cz = axial_to_world_flat(q, r, radius)
            pts = hex_points_flat(cx, cz, radius)
            pts = [(x-minx, z-miny) for (x,z) in pts]
            b = int(biome[r,q]); b = 0 if b < 0 or b >= len(COLORS) else b
            draw.polygon(pts, fill=COLORS[b])
    if scale > 1:
        img = img.resize((img_w*scale, img_h*scale), Image.NEAREST)
    return img
