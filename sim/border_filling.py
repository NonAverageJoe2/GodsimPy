"""Smart border filling for enclosed territories."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from typing import List, Tuple, Set
from collections import deque


def get_neighbors_4connected(r: int, c: int, h: int, w: int) -> List[Tuple[int, int]]:
    """Get 4-connected neighbors (up, down, left, right) for flood fill."""
    neighbors = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            neighbors.append((nr, nc))
    return neighbors


def flood_fill_component(start_r: int, start_c: int, 
                        owner_map: NDArray[np.int32], 
                        visited: NDArray[np.bool_]) -> List[Tuple[int, int]]:
    """Flood fill to find all tiles in a connected component of unowned territory."""
    h, w = owner_map.shape
    component = []
    queue = deque([(start_r, start_c)])
    visited[start_r, start_c] = True
    
    while queue:
        r, c = queue.popleft()
        component.append((r, c))
        
        for nr, nc in get_neighbors_4connected(r, c, h, w):
            if not visited[nr, nc] and owner_map[nr, nc] < 0:  # Unowned
                visited[nr, nc] = True
                queue.append((nr, nc))
    
    return component


def get_surrounding_owners(component: List[Tuple[int, int]], 
                          owner_map: NDArray[np.int32]) -> List[int]:
    """Find all civilization IDs that border this component."""
    h, w = owner_map.shape
    surrounding_owners = set()
    
    for r, c in component:
        for nr, nc in get_neighbors_4connected(r, c, h, w):
            owner = owner_map[nr, nc]
            if owner >= 0:  # Owned territory
                surrounding_owners.add(int(owner))
    
    return list(surrounding_owners)


def is_small_enclosed_area(component: List[Tuple[int, int]], 
                          surrounding_owners: List[int],
                          max_size: int = 10) -> bool:
    """Check if this is a small area that should be filled.
    
    Criteria:
    - Small size (≤ max_size tiles)
    - Surrounded by a single civilization
    """
    if len(component) > max_size:
        return False
        
    if len(surrounding_owners) != 1:
        return False  # Must be surrounded by exactly one civ
        
    return True


def fill_enclosed_territories(owner_map: NDArray[np.int32], 
                            biome_map: NDArray[np.uint8],
                            max_fill_size: int = 8) -> NDArray[np.int32]:
    """Fill small enclosed unowned territories with the surrounding civilization.
    
    Args:
        owner_map: Territory ownership (-1 = unowned)
        biome_map: Biome types (for reference)
        max_fill_size: Maximum size of areas to fill
        
    Returns:
        Updated owner_map with enclosed areas filled
    """
    h, w = owner_map.shape
    result_owner = owner_map.copy()
    visited = np.zeros((h, w), dtype=bool)
    
    # Find all unowned components
    for r in range(h):
        for c in range(w):
            if owner_map[r, c] < 0 and not visited[r, c]:
                # Found unvisited unowned tile - flood fill the component
                component = flood_fill_component(r, c, owner_map, visited)
                
                # Check if this component should be filled
                surrounding_owners = get_surrounding_owners(component, owner_map)
                
                if is_small_enclosed_area(component, surrounding_owners, max_fill_size):
                    # Fill this component with the surrounding owner
                    fill_owner = surrounding_owners[0]
                    for cr, cc in component:
                        result_owner[cr, cc] = fill_owner
    
    return result_owner


def fill_water_bodies(owner_map: NDArray[np.int32], 
                     biome_map: NDArray[np.uint8]) -> NDArray[np.int32]:
    """Fill enclosed water bodies (lakes) with the surrounding civilization.
    
    This specifically targets water areas (ocean/coast) that are completely
    enclosed by a single civilization.
    """
    h, w = owner_map.shape
    result_owner = owner_map.copy()
    visited = np.zeros((h, w), dtype=bool)
    
    # Find water areas that are unowned
    for r in range(h):
        for c in range(w):
            biome = biome_map[r, c]
            if (biome in [1, 3] and  # Coast or ocean
                owner_map[r, c] < 0 and  # Unowned
                not visited[r, c]):
                
                # Flood fill the water body
                component = flood_fill_component(r, c, owner_map, visited)
                surrounding_owners = get_surrounding_owners(component, owner_map)
                
                # Fill if completely enclosed by one civ (regardless of size)
                if len(surrounding_owners) == 1:
                    fill_owner = surrounding_owners[0]
                    for cr, cc in component:
                        result_owner[cr, cc] = fill_owner
    
    return result_owner


def apply_smart_borders(owner_map: NDArray[np.int32], 
                       biome_map: NDArray[np.uint8]) -> NDArray[np.int32]:
    """Apply smart border filling for both land enclaves and water bodies.
    
    This combines both types of border filling for a complete solution.
    """
    # First fill small enclosed land areas
    result = fill_enclosed_territories(owner_map, biome_map, max_fill_size=6)
    
    # Then fill enclosed water bodies
    result = fill_water_bodies(result, biome_map)
    
    return result