from __future__ import annotations
from typing import Dict, Tuple

# Per-biome resource yields per year (food, production)
BIOME_YIELDS: Dict[str, Tuple[float, float]] = {
    "ocean": (0.2, 0.2),
    "coast": (0.8, 0.4),
    "grass": (1.0, 0.6),
    "mountain": (0.1, 1.0),
}

# Multipliers for terrain features
# Each entry: feature -> (food_multiplier, production_multiplier)
FEATURE_MULTIPLIERS: Dict[str, Tuple[float, float]] = {
    "forest": (1.1, 1.2),
}


def yields_for(tile) -> Tuple[float, float]:
    """Return yearly (food, production) yields for ``tile``.

    The yield is determined by the tile's biome and optionally modified
    by its terrain feature.
    """
    food, prod = BIOME_YIELDS.get(tile.biome, (0.0, 0.0))
    if tile.feature:
        mult = FEATURE_MULTIPLIERS.get(tile.feature)
        if mult is not None:
            food *= mult[0]
            prod *= mult[1]
    return food, prod
