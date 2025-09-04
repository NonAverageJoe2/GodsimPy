"""
Systems package: gameplay systems such as colonization, diplomacy, economy.
"""

# Expose colonization system directly
from . import config_colonization
from .colonization_enhanced import (
    EnhancedColonizationSystem,
    ColonizationStrategy,
    integrate_enhanced_colonization,
    determine_colonization_strategy,
)

__all__ = [
    "config_colonization",
    "EnhancedColonizationSystem",
    "ColonizationStrategy",
    "integrate_enhanced_colonization",
    "determine_colonization_strategy",
]
