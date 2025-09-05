from __future__ import annotations
import numpy as np


def has_oasis_feature(r: int, c: int) -> bool:
    """Placeholder for checking if a tile has an oasis feature."""
    return False


def is_nomadic_civ(civ_id: int) -> bool:
    """Placeholder for checking whether a civilization is nomadic."""
    return False


def apply_biome_modifiers(ws, pop_map: np.ndarray, growth_rates: np.ndarray, biome_map: np.ndarray):
    """Apply biome-specific modifiers to population and growth."""
    h, w = biome_map.shape

    for r in range(h):
        for c in range(w):
            biome = int(biome_map[r, c])

            # Glacier tiles - uninhabitable
            if biome == 6:  # GLACIER
                pop_map[r, c] = 0.0
                growth_rates[r, c] = 0.0
                continue

            # Tundra - very limited growth
            if biome == 5:  # TUNDRA
                growth_rates[r, c] *= 0.3
                pop_map[r, c] = min(pop_map[r, c], 30.0)

            # Desert - limited population without oases
            elif biome == 4:  # DESERT
                growth_rates[r, c] *= 0.5
                if not has_oasis_feature(r, c):
                    pop_map[r, c] = min(pop_map[r, c], 50.0)

            # Marsh - higher disease rate (handled elsewhere)
            elif biome == 7:  # MARSH
                pass

            # Steppe - bonus for nomadic civs
            elif biome == 8:  # STEPPE
                owner = ws.owner_map[r, c]
                if owner >= 0 and is_nomadic_civ(int(owner)):
                    growth_rates[r, c] *= 1.3

    return pop_map, growth_rates


def get_movement_cost(biome: int) -> float:
    """Get movement cost multiplier for different biomes."""
    movement_costs = {
        0: 1.0,   # GRASS
        1: 1.0,   # COAST
        2: 5.0,   # MOUNTAIN
        3: 999.0, # OCEAN - impassable without boats
        4: 1.2,   # DESERT - slightly harder
        5: 1.5,   # TUNDRA - snow slows movement
        6: 999.0, # GLACIER - impassable
        7: 2.0,   # MARSH - very slow
        8: 0.8,   # STEPPE - easy travel
        9: 1.0,   # SAVANNA
        10: 1.3,  # TAIGA - forest slows
        11: 1.2,  # TEMPERATE_FOREST
        12: 1.5,  # TROPICAL_FOREST - dense
    }
    return movement_costs.get(biome, 1.0)
