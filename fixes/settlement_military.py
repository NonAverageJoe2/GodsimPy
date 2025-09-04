# settlement_military.py
"""Integration between settlements and military systems."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum

class SettlementType(Enum):
    """Settlement types with military capabilities."""
    HAMLET = 0
    VILLAGE = 1
    TOWN = 2
    CITY = 3
    CAPITAL = 4

@dataclass
class SettlementMilitary:
    """Military attributes of a settlement."""
    type: SettlementType
    garrison_capacity: int = 0
    garrison_strength: int = 0
    fortification_level: int = 0  # 0-3: none, palisade, walls, fortress
    recruitment_capacity: int = 0  # Soldiers per turn
    supply_generation: int = 0
    
    @classmethod
    def from_settlement_type(cls, stype: SettlementType) -> 'SettlementMilitary':
        """Create military attributes based on settlement type."""
        configs = {
            SettlementType.HAMLET: {
                "garrison_capacity": 0,
                "recruitment_capacity": 0,
                "supply_generation": 5,
                "fortification_level": 0
            },
            SettlementType.VILLAGE: {
                "garrison_capacity": 10,
                "recruitment_capacity": 2,
                "supply_generation": 10,
                "fortification_level": 0
            },
            SettlementType.TOWN: {
                "garrison_capacity": 30,
                "recruitment_capacity": 5,
                "supply_generation": 25,
                "fortification_level": 1
            },
            SettlementType.CITY: {
                "garrison_capacity": 60,
                "recruitment_capacity": 10,
                "supply_generation": 50,
                "fortification_level": 2
            },
            SettlementType.CAPITAL: {
                "garrison_capacity": 100,
                "recruitment_capacity": 20,
                "supply_generation": 100,
                "fortification_level": 3
            }
        }
        
        config = configs.get(stype, configs[SettlementType.HAMLET])
        return cls(
            type=stype,
            garrison_capacity=config["garrison_capacity"],
            garrison_strength=0,
            fortification_level=config["fortification_level"],
            recruitment_capacity=config["recruitment_capacity"],
            supply_generation=config["supply_generation"]
        )


@dataclass
class MilitaryBuilding:
    """Represents military buildings that can be constructed."""
    name: str
    type: str  # "barracks", "walls", "depot", "arsenal"
    cost_production: int
    maintenance_cost: float
    effects: Dict[str, float]  # e.g., {"recruitment_bonus": 1.5, "garrison_bonus": 20}
    tech_required: Optional[str] = None


class SettlementMilitarySystem:
    """Manages settlement-military interactions."""
    
    def __init__(self):
        self.settlement_military: Dict[Tuple[int, int], SettlementMilitary] = {}
        self.military_buildings: Dict[Tuple[int, int], List[MilitaryBuilding]] = {}
        self.recruitment_queue: Dict[Tuple[int, int], List[dict]] = {}  # Queue of units being trained
        self.siege_modifiers: Dict[Tuple[int, int], float] = {}  # Combat modifiers from fortifications
    
    def initialize_settlement(self, q: int, r: int, settlement_type: int) -> None:
        """Initialize military attributes for a settlement."""
        stype = SettlementType(settlement_type)
        self.settlement_military[(q, r)] = SettlementMilitary.from_settlement_type(stype)
    
    def can_recruit_at(self, q: int, r: int, world) -> Tuple[bool, int]:
        """Check if recruitment is possible at this settlement."""
        key = (q, r)
        if key not in self.settlement_military:
            return False, 0
        
        mil = self.settlement_military[key]
        tile = world.get_tile(q, r)
        
        # Check if settlement has capacity
        if mil.recruitment_capacity <= 0:
            return False, 0
        
        # Check if there's population to recruit from
        if hasattr(world, 'cohort_state'):
            cohorts = world.cohort_state.get_tile_cohorts(q, r)
            available = cohorts.military_age_males()
            max_recruitible = min(mil.recruitment_capacity, int(available * 0.1))  # Max 10% per turn
            return max_recruitible > 0, max_recruitible
        else:
            # Fallback for non-cohort system
            available = int(tile.pop * 0.1)
            max_recruitible = min(mil.recruitment_capacity, available)
            return max_recruitible > 0, max_recruitible
    
    def recruit_garrison(self, q: int, r: int, amount: int, world) -> int:
        """Recruit soldiers directly into garrison. Returns actual recruited."""
        key = (q, r)
        if key not in self.settlement_military:
            return 0
        
        mil = self.settlement_military[key]
        can_recruit, max_amount = self.can_recruit_at(q, r, world)
        
        if not can_recruit:
            return 0
        
        actual = min(amount, max_amount, mil.garrison_capacity - mil.garrison_strength)
        
        # Remove from population
        tile = world.get_tile(q, r)
        if hasattr(world, 'cohort_state'):
            removed = world.cohort_state.apply_army_recruitment(q, r, actual)
            actual = removed  # May be less if not enough young males
        else:
            tile.pop = max(0, tile.pop - actual)
        
        # Add to garrison
        mil.garrison_strength += actual
        
        return actual
    
    def release_garrison(self, q: int, r: int, amount: int = None) -> int:
        """Release garrison back to population. Returns amount released."""
        key = (q, r)
        if key not in self.settlement_military:
            return 0
        
        mil = self.settlement_military[key]
        if amount is None:
            amount = mil.garrison_strength
        
        actual = min(amount, mil.garrison_strength)
        mil.garrison_strength -= actual
        
        # Add back to population
        # (In full implementation, would add to appropriate cohorts)
        return actual
    
    def create_army_from_garrison(self, q: int, r: int, strength: int, world) -> Optional['Army']:
        """Create an army from garrison troops."""
        key = (q, r)
        if key not in self.settlement_military:
            return None
        
        mil = self.settlement_military[key]
        if mil.garrison_strength < strength:
            return None
        
        tile = world.get_tile(q, r)
        if tile.owner is None:
            return None
        
        # Check if civ can afford maintenance
        if hasattr(world, 'military_economy'):
            if not world.military_economy.can_afford_army(tile.owner, strength, world):
                return None
        
        # Create the army
        from military_fixes import ArmyFixed
        army = ArmyFixed(
            civ_id=tile.owner,
            q=q,
            r=r,
            strength=strength,
            supply=100,
            max_supply=100
        )
        
        # Remove from garrison
        mil.garrison_strength -= strength
        
        # Add to world
        world.armies.append(army)
        if tile.owner in world.civs:
            world.civs[tile.owner].armies.append(army)
            world.civs[tile.owner].manpower_used += strength
        
        # Pay creation cost
        if hasattr(world, 'military_economy'):
            world.military_economy.pay_army_creation_cost(tile.owner, strength)
        
        return army
    
    def apply_siege_combat(self, attacker, defender_tile, world) -> Tuple[int, int]:
        """Apply combat with fortification bonuses. Returns (attacker_losses, defender_losses)."""
        key = (defender_tile.q, defender_tile.r)
        
        # Get garrison and fortification
        garrison = 0
        fortification_bonus = 1.0
        
        if key in self.settlement_military:
            mil = self.settlement_military[key]
            garrison = mil.garrison_strength
            
            # Fortification bonuses
            fort_multipliers = {
                0: 1.0,   # No fortification
                1: 1.5,   # Palisade
                2: 2.0,   # Walls
                3: 3.0    # Fortress
            }
            fortification_bonus = fort_multipliers.get(mil.fortification_level, 1.0)
        
        # Calculate effective strengths
        attacker_strength = attacker.strength
        defender_strength = garrison * fortification_bonus
        
        # Add any field armies at the location
        for army in world.armies:
            if army.q == defender_tile.q and army.r == defender_tile.r:
                if army.civ_id == defender_tile.owner:
                    defender_strength += army.strength
        
        # Combat resolution
        if attacker_strength > defender_strength:
            # Attacker wins but takes casualties
            attacker_losses = int(defender_strength * 0.3)  # Takes 30% of defender strength
            defender_losses = garrison  # All garrison lost
            
            # Damage settlement
            if key in self.settlement_military:
                mil = self.settlement_military[key]
                mil.garrison_strength = 0
                mil.fortification_level = max(0, mil.fortification_level - 1)
        else:
            # Defender wins
            defender_losses = int(attacker_strength * 0.3)
            attacker_losses = int(attacker.strength * 0.7)  # Heavy losses for failed siege
            
            if key in self.settlement_military:
                mil = self.settlement_military[key]
                mil.garrison_strength = max(0, garrison - defender_losses)
        
        return attacker_losses, defender_losses
    
    def get_defense_bonus(self, q: int, r: int) -> float:
        """Get defensive combat bonus for a settlement."""
        key = (q, r)
        if key not in self.settlement_military:
            return 1.0
        
        mil = self.settlement_military[key]
        fort_multipliers = {
            0: 1.0,
            1: 1.5,
            2: 2.0,
            3: 3.0
        }
        return fort_multipliers.get(mil.fortification_level, 1.0)
    
    def process_settlement_supply(self, world, dt_years: float) -> Dict[Tuple[int, int], int]:
        """Generate supplies from settlements."""
        supply_generated = {}
        
        for key, mil in self.settlement_military.items():
            q, r = key
            tile = world.get_tile(q, r)
            
            if tile.owner is None:
                continue
            
            # Generate supply based on settlement size
            base_supply = mil.supply_generation * dt_years
            
            # Bonus from buildings
            if key in self.military_buildings:
                for building in self.military_buildings[key]:
                    if building.type == "depot":
                        base_supply *= building.effects.get("supply_bonus", 1.0)
            
            supply_generated[key] = int(base_supply)
        
        return supply_generated
    
    def upgrade_fortification(self, q: int, r: int, world) -> bool:
        """Upgrade fortification level of a settlement."""
        key = (q, r)
        if key not in self.settlement_military:
            return False
        
        mil = self.settlement_military[key]
        if mil.fortification_level >= 3:
            return False  # Max level
        
        # Check cost (simplified - should use production)
        tile = world.get_tile(q, r)
        if tile.owner is None:
            return False
        
        upgrade_costs = {0: 100, 1: 250, 2: 500}
        cost = upgrade_costs.get(mil.fortification_level, 1000)
        
        # For now, just check food reserves as proxy for resources
        if hasattr(world, 'military_economy'):
            reserves = world.military_economy.food_reserves.get(tile.owner, 0)
            if reserves >= cost:
                world.military_economy.food_reserves[tile.owner] -= cost
                mil.fortification_level += 1
                return True
        
        return False
    
    def save_state(self) -> dict:
        """Save settlement military state."""
        return {
            "settlements": {
                f"{q},{r}": {
                    "type": mil.type.value,
                    "garrison": mil.garrison_strength,
                    "fortification": mil.fortification_level,
                    "capacity": mil.garrison_capacity
                }
                for (q, r), mil in self.settlement_military.items()
            },
            "buildings": {
                f"{q},{r}": [
                    {"name": b.name, "type": b.type, "effects": b.effects}
                    for b in buildings
                ]
                for (q, r), buildings in self.military_buildings.items()
            }
        }
    
    def load_state(self, data: dict) -> None:
        """Load settlement military state."""
        self.settlement_military.clear()
        for key, sdata in data.get("settlements", {}).items():
            q, r = map(int, key.split(","))
            mil = SettlementMilitary(
                type=SettlementType(sdata["type"]),
                garrison_capacity=sdata["capacity"],
                garrison_strength=sdata["garrison"],
                fortification_level=sdata["fortification"]
            )
            self.settlement_military[(q, r)] = mil
