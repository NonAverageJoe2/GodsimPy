"""
Population-based workforce and food production system.

Historically around sixty percent of the population needed to farm
simply to feed everyone.  That hard requirement caused population
stagnation in the simulation because the limited food output prevented
further growth or expansion.  These defaults are tuned slightly higher
to keep early civilizations from getting trapped at tiny sizes while
remaining in the same rough historical ballpark.
"""
from __future__ import annotations
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class WorkforceAllocation:
    """Tracks how a civilization's population is allocated across jobs."""
    total_population: int = 0
    agricultural_workers: int = 0
    available_military: int = 0
    other_workers: int = 0
    food_production: float = 0.0
    food_capacity: float = 0.0
    

class WorkforceSystem:
    """Manages population-based food production and workforce allocation."""
    
    # Base productivity per worker per year.  Increasing this allows each
    # farmer to feed more people which helps small civilizations grow.
    AGRICULTURAL_PRODUCTIVITY = 3.0  # Each farmer now feeds 3 people
    FOOD_CONSUMPTION_PER_PERSON = 1.0  # Food consumed per person per year
    MILITARY_FOOD_MULTIPLIER = 1.5    # Soldiers eat 1.5x normal (training, equipment)
    
    # Required workforce ratios (can be modified by technology).  Lowering the
    # base agricultural ratio reduces how many citizens must farm before the
    # civilization can support specialists or soldiers.
    BASE_AGRICULTURAL_RATIO = 0.40  # 40% must work in agriculture
    MAX_MILITARY_RATIO = 0.25      # Up to 25% can be military
    OTHER_WORKERS_RATIO = 0.15     # 15% for crafts, trade, etc.
    
    def calculate_workforce(self, civ_id: int, total_pop: int, 
                          tech_bonuses=None) -> WorkforceAllocation:
        """Calculate optimal workforce allocation for a civilization."""
        
        # Apply technology bonuses to agricultural efficiency
        agricultural_productivity = self.AGRICULTURAL_PRODUCTIVITY
        agricultural_ratio = self.BASE_AGRICULTURAL_RATIO
        
        if tech_bonuses:
            # Agriculture techs reduce the % needed for farming
            ag_efficiency = getattr(tech_bonuses, 'agricultural_efficiency', 0.0)
            agricultural_productivity *= (1.0 + ag_efficiency)
            # More efficient agriculture = fewer farmers needed
            agricultural_ratio = max(0.3, agricultural_ratio * (1.0 - ag_efficiency * 0.5))
        
        # Calculate workforce allocation
        agricultural_workers = int(total_pop * agricultural_ratio)
        remaining_pop = total_pop - agricultural_workers
        
        # Military availability (limited by non-agricultural population)
        available_military = int(remaining_pop * (self.MAX_MILITARY_RATIO / (1.0 - agricultural_ratio)))
        available_military = min(available_military, remaining_pop)
        
        # Other workers (craftsmen, traders, etc.)
        other_workers = remaining_pop - available_military
        
        # Food production and capacity
        food_production = agricultural_workers * agricultural_productivity
        food_capacity = food_production  # How many people this civ can feed
        
        return WorkforceAllocation(
            total_population=total_pop,
            agricultural_workers=agricultural_workers,
            available_military=available_military,
            other_workers=other_workers,
            food_production=food_production,
            food_capacity=food_capacity
        )
    
    def get_biome_productivity_modifier(self, biome: str) -> float:
        """Get productivity modifier based on terrain quality."""
        # Terrain affects agricultural productivity
        modifiers = {
            "grass": 1.2,      # Fertile plains - best for farming
            "coast": 1.0,      # Average coastal farming + fishing
            "forest": 0.8,     # Must clear forests, but fertile soil
            "mountain": 0.4,   # Poor terrain for farming
            "desert": 0.3,     # Very poor for agriculture  
            "ocean": 0.1,      # Minimal fishing productivity
        }
        return modifiers.get(biome, 1.0)
    
    def calculate_civ_food_production(self, civ, world, tech_bonuses=None) -> Tuple[float, float]:
        """Calculate total food production and capacity for a civilization."""
        total_pop = sum(world.get_tile(q, r).pop for q, r in civ.tiles)
        
        if total_pop == 0:
            return 0.0, 0.0
            
        workforce = self.calculate_workforce(civ.civ_id, total_pop, tech_bonuses)
        
        # Apply terrain modifiers based on where the population lives
        weighted_productivity = 0.0
        total_agricultural_pop = 0
        
        for q, r in civ.tiles:
            tile = world.get_tile(q, r)
            if tile.pop <= 0:
                continue
                
            # Calculate how many farmers are on this tile
            tile_ag_workers = int(tile.pop * (workforce.agricultural_workers / total_pop))
            biome_modifier = self.get_biome_productivity_modifier(tile.biome)
            
            # This tile's food production
            tile_food_production = tile_ag_workers * self.AGRICULTURAL_PRODUCTIVITY * biome_modifier
            weighted_productivity += tile_food_production
            total_agricultural_pop += tile_ag_workers
        
        # Total food production and capacity
        food_production = weighted_productivity

        # Provide a subsistence bonus representing foraging, fishing and
        # other baseline food sources that don't require dedicated farmers.
        # This softens the hard food cap and allows populations to expand
        # beyond the initial threshold.
        food_production *= 1.3

        food_capacity = food_production  # How many people this food can support
        
        return food_production, food_capacity
    
    def calculate_food_consumption(self, total_pop: int, military_pop: int = 0) -> float:
        """Calculate total food consumption for a population."""
        civilian_pop = total_pop - military_pop
        civilian_consumption = civilian_pop * self.FOOD_CONSUMPTION_PER_PERSON
        military_consumption = military_pop * self.FOOD_CONSUMPTION_PER_PERSON * self.MILITARY_FOOD_MULTIPLIER
        return civilian_consumption + military_consumption


# Global workforce system instance
WORKFORCE_SYSTEM = WorkforceSystem()
