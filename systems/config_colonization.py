"""
Colonization & Migration tuning knobs.
Safe to tweak without touching system code.
"""

from modifiers import MODIFIERS

# Global pace multiplier: 0.5 = slower, 2.0 = faster
PACE_MULTIPLIER: float = 1.0

# Migration - reduced to encourage colonization instead
MIGRATION_BASE_RATE: float = 0.05     # Reduced from 0.10 - less internal migration  
MIGRATION_MIN_SOURCE_POP: int = 40    # Increased from 20 - colonize first, migrate later
MIGRATION_TOP_PRESSURE_TILES: int = 5 # per civ, limit sources per step
MIGRATION_RECENT_WINDOW: int = 6      # turns: reduces ping-pong if dest received migrants recently
MIGRATION_RECENT_FRICTION: float = 0.8  # multiply outflow if dest recently received

# Colonization - more aggressive expansion
COLONIZE_SOURCE_MIN_POP: int = 30  # Reduced from 60 - colonize earlier
COLONIZE_COLONY_SEED: int = 20     # Increased from 15 - bigger colonies

# Carrying capacity
CARRYING_CAP_PER_FOOD: float = MODIFIERS.carrying_capacity_per_food
MIN_FOOD_EPS: float = MODIFIERS.min_food_eps  # avoid div-by-zero on barren tiles

# Trade routes
TRADE_ROUTE_MIN_DIST: int = 5
TRADE_ROUTE_MAX_DIST: int = 15
TRADE_ROUTE_MAX_PER_CIV: int = 3

# Culture
CULTURAL_RADIUS: int = 3
CULTURAL_FLIP_MAX_CHANCE: float = 0.10
POP_CORE_THRESHOLD: int = 80  # tiles at/above this pop never flip

# Connectivity / center calc
CONNECTIVITY_CENTER_TOP_N: int = 10
CONNECTIVITY_MAX: float = 2.0
CONNECTIVITY_DIST_DENOM: float = 20.0
CONNECTIVITY_ADJACENT_BONUS: float = 0.1
CONNECTIVITY_TRADE_BONUS: float = 0.3
