"""
Technology and Ages System for GodsimPy

This module implements a technology tree and age progression system for civilizations.
Technologies unlock new capabilities and bonuses, while ages represent major
technological milestones.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum, auto
import json
import math


class TechCategory(Enum):
    """Categories for organizing technologies."""
    AGRICULTURE = auto()
    MILITARY = auto()
    ECONOMY = auto()
    SCIENCE = auto()
    CULTURE = auto()
    EXPLORATION = auto()
    INFRASTRUCTURE = auto()
    METALLURGY = auto()


class Age(Enum):
    """Technological ages that civilizations progress through."""
    DISSEMINATION = "Age of Dissemination"  # Stone Age equivalent
    COPPER = "Copper Age"
    BRONZE = "Bronze Age"
    IRON = "Iron Age"
    CLASSICAL = "Classical Age"
    MEDIEVAL = "Medieval Age"
    RENAISSANCE = "Renaissance Age"
    INDUSTRIAL = "Industrial Age"
    
    @property
    def min_techs_required(self) -> int:
        """Minimum number of technologies required to advance to this age."""
        requirements = {
            Age.DISSEMINATION: 0,
            Age.COPPER: 3,
            Age.BRONZE: 8,
            Age.IRON: 15,
            Age.CLASSICAL: 25,
            Age.MEDIEVAL: 40,
            Age.RENAISSANCE: 60,
            Age.INDUSTRIAL: 85,
        }
        return requirements.get(self, 0)
    
    @property
    def resource_requirements(self) -> Set[str]:
        """Resources required to enter this age."""
        requirements = {
            Age.DISSEMINATION: set(),
            # Earlier ages no longer require specific metal ores; only coal is
            # needed for the Industrial Age.
            Age.COPPER: set(),
            Age.BRONZE: set(),
            Age.IRON: set(),
            Age.CLASSICAL: set(),
            Age.MEDIEVAL: set(),
            Age.RENAISSANCE: set(),
            Age.INDUSTRIAL: {"coal"},
        }
        return requirements.get(self, set())
    
    def next(self) -> Optional[Age]:
        """Get the next age in progression."""
        ages = list(Age)
        current_idx = ages.index(self)
        if current_idx < len(ages) - 1:
            return ages[current_idx + 1]
        return None


@dataclass
class TechBonus:
    """Bonuses provided by a technology."""
    food_multiplier: float = 1.0
    production_multiplier: float = 1.0
    population_growth_rate: float = 0.0
    military_strength: float = 0.0
    movement_speed: float = 0.0
    territory_expansion_rate: float = 0.0
    research_speed: float = 0.0
    trade_income: float = 0.0
    agricultural_efficiency: float = 0.0  # Reduces workforce needed for farming
    
    def apply_to_yields(self, base_food: float, base_prod: float) -> Tuple[float, float]:
        """Apply technology bonuses to base yields."""
        return (base_food * self.food_multiplier, 
                base_prod * self.production_multiplier)


@dataclass
class Technology:
    """Represents a single technology in the tech tree."""
    tech_id: str
    name: str
    category: TechCategory
    description: str
    research_cost: int
    prerequisites: List[str] = field(default_factory=list)
    required_age: Age = Age.DISSEMINATION
    required_resources: Set[str] = field(default_factory=set)
    bonuses: TechBonus = field(default_factory=TechBonus)
    unlocks_units: List[str] = field(default_factory=list)
    unlocks_buildings: List[str] = field(default_factory=list)
    # Generic unlock flags (used for society choice in the tests)
    unlocks: Dict[str, bool] = field(default_factory=dict)
    
    def can_research(self, 
                     researched: Set[str], 
                     current_age: Age,
                     available_resources: Set[str]) -> bool:
        """Check if this technology can be researched."""
        # Check prerequisites
        if not all(prereq in researched for prereq in self.prerequisites):
            return False
        
        # Check age requirement
        ages = list(Age)
        if ages.index(current_age) < ages.index(self.required_age):
            return False
        
        # Check resource requirements
        if not self.required_resources.issubset(available_resources):
            return False
        
        return True


class TechTree:
    """The complete technology tree for the game."""
    
    def __init__(self):
        self.technologies: Dict[str, Technology] = {}
        self._initialize_technologies()
    
    def _initialize_technologies(self):
        """Initialize the default technology tree."""
        
        # Age of Dissemination (Stone Age)
        self.add_technology(Technology(
            tech_id="agriculture",
            name="Agriculture",
            category=TechCategory.AGRICULTURE,
            description="Develop basic farming techniques",
            research_cost=10,
            required_age=Age.DISSEMINATION,
            bonuses=TechBonus(food_multiplier=1.3, population_growth_rate=0.01, agricultural_efficiency=0.1)
        ))
        
        self.add_technology(Technology(
            tech_id="animal_husbandry",
            name="Animal Husbandry",
            category=TechCategory.AGRICULTURE,
            description="Domesticate animals for food and labor",
            research_cost=12,
            required_age=Age.DISSEMINATION,
            bonuses=TechBonus(food_multiplier=1.2, production_multiplier=1.1)
        ))

        # Proto-Governance unlocks society choice
        self.add_technology(Technology(
            tech_id="proto_governance",
            name="Proto-Governance",
            category=TechCategory.CULTURE,
            description="Early forms of societal organisation",
            research_cost=20,
            prerequisites=["agriculture", "animal_husbandry"],
            required_age=Age.DISSEMINATION,
            unlocks={"society_choice": True},
        ))
        
        self.add_technology(Technology(
            tech_id="pottery",
            name="Pottery",
            category=TechCategory.CULTURE,
            description="Create ceramic vessels for storage",
            research_cost=8,
            required_age=Age.DISSEMINATION,
            bonuses=TechBonus(food_multiplier=1.1)
        ))
        
        self.add_technology(Technology(
            tech_id="stone_tools",
            name="Stone Tools",
            category=TechCategory.MILITARY,
            description="Craft basic tools and weapons from stone",
            research_cost=5,
            required_age=Age.DISSEMINATION,
            bonuses=TechBonus(production_multiplier=1.2, military_strength=2.0)
        ))
        
        # Copper Age
        self.add_technology(Technology(
            tech_id="copper_working",
            name="Copper Working",
            category=TechCategory.METALLURGY,
            description="Smelt and work copper into tools",
            research_cost=20,
            prerequisites=["stone_tools"],
            required_age=Age.COPPER,
            bonuses=TechBonus(production_multiplier=1.3, military_strength=5.0)
        ))
        
        self.add_technology(Technology(
            tech_id="wheel",
            name="The Wheel",
            category=TechCategory.INFRASTRUCTURE,
            description="Revolutionary invention for transportation",
            research_cost=15,
            required_age=Age.COPPER,
            bonuses=TechBonus(movement_speed=0.3, trade_income=0.2)
        ))
        
        self.add_technology(Technology(
            tech_id="writing",
            name="Writing",
            category=TechCategory.SCIENCE,
            description="Develop a system for recording information",
            research_cost=25,
            prerequisites=["pottery"],
            required_age=Age.COPPER,
            bonuses=TechBonus(research_speed=0.2, trade_income=0.1)
        ))
        
        # Bronze Age
        self.add_technology(Technology(
            tech_id="bronze_working",
            name="Bronze Working",
            category=TechCategory.METALLURGY,
            description="Alloy copper and tin to create bronze",
            research_cost=35,
            prerequisites=["copper_working"],
            required_age=Age.BRONZE,
            bonuses=TechBonus(production_multiplier=1.4, military_strength=10.0)
        ))
        
        self.add_technology(Technology(
            tech_id="mathematics",
            name="Mathematics",
            category=TechCategory.SCIENCE,
            description="Develop numerical systems and calculations",
            research_cost=30,
            prerequisites=["writing"],
            required_age=Age.BRONZE,
            bonuses=TechBonus(research_speed=0.15, production_multiplier=1.1)
        ))
        
        self.add_technology(Technology(
            tech_id="irrigation",
            name="Irrigation",
            category=TechCategory.AGRICULTURE,
            description="Channel water to improve farming",
            research_cost=25,
            prerequisites=["agriculture"],
            required_age=Age.BRONZE,
            bonuses=TechBonus(food_multiplier=1.4, territory_expansion_rate=0.1, agricultural_efficiency=0.15)
        ))
        
        # Iron Age
        self.add_technology(Technology(
            tech_id="iron_working",
            name="Iron Working",
            category=TechCategory.METALLURGY,
            description="Smelt and forge iron tools and weapons",
            research_cost=50,
            prerequisites=["bronze_working"],
            required_age=Age.IRON,
            bonuses=TechBonus(production_multiplier=1.5, military_strength=20.0)
        ))
        
        self.add_technology(Technology(
            tech_id="currency",
            name="Currency",
            category=TechCategory.ECONOMY,
            description="Standardized money for trade",
            research_cost=40,
            prerequisites=["mathematics", "bronze_working"],
            required_age=Age.IRON,
            bonuses=TechBonus(trade_income=0.5, production_multiplier=1.2)
        ))
        
        self.add_technology(Technology(
            tech_id="philosophy",
            name="Philosophy",
            category=TechCategory.CULTURE,
            description="Systematic study of fundamental questions",
            research_cost=45,
            prerequisites=["writing"],
            required_age=Age.IRON,
            bonuses=TechBonus(research_speed=0.2)
        ))
        
        self.add_technology(Technology(
            tech_id="crop_rotation",
            name="Crop Rotation",
            category=TechCategory.AGRICULTURE,
            description="Systematic crop rotation increases soil fertility",
            research_cost=35,
            prerequisites=["irrigation", "iron_working"],
            required_age=Age.IRON,
            bonuses=TechBonus(food_multiplier=1.2, agricultural_efficiency=0.2)
        ))
    
    def add_technology(self, tech: Technology):
        """Add a technology to the tree."""
        self.technologies[tech.tech_id] = tech
    
    def get_available_technologies(self, 
                                   researched: Set[str],
                                   current_age: Age,
                                   available_resources: Set[str]) -> List[Technology]:
        """Get all technologies available for research."""
        available = []
        for tech_id, tech in self.technologies.items():
            if tech_id not in researched and tech.can_research(researched, current_age, available_resources):
                available.append(tech)
        return available


@dataclass
class CivTechState:
    """Technology state for a single civilization."""
    civ_id: int
    current_age: Age = Age.DISSEMINATION
    researched_techs: Set[str] = field(default_factory=set)
    current_research: Optional[str] = None
    research_progress: float = 0.0
    research_points_accumulated: float = 0.0
    available_resources: Set[str] = field(default_factory=set)
    
    def start_research(self, tech_id: str):
        """Begin researching a new technology."""
        self.current_research = tech_id
        self.research_progress = 0.0
    
    def add_research_points(self, points: float, tech_tree: TechTree) -> bool:
        """Add research points to current research. Returns True if completed."""
        if not self.current_research:
            return False
        
        tech = tech_tree.technologies.get(self.current_research)
        if not tech:
            return False
        
        self.research_progress += points
        self.research_points_accumulated += points
        
        if self.research_progress >= tech.research_cost:
            self.researched_techs.add(self.current_research)
            self.current_research = None
            self.research_progress = 0.0
            return True
        return False
    
    def can_advance_age(self, tech_tree: TechTree) -> bool:
        """Check if civilization can advance to the next age."""
        next_age = self.current_age.next()
        if not next_age:
            return False
        
        # Check tech count requirement
        if len(self.researched_techs) < next_age.min_techs_required:
            return False
        
        # Check resource requirements
        if not next_age.resource_requirements.issubset(self.available_resources):
            return False
        
        return True
    
    def advance_age(self) -> bool:
        """Advance to the next age if possible."""
        if self.can_advance_age(None):  # Note: tech_tree not needed for basic check
            next_age = self.current_age.next()
            if next_age:
                self.current_age = next_age
                return True
        return False
    
    def calculate_total_bonuses(self, tech_tree: TechTree) -> TechBonus:
        """Calculate cumulative bonuses from all researched technologies."""
        total = TechBonus()
        
        for tech_id in self.researched_techs:
            tech = tech_tree.technologies.get(tech_id)
            if tech:
                bonus = tech.bonuses
                # Multiply multipliers
                total.food_multiplier *= bonus.food_multiplier
                total.production_multiplier *= bonus.production_multiplier
                
                # Add flat bonuses
                total.population_growth_rate += bonus.population_growth_rate
                total.military_strength += bonus.military_strength
                total.movement_speed += bonus.movement_speed
                total.territory_expansion_rate += bonus.territory_expansion_rate
                total.research_speed += bonus.research_speed
                total.trade_income += bonus.trade_income
        
        return total
    
    def get_research_rate(self, base_science: float, tech_tree: TechTree) -> float:
        """Calculate research points generated per turn."""
        bonuses = self.calculate_total_bonuses(tech_tree)
        return base_science * (1.0 + bonuses.research_speed)


class TechnologySystem:
    """Main technology system manager."""
    
    def __init__(self):
        self.tech_tree = TechTree()
        self.civ_states: Dict[int, CivTechState] = {}
    
    def initialize_civ(self, civ_id: int, starting_resources: Set[str] = None) -> CivTechState:
        """Initialize technology state for a new civilization.

        Returns the created :class:`CivTechState` for convenience.
        """
        state = CivTechState(
            civ_id=civ_id,
            available_resources=starting_resources or set()
        )
        self.civ_states[civ_id] = state
        return state
    
    def update_civ_resources(self, civ_id: int, resources: Set[str]):
        """Update available resources for a civilization."""
        if civ_id in self.civ_states:
            self.civ_states[civ_id].available_resources = resources
    
    def process_research(self, civ_id: int, science_output: float) -> List[str]:
        """Process research for a civilization. Returns list of completed techs."""
        if civ_id not in self.civ_states:
            return []
        
        state = self.civ_states[civ_id]
        completed = []
        
        # Auto-select research if none active
        if not state.current_research:
            available = self.tech_tree.get_available_technologies(
                state.researched_techs,
                state.current_age,
                state.available_resources
            )
            if available:
                # Select cheapest available tech
                available.sort(key=lambda t: t.research_cost)
                state.start_research(available[0].tech_id)
        
        # Add research points
        if state.current_research:
            research_rate = state.get_research_rate(science_output, self.tech_tree)
            if state.add_research_points(research_rate, self.tech_tree):
                completed.append(state.current_research)
                
                # Check for age advancement
                if state.can_advance_age(self.tech_tree):
                    state.advance_age()
        
        return completed
    
    def get_civ_bonuses(self, civ_id: int) -> TechBonus:
        """Get total technology bonuses for a civilization."""
        if civ_id not in self.civ_states:
            return TechBonus()
        return self.civ_states[civ_id].calculate_total_bonuses(self.tech_tree)
    
    def save_state(self) -> Dict:
        """Save technology system state to dictionary."""
        return {
            "civ_states": {
                str(civ_id): {
                    "current_age": state.current_age.value,
                    "researched_techs": list(state.researched_techs),
                    "current_research": state.current_research,
                    "research_progress": state.research_progress,
                    "research_points_accumulated": state.research_points_accumulated,
                    "available_resources": list(state.available_resources)
                }
                for civ_id, state in self.civ_states.items()
            }
        }
    
    def load_state(self, data: Dict):
        """Load technology system state from dictionary."""
        self.civ_states = {}
        for civ_id_str, state_data in data.get("civ_states", {}).items():
            civ_id = int(civ_id_str)
            self.civ_states[civ_id] = CivTechState(
                civ_id=civ_id,
                current_age=Age(state_data["current_age"]),
                researched_techs=set(state_data["researched_techs"]),
                current_research=state_data.get("current_research"),
                research_progress=state_data.get("research_progress", 0.0),
                research_points_accumulated=state_data.get("research_points_accumulated", 0.0),
                available_resources=set(state_data.get("available_resources", []))
            )


# Integration helper functions for the engine

def apply_tech_bonuses_to_tile(tile, bonuses: TechBonus, base_food: float, base_prod: float):
    """Apply technology bonuses to a tile's yields."""
    modified_food, modified_prod = bonuses.apply_to_yields(base_food, base_prod)
    return modified_food, modified_prod


def calculate_civ_science_output(civ, world) -> float:
    """Calculate science output for a civilization based on their tiles and population."""
    science = 0.0
    for (q, r) in civ.tiles:
        tile = world.get_tile(q, r)
        # Science based on population and tile development
        tile_science = math.log(max(1, tile.pop)) * 0.5
        
        # Bonus for certain biomes (representing good locations for learning)
        if tile.biome in ["grass", "coast"]:
            tile_science *= 1.2
        
        science += tile_science
    
    return science


def detect_resources_in_territory(civ, world, feature_map=None) -> Set[str]:
    """Detect what resources a civilization has access to.

    The detection integrates with the ``TradeGoodsManager`` attached to the
    world and returns the names of any trade goods actively produced within the
    civilization's territory.  These names are lower-cased to match technology
    resource requirements (e.g. ``"coal"`` for the Industrial Age).
    """

    resources: Set[str] = set()
    trade_mgr = getattr(world, "trade_manager", None)
    if trade_mgr is not None:
        for q, r in civ.tiles:
            tg = trade_mgr.tile_goods.get((q, r))
            if not tg:
                continue
            for good in tg.active_goods.keys():
                resources.add(good.name.lower())

    if feature_map is not None:
        # Placeholder for more detailed detection based on map features
        pass
      
    return resources
