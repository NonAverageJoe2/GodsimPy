from __future__ import annotations
import numpy as np
from enum import IntEnum
from .hexgrid import neighbors_axial, in_bounds


class Biome(IntEnum):
    GRASS = 0
    COAST = 1
    MOUNTAIN = 2
    OCEAN = 3
    DESERT = 4
    TUNDRA = 5      # Cold, barely habitable
    GLACIER = 6     # Frozen, uninhabitable
    MARSH = 7       # Wetlands, moderate yields
    STEPPE = 8      # Dry grassland, good for nomads
    SAVANNA = 9     # Warm grassland
    TAIGA = 10      # Cold forest
    TEMPERATE_FOREST = 11  # Regular forest
    TROPICAL_FOREST = 12    # Jungle


# Backwards compatibility constants
GRASS, COAST, MOUNTAIN, OCEAN = Biome.GRASS, Biome.COAST, Biome.MOUNTAIN, Biome.OCEAN
DESERT, TUNDRA, GLACIER = Biome.DESERT, Biome.TUNDRA, Biome.GLACIER
MARSH, STEPPE, SAVANNA = Biome.MARSH, Biome.STEPPE, Biome.SAVANNA
TAIGA, TEMPERATE_FOREST, TROPICAL_FOREST = (
    Biome.TAIGA, Biome.TEMPERATE_FOREST, Biome.TROPICAL_FOREST
)


def calculate_temperature(latitude: float, altitude: float) -> float:
    """Calculate temperature based on latitude and altitude.
    Returns value from 0 (coldest) to 1 (hottest)."""
    # Base temperature decreases with latitude (0 at poles, 1 at equator)
    lat_temp = 1.0 - abs(latitude)

    # Temperature decreases with altitude
    alt_penalty = altitude * 0.8

    return max(0.0, min(1.0, lat_temp - alt_penalty))


def calculate_moisture(distance_to_water: float, altitude: float, latitude: float) -> float:
    """Calculate moisture based on distance from water and climate factors.
    Returns value from 0 (driest) to 1 (wettest)."""
    # Base moisture decreases with distance from water
    water_moisture = max(0, 1.0 - distance_to_water / 10.0)

    # Mountains create rain shadows
    if altitude > 0.7:
        water_moisture *= 0.3

    # Tropical regions get more rain
    if abs(latitude) < 0.3:
        water_moisture *= 1.2

    return max(0.0, min(1.0, water_moisture))


def find_distance_to_water(r: int, q: int, height_map: np.ndarray,
                           sea_level: float, max_dist: int = 15) -> int:
    """BFS to find distance to nearest water tile."""
    H, W = height_map.shape
    if height_map[r, q] < sea_level:
        return 0

    visited = set()
    queue = [(r, q, 0)]
    visited.add((r, q))

    while queue:
        curr_r, curr_q, dist = queue.pop(0)

        for nq, nr in neighbors_axial(curr_q, curr_r):
            if not in_bounds(nq, nr, W, H):
                continue
            if (nr, nq) in visited:
                continue

            if height_map[nr, nq] < sea_level:
                return dist + 1

            if dist + 1 < max_dist:
                queue.append((nr, nq, dist + 1))
                visited.add((nr, nq))

    return max_dist


def build_biomes_advanced(height_map: np.ndarray, sea_level: float,
                          mountain_h: float, seed: int = 0) -> np.ndarray:
    """Generate biomes based on temperature, moisture, and altitude."""
    H, W = height_map.shape
    biomes = np.zeros((H, W), dtype=np.int32)

    # Pre-calculate distance to water for all land tiles
    distance_map = np.zeros((H, W), dtype=np.int32)
    for r in range(H):
        for q in range(W):
            if height_map[r, q] >= sea_level:
                distance_map[r, q] = find_distance_to_water(r, q, height_map, sea_level)

    # Add some noise for natural variation
    rng = np.random.default_rng(seed)
    temp_noise = rng.normal(0, 0.1, (H, W))
    moisture_noise = rng.normal(0, 0.1, (H, W))

    for r in range(H):
        for q in range(W):
            height = float(height_map[r, q])

            # Ocean tiles
            if height < sea_level:
                biomes[r, q] = OCEAN
                continue

            # Calculate latitude (0 at equator, ±1 at poles)
            latitude = (r / H - 0.5) * 2.0

            # Calculate climate factors
            altitude = (height - sea_level) / (1.0 - sea_level)
            temperature = calculate_temperature(latitude, altitude) + temp_noise[r, q]
            moisture = calculate_moisture(distance_map[r, q], altitude, latitude) + moisture_noise[r, q]

            # Mountain tiles (high altitude)
            if height >= mountain_h:
                if temperature < 0.3:
                    biomes[r, q] = GLACIER  # Frozen peaks
                else:
                    biomes[r, q] = MOUNTAIN
                continue

            # Check if coastal
            is_coastal = False
            for nq, nr in neighbors_axial(q, r):
                if in_bounds(nq, nr, W, H) and height_map[nr, nq] < sea_level:
                    is_coastal = True
                    break

            # Coastal tiles
            if is_coastal:
                if temperature < 0.2:
                    biomes[r, q] = TUNDRA  # Frozen coast
                elif moisture > 0.7 and temperature > 0.6:
                    biomes[r, q] = MARSH  # Coastal wetlands
                else:
                    biomes[r, q] = COAST
                continue

            # Interior land biomes based on temperature and moisture
            if temperature < 0.2:
                # Very cold
                if altitude > 0.5:
                    biomes[r, q] = GLACIER
                else:
                    biomes[r, q] = TUNDRA
            elif temperature < 0.4:
                # Cold
                if moisture > 0.5:
                    biomes[r, q] = TAIGA
                else:
                    biomes[r, q] = TUNDRA
            elif temperature < 0.7:
                # Temperate
                if moisture < 0.3:
                    biomes[r, q] = STEPPE
                elif moisture < 0.5:
                    biomes[r, q] = GRASS
                elif moisture < 0.7:
                    biomes[r, q] = TEMPERATE_FOREST
                else:
                    biomes[r, q] = MARSH
            else:
                # Hot
                if moisture < 0.2:
                    biomes[r, q] = DESERT
                elif moisture < 0.4:
                    biomes[r, q] = SAVANNA
                elif moisture < 0.7:
                    biomes[r, q] = GRASS
                else:
                    biomes[r, q] = TROPICAL_FOREST

    return biomes


# Keep the simpler version for backwards compatibility
def build_biomes(height: np.ndarray, sea_level: float, mountain_h: float) -> np.ndarray:
    """Simple biome generation for backwards compatibility."""
    H, W = height.shape
    out = np.zeros((H, W), dtype=np.int32)
    for r in range(H):
        for q in range(W):
            h0 = float(height[r, q])
            if h0 < sea_level:
                out[r, q] = OCEAN
            elif h0 >= mountain_h:
                out[r, q] = MOUNTAIN
            else:
                coast = False
                for nq, nr in neighbors_axial(q, r):
                    if in_bounds(nq, nr, W, H) and height[nr, nq] < sea_level:
                        coast = True
                        break
                out[r, q] = COAST if coast else GRASS
    return out
