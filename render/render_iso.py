# render_iso.py - seam-free, flat-top, corner-camera “fake 3D” isometric renderer
from __future__ import annotations
import math
import numpy as np
from PIL import Image, ImageDraw
from worldgen.hexgrid import axial_to_world_flat

COLORS = [
    (int(0.15*255), int(0.50*255), int(0.15*255)),  # Grass - darker
    (int(0.70*255), int(0.60*255), int(0.18*255)),  # Coast/Desert - less bright
    (int(0.45*255), int(0.45*255), int(0.45*255)),  # Mountain - darker
    (int(0.03*255), int(0.10*255), int(0.35*255)),  # Ocean - deeper
]

def _rot_y(yaw): c,s = math.cos(yaw), math.sin(yaw); return np.array([[c,0,s],[0,1,0],[-s,0,c]], np.float32)
def _rot_x(pit): c,s = math.cos(pit), math.sin(pit); return np.array([[1,0,0],[0,c,-s],[0,s,c]], np.float32)

def _hex_prism(x: float, z: float, radius: float, hpx: float):
    base, top = [], []
    for i in range(6):
        ang = math.radians(60*i)  # flat-top, i=0 along +X
        px = x + math.cos(ang) * radius
        pz = z + math.sin(ang) * radius
        base.append([px, 0.0, pz])
        top.append([px, hpx, pz])
    return np.array(base, np.float32), np.array(top, np.float32)

def _project(P: np.ndarray) -> np.ndarray:
    return np.stack([P[:,0], -P[:,1]], axis=1)

def render_iso(
    height: np.ndarray,
    biome: np.ndarray,
    radius: float,
    sea_level: float = 0.0,
    height_pixels: float = 36.0,
    yaw_deg: float = 45.0,
    tilt_deg: float = 35.264,
    supersample: int = 1,
    zoom: float = 1.0,
) -> Image.Image:
    """Render a simple corner-view isometric projection.

    ``sea_level`` is subtracted from the height map so that ocean tiles
    appear flat while land rises above the water level.  This makes the
    height differences visible in the final render.
    """

    H, W = height.shape
    R = _rot_x(math.radians(tilt_deg)) @ _rot_y(math.radians(yaw_deg))

    # Apply zoom to radius and height_pixels
    radius *= zoom
    height_pixels *= zoom

    # canvas bounds
    xs, ys = [], []
    for (q, r) in ((0,0),(W-1,0),(0,H-1),(W-1,H-1)):
        x, z = axial_to_world_flat(q, r, radius)
        P = np.array([[x, 0.0, z],[x, height_pixels, z]], np.float32)
        Pc = (R @ P.T).T; S = _project(Pc)
        xs += [S[0,0], S[1,0]]; ys += [S[0,1], S[1,1]]
    pad = radius * 3
    minx, maxx = min(xs)-pad, max(xs)+pad
    miny, maxy = min(ys)-pad, max(ys)+pad
    img_w = int(math.ceil((maxx - minx))) * supersample
    img_h = int(math.ceil((maxy - miny))) * supersample
    offx, offy = minx, miny

    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img, "RGBA")

    def to_img(pt):
        # snap to integer to avoid half-pixel seams (with supersampling factor)
        x = int(round((pt[0] - offx) * supersample))
        y = int(round((pt[1] - offy) * supersample))
        return (x, y)

    def shade(color, k):
        k = 0.0 if k < 0.0 else 1.0 if k > 1.0 else k
        r,g,b = color
        return (int(r * (0.35 + 0.35*k)),  # Reduced base lighting
                int(g * (0.35 + 0.35*k)),  # and reduced range
                int(b * (0.35 + 0.35*k)), 255)

    # order: back-to-front by (q+r, q)
    order = [(q + r, q, r) for r in range(H) for q in range(W)]
    order.sort()

    for _, q, r in order:
        # Normalize height relative to sea level so water stays flat
        h01 = float(max(height[r, q] - sea_level, 0.0))
        hpx = max(h01 * height_pixels, 1.0)
        x, z = axial_to_world_flat(q, r, radius)
        base, top = _hex_prism(x, z, radius, hpx)
        base_c = (R @ base.T).T; top_c = (R @ top.T).T
        base_s = np.array([to_img(p) for p in _project(base_c)], np.int32)
        top_s  = np.array([to_img(p) for p in _project(top_c)],  np.int32)
        b = int(biome[r, q]); b = 0 if b < 0 or b >= len(COLORS) else b
        col = COLORS[b]

        # two front faces for corner view: (5-0) and (0-1)
        faceA = [tuple(top_s[5]), tuple(top_s[0]), tuple(base_s[0]), tuple(base_s[5])]
        faceB = [tuple(top_s[0]), tuple(top_s[1]), tuple(base_s[1]), tuple(base_s[0])]
        draw.polygon(faceA, fill=shade(col, 0.65))
        draw.polygon(faceB, fill=shade(col, 0.45))

        # top last
        top_poly = [tuple(p) for p in top_s.tolist()]
        draw.polygon(top_poly, fill=(col[0], col[1], col[2], 255))

    if supersample > 1:
        img = img.resize((img_w // supersample, img_h // supersample), Image.BILINEAR)
    return img

def render_iso_heightmap(
    height: np.ndarray,
    radius: float,
    sea_level: float = 0.0,
    height_pixels: float = 36.0,
    yaw_deg: float = 45.0,
    tilt_deg: float = 35.264,
    supersample: int = 1,
    zoom: float = 1.0,
) -> Image.Image:
    """Render isometric heightmap with elevation-based colors."""
    H, W = height.shape
    R = _rot_x(math.radians(tilt_deg)) @ _rot_y(math.radians(yaw_deg))

    radius *= zoom
    height_pixels *= zoom

    # canvas bounds
    xs, ys = [], []
    for (q, r) in ((0,0),(W-1,0),(0,H-1),(W-1,H-1)):
        x, z = axial_to_world_flat(q, r, radius)
        P = np.array([[x, 0.0, z],[x, height_pixels, z]], np.float32)
        Pc = (R @ P.T).T; S = _project(Pc)
        xs += [S[0,0], S[1,0]]; ys += [S[0,1], S[1,1]]
    pad = radius * 3
    minx, maxx = min(xs)-pad, max(xs)+pad
    miny, maxy = min(ys)-pad, max(ys)+pad
    img_w = int(math.ceil((maxx - minx))) * supersample
    img_h = int(math.ceil((maxy - miny))) * supersample
    offx, offy = minx, miny

    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img, "RGBA")

    def to_img(pt):
        x = int(round((pt[0] - offx) * supersample))
        y = int(round((pt[1] - offy) * supersample))
        return (x, y)

    def shade(color, k):
        k = 0.0 if k < 0.0 else 1.0 if k > 1.0 else k
        r,g,b = color
        return (int(r * (0.35 + 0.35*k)),
                int(g * (0.35 + 0.35*k)),
                int(b * (0.35 + 0.35*k)), 255)

    # Normalize height for color mapping
    h_min, h_max = np.min(height), np.max(height)
    h_range = h_max - h_min if h_max > h_min else 1.0

    order = [(q + r, q, r) for r in range(H) for q in range(W)]
    order.sort()

    for _, q, r in order:
        h01 = float(max(height[r, q] - sea_level, 0.0))
        hpx = max(h01 * height_pixels, 1.0)
        x, z = axial_to_world_flat(q, r, radius)
        base, top = _hex_prism(x, z, radius, hpx)
        base_c = (R @ base.T).T; top_c = (R @ top.T).T
        base_s = np.array([to_img(p) for p in _project(base_c)], np.int32)
        top_s  = np.array([to_img(p) for p in _project(top_c)],  np.int32)
        
        # Height-based coloring
        h_norm = (height[r, q] - h_min) / h_range
        if h_norm < 0.2:  # Deep water
            col = (20, 50, 150)
        elif h_norm < 0.4:  # Shallow water/coast
            col = (50, 120, 180)
        elif h_norm < 0.6:  # Low land
            col = (100, 150, 80)
        elif h_norm < 0.8:  # Hills
            col = (120, 100, 60)
        else:  # Mountains
            col = (200, 200, 200)

        # two front faces
        faceA = [tuple(top_s[5]), tuple(top_s[0]), tuple(base_s[0]), tuple(base_s[5])]
        faceB = [tuple(top_s[0]), tuple(top_s[1]), tuple(base_s[1]), tuple(base_s[0])]
        draw.polygon(faceA, fill=shade(col, 0.65))
        draw.polygon(faceB, fill=shade(col, 0.45))

        # top
        top_poly = [tuple(p) for p in top_s.tolist()]
        draw.polygon(top_poly, fill=(col[0], col[1], col[2], 255))

    if supersample > 1:
        img = img.resize((img_w // supersample, img_h // supersample), Image.BILINEAR)
    return img
