from dataclasses import dataclass

from society import DEFAULT_SOCIETY


@dataclass
class GameModifiers:
    """Tweakable simulation parameters.

    Central store for values that affect core simulation mechanics.
    Events or technologies can modify these numbers at runtime to
    globally influence systems that consume them.
    """

    # Carrying capacity derived from food supply
    carrying_capacity_per_food: float = 100.0
    min_food_eps: float = 1e-6

    # Population dynamics - POPULATION FIX: Increased for 1000+ year simulations
    base_population_growth_rate: float = 1.2  # logistic growth per year (10x increase for visible changes)
    growth_variance: float = 0.2
    food_per_pop: float = 1.0
    disaster_rate: float = 0.02

    # Military and economic costs
    food_per_pop_per_year: float = 1.0
    food_per_soldier_per_year: float = 1.5
    army_creation_food_cost_multiplier: float = 3.0


# Global modifiers instance used throughout the codebase
MODIFIERS = GameModifiers()

# Expose society defaults through this module so other parts of the codebase
# can access them without importing :mod:`society` directly.
SOCIETY_DEFAULTS = DEFAULT_SOCIETY

