"""
Realistic Colonization and Cultural Evolution System for GodsimPy

This system implements more realistic colonization patterns and dynamic culture spawning:
- Colonization based on geographical barriers, resource availability, and cultural factors
- Distance decay for colonization likelihood
- Cultural pressure and natural expansion patterns
- Dynamic spawning of new cultures in isolated regions over time
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List, Set
from enum import Enum, auto
import random
import math
import numpy as np
import json
import os

# Import existing systems
from society import SocietyType, DEFAULT_SOCIETY
from name_generator import NameGenerator


@dataclass 
class ColonizationContext:
    """Context information for colonization decisions."""
    source_tile: Tuple[int, int]
    target_tile: Tuple[int, int] 
    civ_id: int
    distance: int
    terrain_difficulty: float
    resource_value: float
    strategic_value: float
    cultural_compatibility: float
    population_pressure: float


class TerrainType(Enum):
    """Terrain types affecting colonization difficulty."""
    PLAINS = auto()
    FOREST = auto() 
    HILLS = auto()
    MOUNTAINS = auto()
    DESERT = auto()
    SWAMP = auto()
    COAST = auto()
    RIVER = auto()


class RealisticColonizationSystem:
    """Implements realistic colonization patterns based on geographical and cultural factors."""
    
    def __init__(self, world, rng_seed: int = 42):
        self.world = world
        self.rng = random.Random(rng_seed)
        
        # Load configuration
        self.config = self._load_config()
        
        # Colonization parameters
        col_config = self.config.get('colonization', {})
        self.base_colonization_range = col_config.get('base_colonization_range', 3)
        self.max_colonization_range = col_config.get('max_colonization_range', 8)
        self.distance_decay_factor = col_config.get('distance_decay_factor', 0.7)
        self.population_pressure_threshold = col_config.get('population_pressure_threshold', 25)
        self.settler_population_cost = col_config.get('settler_population_cost', 8)
        self.expansion_probability = col_config.get('expansion_attempt_probability', 0.15)
        
        # Terrain modifiers
        self.terrain_modifiers = self.config.get('terrain_modifiers', self._init_default_terrain_modifiers())
        
        # Cultural spawning parameters
        spawn_config = self.config.get('culture_spawning', {})
        self.culture_spawn_interval = spawn_config.get('spawn_interval_turns', 100)
        self.isolation_threshold = spawn_config.get('isolation_threshold_hexes', 5)
        self.min_spawn_population = spawn_config.get('min_spawn_population', 15)
        self.culture_spawn_probability = spawn_config.get('base_spawn_probability', 0.15)
        
        # Strategic bonuses
        self.strategic_bonuses = self.config.get('strategic_bonuses', {})
        
        # Track when cultures can spawn
        self.last_culture_spawn_turn = 0
        self.culture_spawn_cooldown = {}  # Track cooldowns by region
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'balance', 'realistic_colonization.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load colonization config ({e}), using defaults")
            return {}
    
    def _init_default_terrain_modifiers(self) -> Dict[str, float]:
        """Initialize default terrain difficulty modifiers for colonization."""
        return {
            'ocean': 0.0,        # Cannot colonize
            'mountain': 0.1,     # Very difficult
            'desert': 0.3,       # Difficult  
            'swamp': 0.4,        # Difficult
            'tundra': 0.5,       # Challenging
            'hills': 0.7,        # Moderate
            'forest': 0.8,       # Easier
            'grassland': 0.9,    # Easy
            'plains': 1.0,       # Easiest
            'river': 1.2,        # Bonus for rivers
        }
    
    def get_terrain_difficulty(self, biome: str) -> float:
        """Get colonization difficulty modifier for a biome."""
        return self.terrain_modifiers.get(biome.lower(), 0.5)
    
    def calculate_distance_decay(self, distance: int) -> float:
        """Calculate distance decay for colonization probability."""
        if distance == 0:
            return 1.0
        return max(0.01, self.distance_decay_factor ** distance)
    
    def assess_colonization_viability(self, context: ColonizationContext) -> float:
        """Assess overall viability of a colonization target."""
        # Get source and target tiles
        source_q, source_r = context.source_tile
        target_q, target_r = context.target_tile
        
        source_tile = self.world.get_tile(source_q, source_r)
        target_tile = self.world.get_tile(target_q, target_r)
        
        if not target_tile or target_tile.owner is not None:
            return 0.0
        
        # Base factors
        distance_factor = self.calculate_distance_decay(context.distance)
        terrain_factor = self.get_terrain_difficulty(target_tile.biome)
        
        # Resource attractiveness
        try:
            from resources import yields_for
            food_yield, prod_yield = yields_for(target_tile)
            resource_score = (food_yield * 2.0 + prod_yield) / 10.0
        except:
            resource_score = 0.5  # Default moderate value
        
        # Population pressure factor
        pressure_factor = min(2.0, max(0.5, source_tile.pop / self.population_pressure_threshold))
        
        # Strategic value (coastal access, rivers, etc.)
        strategic_bonus = 1.0
        if hasattr(target_tile, 'feature') and target_tile.feature:
            feature_lower = target_tile.feature.lower()
            if 'river' in feature_lower:
                strategic_bonus += self.strategic_bonuses.get('river_access', 0.3)
            if 'mountain' in feature_lower and 'pass' in feature_lower:
                strategic_bonus += self.strategic_bonuses.get('mountain_pass', 0.15)
        
        biome_lower = target_tile.biome.lower()
        if 'coast' in biome_lower or 'ocean' in biome_lower:
            strategic_bonus += self.strategic_bonuses.get('coastal_access', 0.2)
        
        # Fertile land bonus
        if biome_lower in ['grassland', 'plains', 'river']:
            strategic_bonus += self.strategic_bonuses.get('fertile_land', 0.25)
        
        # Combine all factors
        viability = (
            distance_factor * 
            terrain_factor * 
            resource_score * 
            pressure_factor * 
            strategic_bonus
        )
        
        return max(0.0, min(1.0, viability))
    
    def find_colonization_targets(self, civ_id: int) -> List[Tuple[Tuple[int, int], Tuple[int, int], float]]:
        """Find and score potential colonization targets for a civilization."""
        civ = self.world.civs.get(civ_id)
        if not civ:
            return []
        
        targets = []
        
        # Check expansion from each owned tile
        for source_q, source_r in civ.tiles:
            source_tile = self.world.get_tile(source_q, source_r)
            
            # Dynamic population pressure threshold based on food situation
            try:
                from workforce import WORKFORCE_SYSTEM
                total_pop = sum(self.world.get_tile(q, r).pop for q, r in civ.tiles)
                _, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(civ, self.world, None)
                food_pressure_ratio = total_pop / max(food_capacity, 1.0)
                
                # Lower threshold if food-limited (need to expand for more farmland)
                if food_pressure_ratio > 0.8:
                    effective_threshold = max(8, self.population_pressure_threshold * 0.5)
                else:
                    effective_threshold = self.population_pressure_threshold
            except:
                effective_threshold = self.population_pressure_threshold
            
            # Only expand from sufficiently populated tiles
            if source_tile.pop < effective_threshold:
                continue
            
            # Search in expanding rings
            for distance in range(1, self.base_colonization_range + 1):
                for target_q, target_r in self._get_tiles_at_distance(source_q, source_r, distance):
                    if not self.world.in_bounds(target_q, target_r):
                        continue
                    
                    context = ColonizationContext(
                        source_tile=(source_q, source_r),
                        target_tile=(target_q, target_r),
                        civ_id=civ_id,
                        distance=distance,
                        terrain_difficulty=0.0,  # Will be calculated
                        resource_value=0.0,      # Will be calculated  
                        strategic_value=0.0,     # Will be calculated
                        cultural_compatibility=1.0,  # Same civ
                        population_pressure=source_tile.pop / self.population_pressure_threshold
                    )
                    
                    viability = self.assess_colonization_viability(context)
                    if viability > 0.1:  # Minimum threshold
                        targets.append(((source_q, source_r), (target_q, target_r), viability))
        
        # Sort by viability score
        targets.sort(key=lambda x: x[2], reverse=True)
        return targets
    
    def _get_tiles_at_distance(self, center_q: int, center_r: int, distance: int) -> List[Tuple[int, int]]:
        """Get all tiles at exactly the specified distance from center."""
        tiles = []
        
        # Use ring algorithm for hex grids
        for i in range(distance):
            q = center_q - distance + i
            r = center_r + distance - i
            
            # Walk around the hex ring
            directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
            
            for direction in directions:
                for step in range(distance):
                    tiles.append((q, r))
                    q += direction[0] 
                    r += direction[1]
        
        return list(set(tiles))  # Remove duplicates
    
    def attempt_colonization(self, civ_id: int) -> bool:
        """Attempt to colonize a new tile for the given civilization."""
        targets = self.find_colonization_targets(civ_id)
        
        if not targets:
            return False
        
        civ = self.world.civs[civ_id]
        
        # Select target based on weighted probability
        total_weight = sum(score for _, _, score in targets[:5])  # Top 5 candidates
        if total_weight == 0:
            return False
        
        roll = self.rng.random() * total_weight
        cumulative = 0.0
        
        for source_pos, target_pos, score in targets[:5]:
            cumulative += score
            if roll <= cumulative:
                # Execute colonization
                source_q, source_r = source_pos
                target_q, target_r = target_pos
                
                source_tile = self.world.get_tile(source_q, source_r)
                target_tile = self.world.get_tile(target_q, target_r)
                
                # Transfer population
                settler_pop = min(self.settler_population_cost, source_tile.pop - 5)  # Leave minimum
                if settler_pop <= 0:
                    continue
                
                source_tile.pop -= settler_pop
                target_tile.pop = settler_pop
                target_tile.owner = civ_id
                
                # Update civilization
                civ.tiles.append((target_q, target_r))
                
                return True
        
        return False
    
    def identify_culture_spawn_candidates(self) -> List[Tuple[int, int, float]]:
        """Identify regions suitable for spawning new cultures."""
        candidates = []
        
        # Look for isolated, populated regions
        for q in range(self.world.width_hex):
            for r in range(self.world.height_hex):
                tile = self.world.get_tile(q, r)
                
                # Must be unowned with sufficient population
                if tile.owner is not None or tile.pop < self.min_spawn_population:
                    continue
                
                # Check isolation from existing civilizations
                min_distance_to_civ = float('inf')
                for civ_id, civ in self.world.civs.items():
                    for civ_q, civ_r in civ.tiles:
                        distance = max(abs(q - civ_q), abs(r - civ_r))  # Chebyshev distance
                        min_distance_to_civ = min(min_distance_to_civ, distance)
                
                if min_distance_to_civ >= self.isolation_threshold:
                    # Calculate spawn score based on population and resources
                    try:
                        from resources import yields_for
                        food_yield, prod_yield = yields_for(tile)
                        resource_score = food_yield + prod_yield * 0.5
                    except:
                        resource_score = 1.0
                    
                    spawn_score = (tile.pop / 100.0) * resource_score * min_distance_to_civ
                    candidates.append((q, r, spawn_score))
        
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates
    
    def attempt_culture_spawn(self, turn: int) -> bool:
        """Attempt to spawn a new culture/civilization."""
        if turn - self.last_culture_spawn_turn < self.culture_spawn_interval:
            return False
        
        candidates = self.identify_culture_spawn_candidates()
        if not candidates:
            return False
        
        # Check probability
        if self.rng.random() > self.culture_spawn_probability:
            return False
        
        # Select spawn location
        total_weight = sum(score for _, _, score in candidates[:3])  # Top 3 candidates
        if total_weight == 0:
            return False
        
        roll = self.rng.random() * total_weight
        cumulative = 0.0
        
        for q, r, score in candidates[:3]:
            cumulative += score
            if roll <= cumulative:
                return self.spawn_new_culture_at(q, r, turn)
        
        return False
    
    def spawn_new_culture_at(self, q: int, r: int, turn: int) -> bool:
        """Spawn a new civilization at the specified location."""
        tile = self.world.get_tile(q, r)
        if tile.owner is not None:
            return False
        
        # Generate new civilization
        try:
            # Try using the engine's spawn_civ method if available
            if hasattr(self.world, 'engine') and hasattr(self.world.engine, 'spawn_civ'):
                civ_id = self.world.engine.spawn_civ((q, r))
                self.last_culture_spawn_turn = turn
                return True
        except:
            pass
        
        # Fallback: manual civilization creation
        civ_id = len(self.world.civs)
        
        # Generate unique culture name and style
        name_gen = NameGenerator(self.world.seed + civ_id * 1337 + turn)
        
        # Choose linguistic style based on location and nearby biomes
        biome_styles = {
            'desert': ['arabic', 'persian'],
            'tundra': ['norse', 'slavic'],
            'forest': ['germanic', 'celtic'],
            'grassland': ['latin', 'greek'],
            'hills': ['celtic', 'turkic'],
            'mountain': ['tibetan', 'quechua'],
        }
        
        style_options = biome_styles.get(tile.biome.lower(), ['latin', 'greek'])
        linguistic_style = self.rng.choice(style_options)
        
        culture_name = name_gen.generate_culture_name(style=linguistic_style)
        country_name = name_gen.generate_country_name(style=linguistic_style)
        
        # Create civilization object (adapt to your Civ class structure)
        from engine import Civ  # Import your Civ class
        
        civ = Civ(
            civ_id=civ_id,
            name=country_name,
            stock_food=20,
            tiles=[(q, r)],
            main_culture=culture_name,
            linguistic_type=linguistic_style
        )
        
        # Add to world
        self.world.civs[civ_id] = civ
        tile.owner = civ_id
        
        # Set capital
        civ.capital = (q, r)
        
        self.last_culture_spawn_turn = turn
        return True
    
    def process_turn(self, turn: int, dt: float) -> None:
        """Process colonization and culture spawning for this turn."""
        # Attempt colonization for each civilization
        for civ_id in list(self.world.civs.keys()):
            civ = self.world.civs[civ_id]
            
            # Skip if civ is too small (but allow single-tile civs if food-pressured)
            if len(civ.tiles) < 1:
                continue
            
            # Check food pressure to determine expansion urgency
            try:
                from workforce import WORKFORCE_SYSTEM
                total_pop = sum(self.world.get_tile(q, r).pop for q, r in civ.tiles)
                _, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(civ, self.world, None)
                food_pressure_ratio = total_pop / max(food_capacity, 1.0)
                is_food_pressured = food_pressure_ratio > 0.8
            except:
                is_food_pressured = False
                food_pressure_ratio = 0.5
            
            # Food requirements based on pressure
            min_food_required = 15 if is_food_pressured else 30
            if civ.stock_food < min_food_required:
                continue
            
            # Probability of expansion attempt (higher if food-pressured)
            base_prob = self.expansion_probability
            size_bonus = len(civ.tiles) * 0.02
            resource_bonus = min(0.1, civ.stock_food / 1000.0)
            food_pressure_bonus = 0.2 if is_food_pressured else 0.0
            
            expansion_probability = min(0.4, base_prob + size_bonus + resource_bonus + food_pressure_bonus)
            
            if self.rng.random() < expansion_probability:
                self.attempt_colonization(civ_id)
        
        # Attempt culture spawning
        self.attempt_culture_spawn(turn)


def integrate_realistic_colonization(engine) -> None:
    """Integrate the realistic colonization system with the main engine."""
    if not hasattr(engine, 'realistic_colonization'):
        engine.realistic_colonization = RealisticColonizationSystem(
            engine.world, 
            rng_seed=engine.world.seed + 999
        )
    
    # Store original step method
    original_step = engine.step
    
    def enhanced_step(dt: float = 1.0 / 52.0):
        # Call original step
        result = original_step(dt)
        
        # Process realistic colonization
        try:
            engine.realistic_colonization.process_turn(engine.world.turn, dt)
        except Exception as e:
            print(f"Warning: Realistic colonization error: {e}")
        
        return result
    
    # Replace step method
    engine.step = enhanced_step
    
    print("Realistic colonization system integrated!")