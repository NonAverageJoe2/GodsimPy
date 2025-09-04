# population_fixes.py
"""Fixes for population float tracking and synchronization issues."""

from typing import Optional
import math

class TileHexFixed:
    """Fixed version of TileHex with proper float tracking."""
    
    def __init__(self, q: int, r: int, height: float = 0.0, biome: str = "ocean",
                 pop: int = 0, owner: Optional[int] = None, feature: Optional[str] = None):
        self.q = q
        self.r = r
        self.height = height
        self.biome = biome
        self._pop_int = pop
        self._pop_float = float(pop)
        self.owner = owner
        self.feature = feature
    
    @property
    def pop(self) -> int:
        """Get integer population."""
        return self._pop_int
    
    @pop.setter
    def pop(self, value: int):
        """Set population, maintaining float sync."""
        self._pop_int = int(value)
        self._pop_float = float(value)
    
    def set_pop_float(self, value: float):
        """Set population from float, updating both values."""
        self._pop_float = float(value)
        self._pop_int = int(math.floor(value))
    
    def get_pop_float(self) -> float:
        """Get float population for calculations."""
        return self._pop_float


def safe_update_population(tile, new_pop_float: float) -> None:
    """Safely update tile population maintaining sync."""
    if hasattr(tile, 'set_pop_float'):
        tile.set_pop_float(new_pop_float)
    else:
        # Fallback for old TileHex
        tile._pop_float = float(new_pop_float)
        # Use object.__setattr__ to avoid triggering the bad __setattr__
        object.__setattr__(tile, "pop", int(math.floor(new_pop_float)))
