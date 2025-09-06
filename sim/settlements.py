"""Settlement growth and expansion mechanics for civilization simulation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from typing import List, Tuple, Dict

# Settlement type constants
HAMLET = 0
VILLAGE = 1  
TOWN = 2
CITY = 3
CAPITAL = 4

# Settlement thresholds and properties
SETTLEMENT_CONFIG = {
    HAMLET: {
        "name": "hamlet",
        "min_pop": 0,
        "max_pop": None,  # No population limit for hamlets
        "growth_bonus": 0.0,  # No growth bonus
        "can_upgrade": False,  # Hamlets cannot upgrade
        "urban_pressure": 0.02,  # Slight pressure to move to better opportunities
    },
    VILLAGE: {
        "name": "village", 
        "min_pop": 40,
        "max_pop": 120,
        "growth_bonus": 0.15,  # 15% faster growth
        "can_upgrade": True,
        "urban_pressure": 0.05,  # Reduced pressure to keep rural populations
    },
    TOWN: {
        "name": "town",
        "min_pop": 100, 
        "max_pop": 400,
        "growth_bonus": 0.2,  # 20% faster growth
        "can_upgrade": True,
        "urban_pressure": 0.1,  # Reduced pressure to keep rural populations
    },
    CITY: {
        "name": "city",
        "min_pop": 200,
        "max_pop": 1000,
        "growth_bonus": 0.3,  # 30% faster growth
        "can_upgrade": False,  # Cities are max level (except capitals)
        "urban_pressure": 0.0,  # Cities attract population
    },
    CAPITAL: {
        "name": "capital",
        "min_pop": 100,
        "max_pop": None,  # No population limit
        "growth_bonus": 0.3,  # 30% faster growth (reduced from 0.5)
        "can_upgrade": False,
        "urban_pressure": 0.0,  # No pressure to preserve rural populations
    }
}


def can_become_settlement(biome_type: int, height: float, food_yield: float) -> bool:
    """Check if a tile can support village+ level settlements."""
    # Ocean cannot support settlements
    if biome_type == 3:
        return False
    
    # Mountains can support settlements but with higher requirements
    if biome_type == 2:  # Mountain
        return food_yield >= 0.8 and height > 0.3  # Lower food requirement but higher height
    
    # Other terrain types (normal requirements)
    return food_yield >= 1.0 and height > 0.1


def get_evenq_hex_neighbors(r: int, q: int, h: int, w: int) -> List[Tuple[int, int]]:
    """Get the 6 direct hex neighbors using even-q offset coordinates.
    
    Args:
        r: row (0 to h-1)
        q: column (0 to w-1) 
        h: map height
        w: map width
    
    Returns:
        List of (row, col) tuples for valid neighbors
    """
    neighbors = []
    
    # Even-q offset hex neighbors (flat-top hexes)
    # Reference: https://www.redblobgames.com/grids/hexagons/#neighbors-offset
    if q % 2 == 0:  # Even column
        neighbor_offsets = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
    else:  # Odd column  
        neighbor_offsets = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
    
    for dr, dq in neighbor_offsets:
        nr, nq = r + dr, q + dq
        if 0 <= nr < h and 0 <= nq < w:
            neighbors.append((nr, nq))
    
    return neighbors


def get_neighbors_within_distance(r: int, c: int, distance: int, h: int, w: int) -> List[Tuple[int, int]]:
    """Get all hex neighbors within a given distance using even-q coordinates."""
    neighbors = []
    
    for dr in range(-distance, distance + 1):
        for dc in range(-distance, distance + 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and (dr != 0 or dc != 0):
                # Check if within hex distance (approximate)
                hex_dist = max(abs(dr), abs(dc), abs(dr + dc))
                if hex_dist <= distance:
                    neighbors.append((nr, nc))
    
    return neighbors


def has_nearby_settlements(r: int, c: int, settlement_map: NDArray[np.uint8], 
                          min_distance: int = 2) -> bool:
    """Check if there are any settlements within min_distance tiles."""
    h, w = settlement_map.shape
    neighbors = get_neighbors_within_distance(r, c, min_distance, h, w)
    
    for nr, nc in neighbors:
        if settlement_map[nr, nc] >= VILLAGE:  # Village or higher
            return True
    
    return False


def is_good_settlement_location(r: int, c: int, settlement_map: NDArray[np.uint8], 
                               civ_mask: NDArray[np.bool_], min_distance_from_capital: int = 2) -> bool:
    """Check if a location is good for settlement upgrade (proper distance from capital)."""
    h, w = settlement_map.shape
    
    # Find capital location for this civilization
    capital_locations = np.argwhere((settlement_map == CAPITAL) & civ_mask)
    
    if len(capital_locations) == 0:
        return True  # No capital found, allow settlement anywhere
    
    # Check distance from each capital (in case of multiple, though there should be one)
    for cap_r, cap_c in capital_locations:
        # Calculate approximate hex distance
        distance = max(abs(r - cap_r), abs(c - cap_c))
        if distance >= min_distance_from_capital:
            return True  # Far enough from this capital
    
    return False  # Too close to capital(s)


def get_settlement_upgrade_candidate(settlement_map: NDArray[np.uint8], 
                                   pop_map: NDArray[np.float32],
                                   owner_map: NDArray[np.int32],
                                   biome_map: NDArray[np.uint8], 
                                   height_map: NDArray[np.float32],
                                   food_yields: NDArray[np.float32],
                                   civ_id: int,
                                   rng: np.random.Generator) -> List[Tuple[int, int, int]]:
    """Find candidate tiles for settlement upgrades.
    
    Returns list of (row, col, new_settlement_type) tuples.
    """
    h, w = settlement_map.shape
    candidates = []
    
    # Find all tiles owned by this civilization
    civ_mask = (owner_map == civ_id)
    
    for r in range(h):
        for c in range(w):
            if not civ_mask[r, c]:
                continue
                
            current_settlement = int(settlement_map[r, c])
            current_pop = float(pop_map[r, c])
            
            # Skip capitals - they don't upgrade
            if current_settlement == CAPITAL:
                continue
                
            # Check if this tile can support higher-level settlements
            if not can_become_settlement(biome_map[r, c], height_map[r, c], food_yields[r, c]):
                continue
            
            config = SETTLEMENT_CONFIG[current_settlement]
            
            # Check if population meets upgrade requirements and settlement can upgrade
            if config["can_upgrade"]:
                # For hamlet->village upgrades, check settlement spacing and population
                if current_settlement == HAMLET:
                    if has_nearby_settlements(r, c, settlement_map, min_distance=1):  # Allow closer settlements
                        continue  # Too close to other settlements
                    # Check distance from capital (should be at least 1 tile away)
                    if not is_good_settlement_location(r, c, settlement_map, civ_mask, min_distance_from_capital=1):
                        continue  
                    if current_pop >= 30:  # Lower threshold for hamlet->village
                        candidates.append((r, c, VILLAGE))
                elif current_settlement == VILLAGE and current_pop >= 80:   # Lower threshold
                    candidates.append((r, c, TOWN))  
                elif current_settlement == TOWN and current_pop >= 200:  # Lower threshold
                    candidates.append((r, c, CITY))
                    
    return candidates


def apply_urban_pressure(pop_map: NDArray[np.float32],
                        settlement_map: NDArray[np.uint8], 
                        owner_map: NDArray[np.int32],
                        neighbors_func,
                        dt_years: float,
                        rng: np.random.Generator) -> NDArray[np.float32]:
    """Apply urban pressure - population migration toward larger settlements."""
    h, w = pop_map.shape
    pop_changes = np.zeros_like(pop_map)
    
    for r in range(h):
        for c in range(w):
            owner = int(owner_map[r, c])
            if owner < 0:
                continue
                
            settlement_type = int(settlement_map[r, c])
            current_pop = float(pop_map[r, c])
            
            if current_pop <= 5:  # Too small to migrate
                continue
                
            config = SETTLEMENT_CONFIG[settlement_type]
            pressure = config["urban_pressure"]
            
            if pressure > 0:  # This settlement pushes people away
                # Find nearby larger settlements
                neigh = neighbors_func(c, r)  # Note: neighbors_func expects (q, r) format
                best_target = None
                best_attraction = 0
                
                for nc, nr in neigh:
                    if not (0 <= nr < h and 0 <= nc < w):
                        continue
                    if owner_map[nr, nc] != owner:  # Must be same civilization
                        continue
                        
                    neighbor_settlement = int(settlement_map[nr, nc])
                    neighbor_config = SETTLEMENT_CONFIG[neighbor_settlement]
                    
                    # Calculate attraction (larger settlements with negative pressure attract)
                    attraction = -neighbor_config["urban_pressure"] + (neighbor_settlement - settlement_type) * 0.1
                    
                    if attraction > best_attraction:
                        best_attraction = attraction
                        best_target = (nr, nc)
                
                if best_target and best_attraction > 0:
                    # Calculate migration amount - much more conservative
                    migration_rate = pressure * best_attraction * dt_years * 0.1  # Reduced from 0.5 to 0.1
                    migrants = min(current_pop * migration_rate, current_pop * 0.05)  # Max 5% per turn instead of 20%
                    
                    if migrants >= 1.0:
                        pop_changes[r, c] -= migrants
                        pop_changes[best_target[0], best_target[1]] += migrants
    
    return pop_map + pop_changes


def apply_frontier_migration(pop_map: NDArray[np.float32],
                           settlement_map: NDArray[np.uint8],
                           owner_map: NDArray[np.int32],
                           food_map: NDArray[np.float32],
                           dt_years: float,
                           rng: np.random.Generator) -> NDArray[np.float32]:
    """Apply population migration toward frontier territories and economic opportunities."""
    h, w = pop_map.shape
    pop_changes = np.zeros_like(pop_map)
    
    # For each civilization, apply internal migration
    unique_civs = np.unique(owner_map[owner_map >= 0])
    
    for civ_id in unique_civs:
        civ_mask = (owner_map == civ_id)
        civ_pop = pop_map[civ_mask]
        civ_food = food_map[civ_mask]
        
        if len(civ_pop) < 2:  # Need at least 2 tiles for migration
            continue
            
        # Find all tiles for this civilization
        civ_coords = np.argwhere(civ_mask)
        
        # Calculate attractiveness scores for each tile
        attractiveness = np.zeros(len(civ_coords))
        
        for i, (r, c) in enumerate(civ_coords):
            score = 0.0
            
            # Food production bonus
            score += food_map[r, c] * 0.3
            
            # Frontier bonus (tiles with fewer neighbors)
            neighbors_count = 0
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, 1), (1, -1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and owner_map[nr, nc] == civ_id:
                    neighbors_count += 1
            
            # Fewer neighbors = more frontier-like = more attractive
            frontier_bonus = (6 - neighbors_count) * 0.2
            score += frontier_bonus
            
            # Settlement type bonus (slight preference for settlements)
            settlement_type = int(settlement_map[r, c])
            if settlement_type > 0:
                score += settlement_type * 0.1
            
            # Avoid overcrowding - penalize tiles with very high population
            current_pop = pop_map[r, c]
            if current_pop > 80:  # High population penalty
                score -= (current_pop - 80) * 0.01
            elif current_pop < 20:  # Low population gets slight bonus
                score += (20 - current_pop) * 0.005
                
            attractiveness[i] = score
        
        # Apply migration between tiles
        migration_rate = dt_years * 0.03  # 3% base migration rate per year
        
        for i, (r, c) in enumerate(civ_coords):
            current_pop = pop_map[r, c]
            
            if current_pop <= 8:  # Too small to lose population
                continue
                
            current_attractiveness = attractiveness[i]
            
            # Find more attractive nearby destinations
            best_targets = []
            for j, (tr, tc) in enumerate(civ_coords):
                if i == j:
                    continue
                    
                # Calculate distance (simple Manhattan for now)
                distance = abs(r - tr) + abs(c - tc)
                if distance > 4:  # Only consider nearby tiles
                    continue
                    
                target_attractiveness = attractiveness[j]
                attractiveness_diff = target_attractiveness - current_attractiveness
                
                if attractiveness_diff > 0.1:  # Significant improvement needed
                    # Weight by distance (closer is better)
                    weighted_attractiveness = attractiveness_diff / (1 + distance * 0.3)
                    best_targets.append((j, tr, tc, weighted_attractiveness))
            
            if best_targets:
                # Sort by weighted attractiveness
                best_targets.sort(key=lambda x: x[3], reverse=True)
                
                # Migrate to top 1-2 destinations
                for _, tr, tc, weight in best_targets[:2]:
                    # Migration amount based on population pressure and attractiveness
                    migration_amount = current_pop * migration_rate * weight * 0.5
                    migration_amount = min(migration_amount, current_pop * 0.08)  # Max 8% per turn
                    
                    if migration_amount >= 1.0:
                        pop_changes[r, c] -= migration_amount
                        pop_changes[tr, tc] += migration_amount
                        current_pop -= migration_amount  # Update for multiple targets
    
    return pop_map + pop_changes


def apply_regional_balance(pop_map: NDArray[np.float32],
                         owner_map: NDArray[np.int32],
                         dt_years: float,
                         rng: np.random.Generator) -> NDArray[np.float32]:
    """Apply gentle population diffusion to balance regional densities within civilizations."""
    h, w = pop_map.shape
    pop_changes = np.zeros_like(pop_map)
    
    # Apply diffusion within each civilization
    unique_civs = np.unique(owner_map[owner_map >= 0])
    
    for civ_id in unique_civs:
        civ_mask = (owner_map == civ_id)
        
        # For each tile in the civilization
        for r in range(h):
            for c in range(w):
                if not civ_mask[r, c]:
                    continue
                    
                current_pop = pop_map[r, c]
                if current_pop <= 3:  # Too small for diffusion
                    continue
                
                # Check neighbors within same civilization
                total_diffusion = 0.0
                neighbor_count = 0
                
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, 1), (1, -1)]:
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < h and 0 <= nc < w and 
                        owner_map[nr, nc] == civ_id):
                        
                        neighbor_pop = pop_map[nr, nc]
                        
                        # Calculate population pressure difference
                        pop_diff = current_pop - neighbor_pop
                        
                        if pop_diff > 5:  # Significant difference
                            # Diffusion rate proportional to difference
                            diffusion_rate = dt_years * 0.01  # 1% base rate
                            diffusion_amount = pop_diff * diffusion_rate * 0.3  # 30% of difference
                            diffusion_amount = min(diffusion_amount, current_pop * 0.03)  # Max 3% per turn
                            
                            if diffusion_amount >= 0.5:
                                total_diffusion += diffusion_amount
                                pop_changes[nr, nc] += diffusion_amount
                                neighbor_count += 1
                
                if total_diffusion > 0:
                    pop_changes[r, c] -= total_diffusion
    
    return pop_map + pop_changes


def apply_growth_bonuses(growth_rates: NDArray[np.float32],
                        settlement_map: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Apply settlement-based growth rate bonuses."""
    h, w = settlement_map.shape
    bonused_rates = growth_rates.copy()
    
    for r in range(h):
        for c in range(w):
            settlement_type = int(settlement_map[r, c])
            if settlement_type in SETTLEMENT_CONFIG:
                bonus = SETTLEMENT_CONFIG[settlement_type]["growth_bonus"]
                bonused_rates[r, c] *= (1.0 + bonus)
                
    return bonused_rates


def enforce_settlement_population_hierarchy(pop_map: NDArray[np.float32],
                                          settlement_map: NDArray[np.uint8],
                                          owner_map: NDArray[np.int32]) -> NDArray[np.float32]:
    """Ensure settlement tiles always have more population than non-settlement tiles.
    
    This maintains realistic population distribution where settlements are population centers.
    """
    h, w = pop_map.shape
    result_pop = pop_map.copy()
    
    # For each civilization
    unique_civs = np.unique(owner_map[owner_map >= 0])
    
    for civ_id in unique_civs:
        civ_mask = (owner_map == civ_id)
        
        # Find all settlement and non-settlement tiles for this civ
        settlement_tiles = []
        non_settlement_tiles = []
        
        for r in range(h):
            for c in range(w):
                if not civ_mask[r, c]:
                    continue
                    
                settlement_type = int(settlement_map[r, c])
                pop = float(pop_map[r, c])
                
                if settlement_type >= VILLAGE:  # Village or higher
                    settlement_tiles.append((r, c, settlement_type, pop))
                else:  # Hamlet
                    non_settlement_tiles.append((r, c, pop))
        
        if not settlement_tiles:
            continue
            
        # Find minimum settlement population
        min_settlement_pop = min(pop for _, _, _, pop in settlement_tiles)
        
        # Cap non-settlement population to be less than smallest settlement
        max_allowed_hamlet_pop = max(20, min_settlement_pop * 0.7)  # 70% of smallest settlement
        
        for r, c, pop in non_settlement_tiles:
            if pop > max_allowed_hamlet_pop:
                # Move excess population to nearest settlement
                excess = pop - max_allowed_hamlet_pop
                result_pop[r, c] = max_allowed_hamlet_pop
                
                # Find nearest settlement to redistribute excess
                best_settlement = None
                best_distance = float('inf')
                
                for sr, sc, stype, spop in settlement_tiles:
                    distance = max(abs(r - sr), abs(c - sc))  # Hex distance approximation
                    if distance < best_distance:
                        best_distance = distance
                        best_settlement = (sr, sc)
                
                if best_settlement:
                    sr, sc = best_settlement
                    result_pop[sr, sc] += excess * 0.5  # Only redistribute half to avoid runaway growth
    
    return result_pop


def promote_best_hamlet_locations(settlement_map: NDArray[np.uint8],
                                 pop_map: NDArray[np.float32], 
                                 owner_map: NDArray[np.int32],
                                 biome_map: NDArray[np.uint8],
                                 height_map: NDArray[np.float32],
                                 food_yields: NDArray[np.float32],
                                 civ_id: int,
                                 rng: np.random.Generator) -> List[Tuple[int, int]]:
    """Find the best hamlet locations that should be promoted to villages.
    
    Prioritizes hamlets that are:
    - 2+ tiles from capital
    - 2+ tiles from other settlements  
    - Have good food/terrain
    - Have decent population (30+)
    """
    h, w = settlement_map.shape
    candidates = []
    
    # Find all hamlets owned by this civilization
    civ_mask = (owner_map == civ_id)
    
    for r in range(h):
        for c in range(w):
            if not civ_mask[r, c]:
                continue
                
            current_settlement = int(settlement_map[r, c])
            current_pop = float(pop_map[r, c])
            
            # Only consider hamlets with decent population
            if current_settlement != HAMLET or current_pop < 30:
                continue
                
            # Check if this tile can support settlements
            if not can_become_settlement(biome_map[r, c], height_map[r, c], food_yields[r, c]):
                continue
            
            # Check spacing from other settlements
            if has_nearby_settlements(r, c, settlement_map, min_distance=2):
                continue
                
            # Check distance from capital
            if not is_good_settlement_location(r, c, settlement_map, civ_mask, min_distance_from_capital=2):
                continue
                
            # Score this location by population and food yield
            score = current_pop + food_yields[r, c] * 10
            candidates.append((r, c, score))
    
    # Sort by score and return best candidates
    candidates.sort(key=lambda x: x[2], reverse=True)
    # Return up to 5 best locations per civ to encourage more settlements
    return [(r, c) for r, c, score in candidates[:5]]


def get_settlement_name(settlement_type: int) -> str:
    """Get display name for settlement type."""
    return SETTLEMENT_CONFIG.get(settlement_type, {}).get("name", "hamlet")