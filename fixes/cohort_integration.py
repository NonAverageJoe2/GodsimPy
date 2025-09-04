# cohort_integration.py
"""Integration of the age cohort system into the main game."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
import numpy as np
from sim.cohorts import (
    init_from_total, step_cohorts, totals_from_cohorts,
    workforce_from_cohorts, COHORT_KEYS
)

@dataclass
class TileCohorts:
    """Age cohort data for a single tile."""
    c0_4: float = 0.0      # Ages 0-4
    c5_14: float = 0.0     # Ages 5-14  
    c15_39: float = 0.0    # Ages 15-39 (prime working/fighting age)
    c40_64: float = 0.0    # Ages 40-64 (mature working age)
    c65p: float = 0.0      # Ages 65+
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to cohort dictionary format."""
        return {
            "c0_4": self.c0_4,
            "c5_14": self.c5_14,
            "c15_39": self.c15_39,
            "c40_64": self.c40_64,
            "c65p": self.c65p
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'TileCohorts':
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_total_pop(cls, total: float) -> 'TileCohorts':
        """Initialize from total population with realistic distribution."""
        cohorts = init_from_total(
            np.array([[total]], dtype=np.float32),
            proportions={
                "c0_4": 0.10,   # 10% young children
                "c5_14": 0.16,  # 16% older children
                "c15_39": 0.40, # 40% prime age adults
                "c40_64": 0.24, # 24% mature adults
                "c65p": 0.10    # 10% elderly
            }
        )
        return cls(
            c0_4=float(cohorts["c0_4"][0, 0]),
            c5_14=float(cohorts["c5_14"][0, 0]),
            c15_39=float(cohorts["c15_39"][0, 0]),
            c40_64=float(cohorts["c40_64"][0, 0]),
            c65p=float(cohorts["c65p"][0, 0])
        )
    
    def total_population(self) -> float:
        """Get total population across all cohorts."""
        return self.c0_4 + self.c5_14 + self.c15_39 + self.c40_64 + self.c65p
    
    def workforce(self) -> float:
        """Get working age population (15-64)."""
        return self.c15_39 + self.c40_64
    
    def military_age_males(self) -> float:
        """Get military age male population (15-39)."""
        return self.c15_39 * 0.5  # 50% male
    
    def apply_war_casualties(self, casualties: int) -> int:
        """Remove casualties from military age cohorts. Returns actual removed."""
        available = self.military_age_males()
        actual_casualties = min(casualties, int(available * 0.8))  # Can't take more than 80%
        
        if actual_casualties > 0:
            # Remove primarily from young adult males
            reduction_factor = 1.0 - (actual_casualties / max(1, self.c15_39))
            self.c15_39 *= reduction_factor
        
        return actual_casualties


class CohortWorldState:
    """Manages cohort data for the entire world."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Store cohorts per tile
        self.tile_cohorts: Dict[Tuple[int, int], TileCohorts] = {}
        # Track cohort history for demographic analysis
        self.total_births: float = 0.0
        self.total_deaths_by_age: Dict[str, float] = {k: 0.0 for k in COHORT_KEYS}
        self.war_casualties: float = 0.0
    
    def initialize_from_pop_map(self, pop_map: np.ndarray) -> None:
        """Initialize cohorts from existing population map."""
        h, w = pop_map.shape
        for r in range(h):
            for q in range(w):
                if pop_map[r, q] > 0:
                    self.tile_cohorts[(q, r)] = TileCohorts.from_total_pop(pop_map[r, q])
    
    def get_tile_cohorts(self, q: int, r: int) -> TileCohorts:
        """Get cohorts for a tile, creating if needed."""
        key = (q, r)
        if key not in self.tile_cohorts:
            self.tile_cohorts[key] = TileCohorts()
        return self.tile_cohorts[key]
    
    def step_all_cohorts(self, dt_years: float, food_map: np.ndarray,
                         carrying_capacity: np.ndarray,
                         war_pressure_map: Optional[np.ndarray] = None) -> np.ndarray:
        """Advance all tile cohorts and return new population map."""
        h, w = food_map.shape
        new_pop_map = np.zeros((h, w), dtype=np.float32)
        
        for r in range(h):
            for q in range(w):
                cohorts = self.get_tile_cohorts(q, r)
                
                # Skip if no population
                if cohorts.total_population() <= 0:
                    continue
                
                # Convert to numpy format for cohort stepping
                coh_dict = cohorts.to_dict()
                coh_arrays = {k: np.array([[v]], dtype=np.float32) for k, v in coh_dict.items()}
                
                # Adjust birth/death rates based on food availability
                food_ratio = food_map[r, q] / max(0.1, carrying_capacity[r, q] / 100.0)
                
                # Modify mortality if food is scarce
                mortality_multiplier = 1.0
                if food_ratio < 0.5:
                    mortality_multiplier = 2.0 - food_ratio * 2  # Up to 2x mortality
                
                mortality_rates = {
                    "c0_4": 0.020 * mortality_multiplier,    # Children most vulnerable
                    "c5_14": 0.002 * mortality_multiplier,
                    "c15_39": 0.004 * mortality_multiplier,
                    "c40_64": 0.010 * mortality_multiplier,
                    "c65p": 0.060 * mortality_multiplier
                }
                
                # Modify birth rate based on food and stability
                births_per_female = 0.12  # Base rate
                if food_ratio > 1.5:
                    births_per_female *= 1.2  # Prosperity bonus
                elif food_ratio < 0.7:
                    births_per_female *= food_ratio  # Scarcity penalty
                
                # Apply war pressure (increases young male mortality)
                if war_pressure_map is not None and war_pressure_map[r, q] > 0:
                    mortality_rates["c15_39"] *= (1.0 + war_pressure_map[r, q])
                
                # Step cohorts forward
                new_coh = step_cohorts(
                    coh_arrays,
                    dt_years=dt_years,
                    births_per_female_per_year=births_per_female,
                    mortality_per_year=mortality_rates
                )
                
                # Apply carrying capacity constraint
                K = np.array([[carrying_capacity[r, q]]], dtype=np.float32)
                total = totals_from_cohorts(new_coh)[0, 0]
                
                if total > K[0, 0]:
                    scale = K[0, 0] / total
                    for key in new_coh:
                        new_coh[key] *= scale
                
                # Update tile cohorts
                cohorts.c0_4 = float(new_coh["c0_4"][0, 0])
                cohorts.c5_14 = float(new_coh["c5_14"][0, 0])
                cohorts.c15_39 = float(new_coh["c15_39"][0, 0])
                cohorts.c40_64 = float(new_coh["c40_64"][0, 0])
                cohorts.c65p = float(new_coh["c65p"][0, 0])
                
                # Track statistics
                # (births and deaths tracking would go here)
                
                new_pop_map[r, q] = cohorts.total_population()
        
        return new_pop_map
    
    def get_civ_manpower_potential(self, civ_tiles: List[Tuple[int, int]]) -> int:
        """Calculate actual available manpower from military-age cohorts."""
        total_military_age = 0.0
        for q, r in civ_tiles:
            cohorts = self.get_tile_cohorts(q, r)
            total_military_age += cohorts.military_age_males()
        
        # Can draft up to 50% of military age males
        return int(total_military_age * 0.5)
    
    def apply_army_recruitment(self, q: int, r: int, strength: int) -> int:
        """Remove recruited soldiers from cohorts. Returns actual recruited."""
        cohorts = self.get_tile_cohorts(q, r)
        return cohorts.apply_war_casualties(strength)  # Uses same mechanism
    
    def save_state(self) -> dict:
        """Serialize cohort state."""
        return {
            "cohorts": {f"{q},{r}": coh.to_dict() 
                       for (q, r), coh in self.tile_cohorts.items()},
            "total_births": self.total_births,
            "total_deaths": self.total_deaths_by_age,
            "war_casualties": self.war_casualties
        }
    
    def load_state(self, data: dict) -> None:
        """Deserialize cohort state."""
        self.tile_cohorts.clear()
        for key, coh_data in data.get("cohorts", {}).items():
            q, r = map(int, key.split(","))
            self.tile_cohorts[(q, r)] = TileCohorts.from_dict(coh_data)
        self.total_births = data.get("total_births", 0.0)
        self.total_deaths_by_age = data.get("total_deaths", {k: 0.0 for k in COHORT_KEYS})
        self.war_casualties = data.get("war_casualties", 0.0)
