"""EU4-style dynamic country labels for hex maps."""

from __future__ import annotations

import math
import pygame
import numpy as np
from typing import List, Tuple, Dict, Set, Optional
from dataclasses import dataclass
from collections import deque

# Label configuration constants
Z_COUNTRY = 0.8  # Only show country labels when zoomed out beyond this
PT_MIN = 12      # Minimum font size
PT_MAX = 48      # Maximum font size
A0 = 8           # Base font size coefficient
A1 = 2           # Area scaling coefficient


@dataclass
class Component:
    """A connected component of tiles belonging to one civilization."""
    civ_id: int
    tiles: List[Tuple[int, int]]  # List of (r, q) coordinates
    centroid: Tuple[float, float]  # World coordinates (x, y)
    pca_angle: float  # Principal axis angle in radians
    area: int  # Number of tiles
    is_largest: bool  # True if this is the largest component for this civ


def get_hex_neighbors(r: int, q: int, is_even_col: bool = True) -> List[Tuple[int, int]]:
    """Get 6-connected hex neighbors using even-q offset coordinates."""
    neighbors = []
    
    # Even-q offset neighbor offsets
    if q % 2 == 0:  # Even column
        offsets = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (0, -1)]
    else:  # Odd column
        offsets = [(-1, -1), (-1, 0), (0, 1), (1, 0), (1, -1), (0, -1)]
    
    for dr, dq in offsets:
        neighbors.append((r + dr, q + dq))
    
    return neighbors


def find_connected_components(owner_map: np.ndarray, biome_map: np.ndarray, 
                             civ_id: int, hex_radius: float, 
                             evenq_center_func) -> List[Component]:
    """Find all connected components for a given civilization."""
    h, w = owner_map.shape
    visited = np.zeros_like(owner_map, dtype=bool)
    components = []
    
    # Find all tiles belonging to this civilization
    civ_tiles = np.argwhere(owner_map == civ_id)
    
    for tile_r, tile_q in civ_tiles:
        r, q = int(tile_r), int(tile_q)
        
        if visited[r, q]:
            continue
            
        # BFS to find connected component
        component_tiles = []
        queue = deque([(r, q)])
        visited[r, q] = True
        
        while queue:
            cur_r, cur_q = queue.popleft()
            component_tiles.append((cur_r, cur_q))
            
            # Check neighbors
            for nr, nq in get_hex_neighbors(cur_r, cur_q):
                if (0 <= nr < h and 0 <= nq < w and 
                    not visited[nr, nq] and 
                    owner_map[nr, nq] == civ_id):
                    visited[nr, nq] = True
                    queue.append((nr, nq))
        
        if not component_tiles:
            continue
            
        # Filter out pure-ocean components
        has_land = any(biome_map[r, q] != 3 for r, q in component_tiles)
        if not has_land:
            continue
            
        # Compute centroid in world coordinates
        world_centers = [evenq_center_func(q, r, hex_radius) for r, q in component_tiles]
        centroid_x = sum(x for x, y in world_centers) / len(world_centers)
        centroid_y = sum(y for x, y in world_centers) / len(world_centers)
        
        # Compute PCA angle
        pca_angle = compute_pca_angle(world_centers, (centroid_x, centroid_y))
        
        component = Component(
            civ_id=civ_id,
            tiles=component_tiles,
            centroid=(centroid_x, centroid_y),
            pca_angle=pca_angle,
            area=len(component_tiles),
            is_largest=False
        )
        components.append(component)
    
    # Mark largest component
    if components:
        largest = max(components, key=lambda c: c.area)
        largest.is_largest = True
    
    return components


def compute_pca_angle(world_centers: List[Tuple[float, float]], 
                     centroid: Tuple[float, float]) -> float:
    """Compute principal component angle using 2x2 covariance matrix."""
    if len(world_centers) <= 1:
        return 0.0
        
    cx, cy = centroid
    
    # Compute covariance matrix elements
    cxx = cxy = cyy = 0.0
    n = len(world_centers)
    
    for x, y in world_centers:
        dx, dy = x - cx, y - cy
        cxx += dx * dx
        cxy += dx * dy
        cyy += dy * dy
    
    cxx /= n
    cxy /= n
    cyy /= n
    
    # Handle degenerate cases
    if abs(cxx) < 1e-10 and abs(cyy) < 1e-10:
        return 0.0
        
    # Compute principal eigenvector angle
    # For 2x2 symmetric matrix [[cxx, cxy], [cxy, cyy]]
    trace = cxx + cyy
    det = cxx * cyy - cxy * cxy
    
    if abs(det) < 1e-10:  # Nearly singular
        return 0.0 if abs(cxy) < 1e-10 else math.atan2(cxy, cxx)
    
    # Eigenvalues: lambda = (trace ± sqrt(trace² - 4*det)) / 2
    discriminant = trace * trace - 4 * det
    if discriminant < 0:
        return 0.0
        
    sqrt_disc = math.sqrt(discriminant)
    lambda1 = (trace + sqrt_disc) / 2
    lambda2 = (trace - sqrt_disc) / 2
    
    # Use the larger eigenvalue's eigenvector
    primary_lambda = lambda1 if lambda1 > lambda2 else lambda2
    
    # Eigenvector for primary eigenvalue: [cxy, primary_lambda - cxx]
    if abs(cxy) > 1e-10:
        return math.atan2(primary_lambda - cxx, cxy)
    elif abs(primary_lambda - cxx) > 1e-10:
        return math.pi / 2 if (primary_lambda - cxx) > 0 else -math.pi / 2
    else:
        return 0.0


def compute_font_size(area: int, camera_zoom: float) -> int:
    """Compute font size based on component area and camera zoom."""
    pt = A0 + A1 * math.sqrt(max(1, area)) * camera_zoom
    return int(max(PT_MIN, min(PT_MAX, pt)))


def render_text_with_outline(text: str, font: pygame.font.Font, 
                           text_color: Tuple[int, int, int] = (255, 255, 255),
                           outline_color: Tuple[int, int, int] = (0, 0, 0),
                           outline_width: int = 2) -> pygame.Surface:
    """Render text with outline border."""
    # Create surfaces
    text_surface = font.render(text, True, text_color)
    text_rect = text_surface.get_rect()
    
    # Create outline surface (larger to accommodate border)
    outline_size = (text_rect.width + 2 * outline_width, 
                   text_rect.height + 2 * outline_width)
    outline_surface = pygame.Surface(outline_size, pygame.SRCALPHA)
    
    # Draw outline by rendering text at multiple offset positions
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:  # Skip center position
                outline_text = font.render(text, True, outline_color)
                outline_surface.blit(outline_text, 
                                   (outline_width + dx, outline_width + dy))
    
    # Draw main text on top
    outline_surface.blit(text_surface, (outline_width, outline_width))
    
    return outline_surface


def rotate_surface(surface: pygame.Surface, angle_degrees: float) -> pygame.Surface:
    """Rotate a surface by the given angle in degrees."""
    return pygame.transform.rotate(surface, -math.degrees(angle_degrees))


def fits_in_component(surface: pygame.Surface, component: Component, 
                     camera, screen_width: int, screen_height: int,
                     hex_radius: float, evenq_center_func) -> bool:
    """Check if rotated text surface fits within the component bounds."""
    # Get surface dimensions
    surf_width, surf_height = surface.get_size()
    
    # Convert component tiles to screen space
    screen_tiles = []
    for r, q in component.tiles:
        wx, wy = evenq_center_func(q, r, hex_radius)
        sx, sy = camera.world_to_screen(wx, wy, screen_width, screen_height)
        screen_tiles.append((sx, sy))
    
    if not screen_tiles:
        return False
    
    # Get component bounding box in screen space
    min_x = min(x for x, y in screen_tiles)
    max_x = max(x for x, y in screen_tiles)
    min_y = min(y for x, y in screen_tiles)
    max_y = max(y for x, y in screen_tiles)
    
    # Check if text fits in bounding box
    component_width = max_x - min_x
    component_height = max_y - min_y
    
    return (surf_width <= component_width * 0.8 and 
            surf_height <= component_height * 0.8)


class CountryLabelRenderer:
    """Renders EU4-style dynamic country labels."""
    
    def __init__(self):
        self.font_cache: Dict[int, pygame.font.Font] = {}
        
    def get_font(self, size: int) -> pygame.font.Font:
        """Get cached font of given size."""
        if size not in self.font_cache:
            self.font_cache[size] = pygame.font.Font(None, size)
        return self.font_cache[size]
        
    def render_country_labels(self, surface: pygame.Surface, world_state, civs: List,
                            camera, hex_radius: float, evenq_center_func):
        """Render all country labels with EU4-style positioning and rotation."""
        # Only show country labels when zoomed out
        if camera.zoom > Z_COUNTRY:
            return
            
        screen_width, screen_height = surface.get_size()
        
        # Find components for each civilization
        all_components = []
        for civ in civs:
            if civ.id < 0:
                continue
                
            components = find_connected_components(
                world_state.owner_map, world_state.biome_map, 
                civ.id, hex_radius, evenq_center_func
            )
            all_components.extend(components)
        
        # Render labels for largest components only
        for component in all_components:
            if not component.is_largest:
                continue
                
            civ = civs[component.civ_id]
            
            # Compute font size
            font_size = compute_font_size(component.area, camera.zoom)
            font = self.get_font(font_size)
            
            # Render text with outline
            text_surface = render_text_with_outline(civ.name, font)
            
            # Rotate by PCA angle
            rotated_surface = rotate_surface(text_surface, component.pca_angle)
            
            # Check if it fits
            if not fits_in_component(rotated_surface, component, camera, 
                                   screen_width, screen_height, hex_radius, evenq_center_func):
                continue
                
            # Convert centroid to screen coordinates
            cx_screen, cy_screen = camera.world_to_screen(
                component.centroid[0], component.centroid[1], 
                screen_width, screen_height
            )
            
            # Center the text on the centroid
            text_rect = rotated_surface.get_rect()
            text_rect.center = (int(cx_screen), int(cy_screen))
            
            # Only draw if on screen
            if (text_rect.right > 0 and text_rect.left < screen_width and
                text_rect.bottom > 0 and text_rect.top < screen_height):
                surface.blit(rotated_surface, text_rect)