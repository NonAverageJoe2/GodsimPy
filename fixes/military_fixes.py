# military_fixes.py
"""Fixes for manpower recovery, army synchronization, and movement persistence."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json

@dataclass
class ArmyFixed:
    """Fixed Army class with persistent movement accumulator."""
    civ_id: int
    q: int
    r: int
    strength: int = 10
    target: Optional[Tuple[int, int]] = None
    path: List[Tuple[int, int]] = field(default_factory=list)
    supply: int = 100
    max_supply: int = 100  # NEW: Maximum supply capacity
    speed_hexes_per_year: int = 52
    movement_accumulator: float = 0.0  # Now a regular field, not hidden
    
    # NEW: Maintenance tracking
    last_supplied_turn: int = 0
    maintenance_cost_paid: bool = True
    
    def to_dict(self) -> dict:
        """Serialize army to dictionary for saving."""
        return {
            "civ_id": self.civ_id,
            "q": self.q, 
            "r": self.r,
            "strength": self.strength,
            "target": self.target,
            "path": self.path,
            "supply": self.supply,
            "max_supply": self.max_supply,
            "movement_accumulator": self.movement_accumulator,
            "last_supplied_turn": self.last_supplied_turn,
            "maintenance_cost_paid": self.maintenance_cost_paid
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ArmyFixed':
        """Deserialize army from dictionary."""
        return cls(
            civ_id=data["civ_id"],
            q=data["q"],
            r=data["r"],
            strength=data.get("strength", 10),
            target=tuple(data["target"]) if data.get("target") else None,
            path=[tuple(p) for p in data.get("path", [])],
            supply=data.get("supply", 100),
            max_supply=data.get("max_supply", 100),
            movement_accumulator=data.get("movement_accumulator", 0.0),
            last_supplied_turn=data.get("last_supplied_turn", 0),
            maintenance_cost_paid=data.get("maintenance_cost_paid", True)
        )


class ManpowerManager:
    """Manages civilization manpower allocation and recovery."""
    
    def __init__(self):
        self.civ_manpower_allocated: Dict[int, int] = {}
        self.civ_manpower_lost: Dict[int, int] = {}  # Track losses for recovery
    
    def allocate_manpower(self, civ_id: int, amount: int) -> bool:
        """Allocate manpower for a new army."""
        current = self.civ_manpower_allocated.get(civ_id, 0)
        self.civ_manpower_allocated[civ_id] = current + amount
        return True
    
    def release_manpower(self, civ_id: int, amount: int, as_casualties: bool = False):
        """Release manpower when army is disbanded or destroyed."""
        current = self.civ_manpower_allocated.get(civ_id, 0)
        self.civ_manpower_allocated[civ_id] = max(0, current - amount)
        
        if as_casualties:
            # Track casualties for gradual recovery
            lost = self.civ_manpower_lost.get(civ_id, 0)
            self.civ_manpower_lost[civ_id] = lost + amount
    
    def recover_casualties(self, civ_id: int, recovery_rate: float = 0.1) -> int:
        """Gradually recover lost manpower (represents new adults)."""
        lost = self.civ_manpower_lost.get(civ_id, 0)
        if lost <= 0:
            return 0
        
        recovered = min(lost, max(1, int(lost * recovery_rate)))
        self.civ_manpower_lost[civ_id] = lost - recovered
        return recovered
    
    def get_civ_manpower_used(self, civ_id: int) -> int:
        """Get current manpower in use."""
        return self.civ_manpower_allocated.get(civ_id, 0)


def synchronize_army_lists(world) -> None:
    """Ensure army lists are synchronized between world and civs."""
    # Clear civ army lists
    for civ in world.civs.values():
        if not hasattr(civ, 'armies'):
            civ.armies = []
        else:
            civ.armies.clear()
    
    # Rebuild from world.armies
    for army in world.armies:
        if army.civ_id in world.civs:
            world.civs[army.civ_id].armies.append(army)


def remove_army_properly(world, army, manpower_manager: ManpowerManager, 
                        as_casualties: bool = False) -> None:
    """Properly remove an army, updating all references and recovering manpower."""
    # Remove from world list
    if army in world.armies:
        world.armies.remove(army)
    
    # Remove from civ list
    if army.civ_id in world.civs:
        civ = world.civs[army.civ_id]
        if hasattr(civ, 'armies') and army in civ.armies:
            civ.armies.remove(army)
    
    # Release manpower
    manpower_manager.release_manpower(army.civ_id, army.strength, as_casualties)
    
    # Update civ manpower_used
    if army.civ_id in world.civs:
        world.civs[army.civ_id].manpower_used = manpower_manager.get_civ_manpower_used(army.civ_id)
