# render_topdown.py - simple top-down (2D) hex fill
from __future__ import annotations
from typing import Tuple
import math
import numpy as np
from PIL import Image, ImageDraw
from worldgen.hexgrid import axial_to_world_flat, SQRT3

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

def render_topdown(biome: np.ndarray, radius: float, scale: int = 4, zoom: float = 1.0) -> Image.Image:
    H, W = biome.shape
    
    # Calculate canvas bounds based on actual hex coordinates
    xs, ys = [], []
    for r in range(H):
        for q in range(W):
            x, z = axial_to_world_flat(q, r, radius)
            xs.append(x)
            ys.append(z)
    
    # Add padding around the hex grid
    padding = radius * 2
    min_x, max_x = min(xs) - padding, max(xs) + padding
    min_y, max_y = min(ys) - padding, max(ys) + padding
    total_width = max_x - min_x
    total_height = max_y - min_y
    
    # Apply zoom
    total_width *= zoom
    total_height *= zoom
    radius *= zoom
    min_x *= zoom
    min_y *= zoom
    
    img_w = int(total_width)
    img_h = int(total_height)
    
    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img)
    
    # Position hexes using proper hex coordinate math
    for r in range(H):
        for q in range(W):
            # Use proper axial-to-world coordinate conversion  
            x, z = axial_to_world_flat(q, r, radius)
            # Adjust for canvas bounds and zoom
            x = (x * zoom) - min_x
            y = (z * zoom) - min_y
            
            pts = hex_points_flat(x, y, radius)
            b = int(biome[r,q]); b = 0 if b < 0 or b >= len(COLORS) else b
            draw.polygon(pts, fill=COLORS[b])
    if scale > 1:
        img = img.resize((img_w*scale, img_h*scale), Image.NEAREST)
    return img

def render_topdown_height(height: np.ndarray, radius: float, scale: int = 4, zoom: float = 1.0) -> Image.Image:
    """Render height map in grayscale/elevation colors."""
    H, W = height.shape
    
    # Calculate canvas bounds based on actual hex coordinates
    xs, ys = [], []
    for r in range(H):
        for q in range(W):
            x, z = axial_to_world_flat(q, r, radius)
            xs.append(x)
            ys.append(z)
    
    # Add padding around the hex grid
    padding = radius * 2
    min_x, max_x = min(xs) - padding, max(xs) + padding
    min_y, max_y = min(ys) - padding, max(ys) + padding
    total_width = max_x - min_x
    total_height = max_y - min_y
    
    # Apply zoom
    total_width *= zoom
    total_height *= zoom
    radius *= zoom
    min_x *= zoom
    min_y *= zoom
    
    img_w = int(total_width)
    img_h = int(total_height)
    
    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img)
    
    # Normalize height to 0-1 range
    h_min, h_max = np.min(height), np.max(height)
    h_range = h_max - h_min if h_max > h_min else 1.0
    
    for r in range(H):
        for q in range(W):
            # Use proper axial-to-world coordinate conversion
            x, z = axial_to_world_flat(q, r, radius)
            # Adjust for canvas bounds and zoom
            x = (x * zoom) - min_x
            y = (z * zoom) - min_y
            
            pts = hex_points_flat(x, y, radius)
            
            # Convert height to color (blue=low, green=mid, brown=high, white=peak)
            h_norm = (height[r, q] - h_min) / h_range
            if h_norm < 0.2:  # Deep water
                color = (int(20), int(50), int(150))
            elif h_norm < 0.4:  # Shallow water/coast
                color = (int(50), int(120), int(180))
            elif h_norm < 0.6:  # Low land
                color = (int(100), int(150), int(80))
            elif h_norm < 0.8:  # Hills
                color = (int(120), int(100), int(60))
            else:  # Mountains
                color = (int(200), int(200), int(200))
            
            draw.polygon(pts, fill=color)
    
    if scale > 1:
        img = img.resize((img_w*scale, img_h*scale), Image.NEAREST)
    return img

def render_topdown_political(biome: np.ndarray, radius: float, scale: int = 4, zoom: float = 1.0) -> Image.Image:
    """Render with distinct political/regional colors."""
    POLITICAL_COLORS = [
        (120, 160, 120),  # Light green
        (200, 180, 100),  # Gold
        (140, 100, 180),  # Purple  
        (80, 140, 200),   # Blue
        (200, 120, 100),  # Orange-red
        (100, 180, 140),  # Teal
        (180, 140, 100),  # Brown
        (160, 120, 160),  # Lavender
    ]
    
    H, W = biome.shape
    
    # Calculate canvas bounds based on actual hex coordinates
    xs, ys = [], []
    for r in range(H):
        for q in range(W):
            x, z = axial_to_world_flat(q, r, radius)
            xs.append(x)
            ys.append(z)
    
    # Add padding around the hex grid
    padding = radius * 2
    min_x, max_x = min(xs) - padding, max(xs) + padding
    min_y, max_y = min(ys) - padding, max(ys) + padding
    total_width = max_x - min_x
    total_height = max_y - min_y
    
    # Apply zoom
    total_width *= zoom
    total_height *= zoom
    radius *= zoom
    min_x *= zoom
    min_y *= zoom
    
    img_w = int(total_width)
    img_h = int(total_height)
    
    img = Image.new("RGBA", (img_w, img_h), (16,18,24,255))
    draw = ImageDraw.Draw(img)
    
    for r in range(H):
        for q in range(W):
            # Use proper axial-to-world coordinate conversion
            x, z = axial_to_world_flat(q, r, radius)
            # Adjust for canvas bounds and zoom
            x = (x * zoom) - min_x
            y = (z * zoom) - min_y
            
            pts = hex_points_flat(x, y, radius)
            b = int(biome[r,q]) % len(POLITICAL_COLORS)
            draw.polygon(pts, fill=POLITICAL_COLORS[b])
    
    if scale > 1:
        img = img.resize((img_w*scale, img_h*scale), Image.NEAREST)
    return img
