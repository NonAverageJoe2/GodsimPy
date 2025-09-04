# military_economy.py
"""Complete military-economic integration with maintenance, supply, and food systems."""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
import math
import numpy as np

class SupplySource(Enum):
    """Types of supply sources for armies."""
    CAPITAL = "capital"
    CITY = "city"
    TOWN = "town"
    DEPOT = "depot"
    FORAGE = "forage"

@dataclass
class SupplyLine:
    """Represents a supply line from source to army."""
    source_tile: Tuple[int, int]
    source_type: SupplySource
    army_id: int
    distance: int
    efficiency: float  # 0.0 to 1.0
    capacity: int  # Max supply units per turn
    
    def calculate_delivered_supply(self, base_amount: int) -> int:
        """Calculate actual supply delivered based on distance and efficiency."""
        # Efficiency drops with distance: 100% at 0, 50% at 5 hexes, 25% at 10
        distance_penalty = 0.5 ** (self.distance / 5.0)
        actual_efficiency = self.efficiency * distance_penalty
        return min(self.capacity, int(base_amount * actual_efficiency))

@dataclass
class MilitaryEconomy:
    """Manages all military-economic interactions."""
    
    # Food economy
    food_per_pop_per_year: float = 1.0
    food_per_soldier_per_year: float = 1.5  # Soldiers eat more
    army_creation_food_cost_multiplier: float = 3.0  # Initial equipment/training
    
    # Maintenance costs
    gold_per_soldier_per_year: float = 2.0
    supply_per_soldier_per_turn: float = 0.5
    
    # Supply parameters
    max_supply_distance: int = 10
    supply_from_capital: int = 100
    supply_from_city: int = 50
    supply_from_town: int = 25
    forage_supply_rate: float = 0.2  # Per soldier from local area
    
    def __init__(self):
        self.supply_lines: Dict[int, SupplyLine] = {}  # army_id -> supply line
        self.army_supply_stocks: Dict[int, int] = {}   # army_id -> current supply
        self.food_reserves: Dict[int, float] = {}       # civ_id -> food stockpile
        self.gold_reserves: Dict[int, float] = {}       # civ_id -> gold (future)
    
    def calculate_food_production(self, civ_id: int, world, cohort_state) -> float:
        """Calculate total food production for a civilization."""
        if civ_id not in world.civs:
            return 0.0
        
        civ = world.civs[civ_id]
        total_food = 0.0
        
        for q, r in civ.tiles:
            tile = world.get_tile(q, r)
            # Base food from tile yields
            base_food, _ = self._get_tile_yields(tile)
            
            # Workforce modifier from cohorts
            cohorts = cohort_state.get_tile_cohorts(q, r)
            workforce = cohorts.workforce()
            total_pop = max(1, cohorts.total_population())
            workforce_ratio = workforce / total_pop
            
            # Actual production = base * workforce ratio * tech bonuses
            production_modifier = 0.5 + workforce_ratio  # 50% base + workforce
            
            # Apply tech bonuses if available
            if hasattr(world, 'tech_system') and world.tech_system:
                tech_bonuses = world.tech_system.get_civ_bonuses(civ_id)
                production_modifier *= tech_bonuses.food_multiplier
            
            tile_food = base_food * production_modifier * 100  # Scale up
            total_food += tile_food
        
        return total_food
    
    def calculate_food_consumption(self, civ_id: int, world, cohort_state) -> float:
        """Calculate total food consumption for a civilization."""
        if civ_id not in world.civs:
            return 0.0
        
        civ = world.civs[civ_id]
        
        # Civilian consumption
        civilian_consumption = 0.0
        for q, r in civ.tiles:
            cohorts = cohort_state.get_tile_cohorts(q, r)
            pop = cohorts.total_population()
            # Children eat less, elderly eat less
            weighted_pop = (cohorts.c0_4 * 0.5 +      # Young children
                          cohorts.c5_14 * 0.7 +       # Older children  
                          cohorts.c15_39 * 1.0 +      # Adults
                          cohorts.c40_64 * 1.0 +      # Mature adults
                          cohorts.c65p * 0.8)         # Elderly
            civilian_consumption += weighted_pop * self.food_per_pop_per_year
        
        # Military consumption
        military_consumption = 0.0
        for army in civ.armies:
            military_consumption += army.strength * self.food_per_soldier_per_year
        
        return civilian_consumption + military_consumption
    
    def process_food_economy(self, world, cohort_state, dt_years: float) -> Dict[int, float]:
        """Process food production and consumption for all civs."""
        food_balance = {}
        
        for civ_id, civ in world.civs.items():
            # Get current reserves
            reserves = self.food_reserves.get(civ_id, 0.0)
            
            # Calculate production and consumption
            production = self.calculate_food_production(civ_id, world, cohort_state) * dt_years
            consumption = self.calculate_food_consumption(civ_id, world, cohort_state) * dt_years
            
            # Update reserves
            new_reserves = reserves + production - consumption
            self.food_reserves[civ_id] = max(0, new_reserves)
            
            # Track balance for starvation effects
            food_balance[civ_id] = new_reserves
            
            # Apply starvation if negative
            if new_reserves < 0:
                deficit_ratio = abs(new_reserves) / max(1, consumption)
                # Starvation affects elderly and children most
                for q, r in civ.tiles:
                    cohorts = cohort_state.get_tile_cohorts(q, r)
                    cohorts.c0_4 *= (1.0 - deficit_ratio * 0.2)   # 20% child mortality
                    cohorts.c65p *= (1.0 - deficit_ratio * 0.15)  # 15% elderly mortality
        
        return food_balance
    
    def establish_supply_lines(self, world) -> None:
        """Establish optimal supply lines for all armies."""
        self.supply_lines.clear()
        
        for army in world.armies:
            best_source = self._find_best_supply_source(army, world)
            if best_source:
                source_tile, source_type, distance = best_source
                
                # Create supply line
                efficiency = 1.0
                if army.maintenance_cost_paid:
                    efficiency = 1.0
                else:
                    efficiency = 0.5  # Half efficiency if not maintained
                
                # Determine capacity based on source type
                capacity = {
                    SupplySource.CAPITAL: self.supply_from_capital,
                    SupplySource.CITY: self.supply_from_city,
                    SupplySource.TOWN: self.supply_from_town,
                    SupplySource.DEPOT: 40,
                    SupplySource.FORAGE: int(army.strength * self.forage_supply_rate)
                }.get(source_type, 20)
                
                self.supply_lines[id(army)] = SupplyLine(
                    source_tile=source_tile,
                    source_type=source_type,
                    army_id=id(army),
                    distance=distance,
                    efficiency=efficiency,
                    capacity=capacity
                )
    
    def process_army_supply(self, world, dt_years: float) -> None:
        """Process supply consumption and resupply for all armies."""
        turns_per_year = 52 if world.time_scale == "week" else (12 if world.time_scale == "month" else 1)
        
        for army in world.armies:
            army_id = id(army)
            
            # Consume supply
            consumption = army.strength * self.supply_per_soldier_per_turn * (dt_years * turns_per_year)
            army.supply = max(0, army.supply - int(consumption))
            
            # Resupply from supply line
            if army_id in self.supply_lines:
                line = self.supply_lines[army_id]
                resupply_amount = line.calculate_delivered_supply(army.strength)
                army.supply = min(army.max_supply, army.supply + resupply_amount)
                army.last_supplied_turn = world.turn
            
            # Forage if no supply line or low supply
            if army.supply < army.max_supply * 0.3:
                tile = world.get_tile(army.q, army.r)
                if tile.biome not in ["ocean", "mountain"]:
                    forage = int(army.strength * self.forage_supply_rate)
                    army.supply = min(army.max_supply, army.supply + forage)
                    # Foraging damages local population
                    if tile.pop > forage:
                        tile.pop -= forage // 10
            
            # Apply attrition if out of supply
            if army.supply <= 0:
                attrition = max(1, int(army.strength * 0.1))  # 10% attrition
                army.strength = max(0, army.strength - attrition)
                
                # Track casualties
                if army.civ_id in world.civs:
                    civ = world.civs[army.civ_id]
                    # These become recoverable casualties
    
    def process_army_maintenance(self, world, dt_years: float) -> Dict[int, bool]:
        """Process maintenance costs for all armies."""
        maintenance_paid = {}
        
        for civ_id, civ in world.civs.items():
            # Calculate total maintenance cost
            total_soldiers = sum(army.strength for army in civ.armies)
            food_cost = total_soldiers * self.food_per_soldier_per_year * dt_years
            
            # Check if civ can pay
            current_food = self.food_reserves.get(civ_id, 0)
            
            if current_food >= food_cost:
                self.food_reserves[civ_id] -= food_cost
                # Mark all armies as maintained
                for army in civ.armies:
                    army.maintenance_cost_paid = True
                    maintenance_paid[id(army)] = True
            else:
                # Partial payment - prioritize armies near enemies
                available = current_food
                self.food_reserves[civ_id] = 0
                
                # Sort armies by priority (near enemies first)
                priority_armies = sorted(civ.armies, 
                                       key=lambda a: self._get_army_priority(a, world),
                                       reverse=True)
                
                for army in priority_armies:
                    cost = army.strength * self.food_per_soldier_per_year * dt_years
                    if available >= cost:
                        available -= cost
                        army.maintenance_cost_paid = True
                        maintenance_paid[id(army)] = True
                    else:
                        army.maintenance_cost_paid = False
                        maintenance_paid[id(army)] = False
                        # Unmaintained armies lose morale/effectiveness
                        army.strength = int(army.strength * 0.95)
        
        return maintenance_paid
    
    def can_afford_army(self, civ_id: int, strength: int, world) -> bool:
        """Check if a civ can afford to create an army."""
        food_cost = strength * self.army_creation_food_cost_multiplier
        current_food = self.food_reserves.get(civ_id, 0)
        
        # Also check manpower
        if civ_id in world.civs:
            civ = world.civs[civ_id]
            if civ.manpower_used + strength > civ.manpower_limit:
                return False
        
        return current_food >= food_cost
    
    def pay_army_creation_cost(self, civ_id: int, strength: int) -> None:
        """Deduct the cost of creating an army."""
        food_cost = strength * self.army_creation_food_cost_multiplier
        self.food_reserves[civ_id] = max(0, self.food_reserves.get(civ_id, 0) - food_cost)
    
    def _find_best_supply_source(self, army, world) -> Optional[Tuple[Tuple[int, int], SupplySource, int]]:
        """Find the best supply source for an army."""
        if army.civ_id not in world.civs:
            return None
        
        civ = world.civs[army.civ_id]
        best_source = None
        best_score = -1
        
        for q, r in civ.tiles:
            tile = world.get_tile(q, r)
            settlement = tile.settlement if hasattr(tile, 'settlement') else 0
            
            # Determine source type
            source_type = None
            supply_value = 0
            
            if settlement == 4:  # Capital
                source_type = SupplySource.CAPITAL
                supply_value = self.supply_from_capital
            elif settlement == 3:  # City
                source_type = SupplySource.CITY
                supply_value = self.supply_from_city
            elif settlement == 2:  # Town
                source_type = SupplySource.TOWN
                supply_value = self.supply_from_town
            else:
                continue  # Villages and hamlets can't supply armies
            
            # Calculate distance
            distance = self._hex_distance(army.q, army.r, q, r)
            if distance > self.max_supply_distance:
                continue
            
            # Score based on supply value and distance
            score = supply_value / (1 + distance)
            
            if score > best_score:
                best_score = score
                best_source = ((q, r), source_type, distance)
        
        # If no settlement source, try foraging
        if best_source is None:
            tile = world.get_tile(army.q, army.r)
            if tile.biome not in ["ocean", "mountain", "desert"]:
                best_source = ((army.q, army.r), SupplySource.FORAGE, 0)
        
        return best_source
    
    def _get_army_priority(self, army, world) -> float:
        """Calculate priority for army maintenance."""
        priority = 0.0
        
        # Check for nearby enemies
        for other_army in world.armies:
            if other_army.civ_id != army.civ_id:
                distance = self._hex_distance(army.q, army.r, other_army.q, other_army.r)
                if distance <= 3:
                    priority += 100 / (1 + distance)
        
        # Check for border position
        tile = world.get_tile(army.q, army.r)
        for dq, dr in [(0,1), (1,0), (0,-1), (-1,0), (1,-1), (-1,1)]:
            nq, nr = army.q + dq, army.r + dr
            if world.in_bounds(nq, nr):
                neighbor = world.get_tile(nq, nr)
                if neighbor.owner != tile.owner and neighbor.owner is not None:
                    priority += 20
        
        return priority
    
    def _hex_distance(self, q1: int, r1: int, q2: int, r2: int) -> int:
        """Calculate hex distance between two tiles."""
        return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2
    
    def _get_tile_yields(self, tile) -> Tuple[float, float]:
        """Get food and production yields for a tile."""
        # This should use the actual yields_for function
        biome_yields = {
            "grass": (1.0, 0.6),
            "coast": (0.8, 0.4),
            "mountain": (0.1, 1.0),
            "ocean": (0.2, 0.2),
            "desert": (0.2, 0.3)
        }
        return biome_yields.get(tile.biome, (0.5, 0.5))
    
    def save_state(self) -> dict:
        """Save military economy state."""
        return {
            "food_reserves": dict(self.food_reserves),
            "gold_reserves": dict(self.gold_reserves),
            "supply_lines": {k: {
                "source": v.source_tile,
                "type": v.source_type.value,
                "distance": v.distance,
                "efficiency": v.efficiency
            } for k, v in self.supply_lines.items()}
        }
    
    def load_state(self, data: dict) -> None:
        """Load military economy state."""
        self.food_reserves = data.get("food_reserves", {})
        self.gold_reserves = data.get("gold_reserves", {})
        # Supply lines would need to be rebuilt from armies
