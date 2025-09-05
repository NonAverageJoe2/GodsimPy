"""Culture and religion system for civilization simulation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from typing import List, Tuple, Dict
from dataclasses import dataclass
import colorsys


@dataclass
class Culture:
    """Represents a culture with its characteristics."""
    id: int
    name: str
    color: Tuple[int, int, int]
    origin: Tuple[int, int]  # (r, c) where this culture originated
    linguistic_type: str = "latin"  # Default linguistic pattern
    

@dataclass 
class Religion:
    """Represents a religion with its characteristics."""
    id: int
    name: str
    color: Tuple[int, int, int]
    symbol: str  # Simple text symbol for now
    origin: Tuple[int, int]  # (r, c) where this religion originated


def generate_culture_names(count: int) -> List[str]:
    """Generate culture names."""
    base_names = [
        "Arcani", "Berani", "Celan", "Doran", "Elvan", "Fyran", "Gular", "Hestan",
        "Ithar", "Jolan", "Kethir", "Lysan", "Moran", "Nalar", "Orvani", "Pelan",
        "Qiran", "Rylos", "Solan", "Tular", "Uvan", "Velar", "Wyran", "Xylan",
        "Yvar", "Zelan", "Aveli", "Birin", "Colar", "Dyran", "Eshan", "Folar"
    ]
    
    if count <= len(base_names):
        return base_names[:count]
    
    # Generate additional names if needed
    names = base_names.copy()
    for i in range(count - len(base_names)):
        names.append(f"Culture {chr(65 + i)}")
    
    return names[:count]


def generate_religion_names(count: int) -> List[str]:
    """Generate religion names."""
    base_names = [
        "Solanism", "Lunaris", "Terrath", "Aqueth", "Pyrion", "Venthi", "Umbrism", "Aurion",
        "Crystalism", "Voidism", "Naturae", "Mechanis", "Ethereal", "Primordial", "Astral", "Mystic",
        "Harmony", "Order", "Chaos", "Balance", "Truth", "Wisdom", "Power", "Unity",
        "Light", "Shadow", "Storm", "Earth", "Fire", "Ice", "Wind", "Stone"
    ]
    
    if count <= len(base_names):
        return base_names[:count]
    
    # Generate additional names if needed
    names = base_names.copy()
    for i in range(count - len(base_names)):
        names.append(f"Faith {chr(65 + i)}")
    
    return names[:count]


def generate_religion_symbols(count: int) -> List[str]:
    """Generate simple text symbols for religions."""
    symbols = ["☀", "☽", "⚡", "🌊", "🔥", "❄", "🌪", "🗻", "✦", "◊", "☯", "⚖", "👁", "🔯", "☨", "☪",
               "◉", "◎", "◈", "◇", "◆", "◊", "○", "●", "□", "■", "△", "▲", "▽", "▼", "◁", "▷"]
    
    if count <= len(symbols):
        return symbols[:count]
        
    # Generate additional symbols if needed
    result = symbols.copy()
    for i in range(count - len(symbols)):
        result.append(str(i))
    
    return result[:count]


def create_palette(n: int, hue_offset: float = 0.0) -> List[Tuple[int, int, int]]:
    """Create a palette of n distinct colors."""
    colors = []
    for i in range(n):
        hue = (i / max(n, 1) + hue_offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.7, 0.9)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    return colors


def generate_culture_origins(h: int, w: int, num_cultures: int, 
                           biome_map: NDArray[np.uint8], 
                           seed: int = 0) -> List[Tuple[int, int]]:
    """Generate origin points for cultures, avoiding oceans and mountains."""
    rng = np.random.default_rng(seed)
    
    # Find valid land tiles (not ocean=3 or mountain=2)
    valid_mask = ~np.isin(biome_map, [2, 3])
    valid_coords = np.argwhere(valid_mask)
    
    if len(valid_coords) < num_cultures:
        raise ValueError(f"Not enough valid land for {num_cultures} cultures")
    
    # Select random origins with minimum distance apart
    origins = []
    min_distance = max(5, min(h, w) // (num_cultures + 2))
    
    max_attempts = 1000
    attempts = 0
    
    while len(origins) < num_cultures and attempts < max_attempts:
        attempts += 1
        candidate_idx = rng.integers(len(valid_coords))
        candidate = valid_coords[candidate_idx]
        r, c = candidate[0], candidate[1]
        
        # Check distance from existing origins
        too_close = False
        for existing_r, existing_c in origins:
            distance = max(abs(r - existing_r), abs(c - existing_c))
            if distance < min_distance:
                too_close = True
                break
        
        if not too_close:
            origins.append((int(r), int(c)))
        
        # Reduce distance requirement if struggling to place
        if attempts % 200 == 0:
            min_distance = max(2, min_distance - 1)
    
    # Fill remaining with random positions if needed
    while len(origins) < num_cultures:
        candidate_idx = rng.integers(len(valid_coords))
        candidate = valid_coords[candidate_idx]
        origins.append((int(candidate[0]), int(candidate[1])))
    
    return origins


def create_voronoi_map(h: int, w: int, origins: List[Tuple[int, int]]) -> NDArray[np.int32]:
    """Create a Voronoi diagram map based on origin points."""
    voronoi_map = np.full((h, w), -1, dtype=np.int32)
    
    for r in range(h):
        for c in range(w):
            min_distance = float('inf')
            closest_region = -1
            
            for i, (origin_r, origin_c) in enumerate(origins):
                # Use Chebyshev distance (max of horizontal/vertical distance)
                distance = max(abs(r - origin_r), abs(c - origin_c))
                
                if distance < min_distance:
                    min_distance = distance
                    closest_region = i
            
            voronoi_map[r, c] = closest_region
    
    return voronoi_map


def add_cultural_noise(culture_map: NDArray[np.int32], 
                      biome_map: NDArray[np.uint8],
                      noise_factor: float = 0.1, 
                      seed: int = 0) -> NDArray[np.int32]:
    """Add noise to create more organic cultural boundaries."""
    rng = np.random.default_rng(seed)
    h, w = culture_map.shape
    result = culture_map.copy()
    
    # Apply noise to non-ocean tiles
    land_mask = (biome_map != 3)
    
    for r in range(h):
        for c in range(w):
            if not land_mask[r, c]:
                continue
                
            if rng.random() < noise_factor:
                # Look at neighbors and possibly switch to a neighboring culture
                neighbors = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and (dr != 0 or dc != 0):
                            neighbors.append(culture_map[nr, nc])
                
                if neighbors:
                    # Randomly pick a neighbor's culture
                    result[r, c] = rng.choice(neighbors)
    
    return result


def create_cultures_and_religions(h: int, w: int, biome_map: NDArray[np.uint8], 
                                num_cultures: int = 8, num_religions: int = 5,
                                seed: int = 0) -> Tuple[List[Culture], List[Religion], 
                                                       NDArray[np.int32], NDArray[np.int32]]:
    """Create cultures and religions with their respective maps."""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from name_generator import NameGenerator
    
    rng = np.random.default_rng(seed)
    
    # Initialize name generator
    name_gen = NameGenerator(seed)
    
    # Ensure minimum 8 cultures for good diversity
    actual_num_cultures = max(8, num_cultures)
    
    # Generate culture origins and create Voronoi map
    culture_origins = generate_culture_origins(h, w, actual_num_cultures, biome_map, seed)
    culture_map = create_voronoi_map(h, w, culture_origins)
    culture_map = add_cultural_noise(culture_map, biome_map, noise_factor=0.2, seed=seed)
    
    # Generate religion origins (can be different from culture origins)
    religion_origins = generate_culture_origins(h, w, num_religions, biome_map, seed + 1000)
    religion_map = create_voronoi_map(h, w, religion_origins)
    religion_map = add_cultural_noise(religion_map, biome_map, noise_factor=0.12, seed=seed + 1000)
    
    # Set ocean/mountain tiles to no culture/religion (-1)
    invalid_mask = np.isin(biome_map, [2, 3])  # Mountains and oceans
    culture_map[invalid_mask] = -1
    religion_map[invalid_mask] = -1
    
    # Create culture objects with unique linguistic types and names
    culture_colors = create_palette(actual_num_cultures, hue_offset=0.0)
    cultures = []
    
    # Track used linguistic types to ensure diversity
    used_linguistic_types = set()
    available_types = name_gen.get_available_linguistic_types()
    
    for i in range(actual_num_cultures):
        # Assign linguistic type with diversity - reuse after all types used
        if len(used_linguistic_types) >= len(available_types):
            used_linguistic_types.clear()  # Start over for more cultures
        
        # Pick a linguistic type we haven't used recently
        available_for_selection = [t for t in available_types if t not in used_linguistic_types]
        if not available_for_selection:
            available_for_selection = available_types
            
        linguistic_type = rng.choice(available_for_selection)
        used_linguistic_types.add(linguistic_type)
        
        # Generate culture name with this linguistic type
        culture_name = name_gen.generate_culture_name(style=linguistic_type)
        
        culture = Culture(
            id=i,
            name=culture_name,
            color=culture_colors[i],
            origin=culture_origins[i],
            linguistic_type=linguistic_type
        )
        cultures.append(culture)
    
    # Create religion objects using name generator
    religion_symbols = generate_religion_symbols(num_religions)
    religion_colors = create_palette(num_religions, hue_offset=0.3)  # Different hue offset
    religions = []
    
    for i in range(num_religions):
        religion_name = name_gen.generate_religion_name()
        
        religion = Religion(
            id=i,
            name=religion_name,
            color=religion_colors[i],
            symbol=religion_symbols[i],
            origin=religion_origins[i]
        )
        religions.append(religion)
    
    return cultures, religions, culture_map, religion_map


def get_culture_at_position(culture_map: NDArray[np.int32], r: int, c: int) -> int:
    """Get the culture ID at a given position."""
    if 0 <= r < culture_map.shape[0] and 0 <= c < culture_map.shape[1]:
        return int(culture_map[r, c])
    return -1


def get_religion_at_position(religion_map: NDArray[np.int32], r: int, c: int) -> int:
    """Get the religion ID at a given position."""
    if 0 <= r < religion_map.shape[0] and 0 <= c < religion_map.shape[1]:
        return int(religion_map[r, c])
    return -1


def get_dominant_culture_in_radius(culture_map: NDArray[np.int32], 
                                 r: int, c: int, radius: int = 2) -> int:
    """Get the most common culture within a radius of a position."""
    h, w = culture_map.shape
    culture_counts = {}
    
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                culture_id = culture_map[nr, nc]
                if culture_id >= 0:  # Valid culture
                    culture_counts[culture_id] = culture_counts.get(culture_id, 0) + 1
    
    if not culture_counts:
        return -1
        
    return max(culture_counts.items(), key=lambda x: x[1])[0]


def get_dominant_religion_in_radius(religion_map: NDArray[np.int32], 
                                  r: int, c: int, radius: int = 2) -> int:
    """Get the most common religion within a radius of a position."""
    h, w = religion_map.shape
    religion_counts = {}
    
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                religion_id = religion_map[nr, nc]
                if religion_id >= 0:  # Valid religion
                    religion_counts[religion_id] = religion_counts.get(religion_id, 0) + 1
    
    if not religion_counts:
        return -1
        
    return max(religion_counts.items(), key=lambda x: x[1])[0]