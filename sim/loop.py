from __future__ import annotations

import numpy as np

from .resources import yields_with_features, carrying_capacity
from .time import scale_to_years, step_date
from .settlements import (
    apply_urban_pressure, apply_growth_bonuses, 
    get_settlement_upgrade_candidate, enforce_settlement_population_hierarchy,
    get_evenq_hex_neighbors, SETTLEMENT_CONFIG
)


def advance_turn(
    ws,
    *,
    feature_map=None,
    rng_seed=None,
    growth_rate: float = 0.04,
    growth_variance: float = 0.2,
    food_per_pop: float = 1.0,
    disaster_rate: float = 0.02,
    min_settle_pop: float = 25.0,
    settler_cost: float = 10.0,
    pressure_threshold: float = 0.7,
    steps: int = 1,
) -> object:
    """Advance the world simulation by one turn.

    Parameters
    ----------
    ws : WorldState
        The world state to update in-place.
    feature_map : np.ndarray, optional
        Terrain feature identifiers aligning with the world's maps.
    rng_seed : int, optional
        Seed for deterministic random operations. Falls back to
        ``ws.seed ^ ws.turn`` when ``None``.
    growth_rate : float, default 0.04
        Base logistic growth rate per year.
    growth_variance : float, default 0.2
        Standard deviation of growth rate variation (as fraction of base rate).
    food_per_pop : float, default 1.0
        Food demand per population unit per year.
    disaster_rate : float, default 0.02
        Annual probability of population loss events (disease, disasters).
    min_settle_pop : float, default 40.0
        Minimum population required to send out a settler.
    settler_cost : float, default 15.0
        Population cost of founding a new settlement.
    pressure_threshold : float, default 0.8
        Population pressure ratio (pop/capacity) required for expansion.
    steps : int, default 1
        Number of time units to advance. ``max(1, int(steps))`` is used
        for time scaling.
    """

    if steps <= 0:
        # Allow explicit zero-step calls to bypass pause handling.
        step_count = 1
    else:
        step_count = int(steps)

    dt_years = scale_to_years(ws.time_scale) * max(1, step_count)

    if ws.paused and steps > 0:
        return ws

    # --- Resource yields and carrying capacity ---------------------------------
    yields = yields_with_features(ws.biome_map, feature_map)
    food = yields["food"]
    K = carrying_capacity(food)
    
    # Adjust carrying capacity based on settlement type and terrain
    h, w = ws.settlement_map.shape
    for r in range(h):
        for c in range(w):
            settlement_type = int(ws.settlement_map[r, c])
            biome = int(ws.biome_map[r, c])
            
            # Settlement type adjustments
            if settlement_type == 0:  # Hamlet
                K[r, c] = min(K[r, c], 50)  # Cap hamlet carrying capacity
                
            # Mountain penalties - much lower carrying capacity
            if biome == 2:  # Mountain
                K[r, c] = K[r, c] * 0.3  # Mountains support 30% of normal population
                K[r, c] = max(K[r, c], 5)  # But at least 5 people

    # --- Logistic growth with realistic variation and food budget --------------
    P = np.asarray(ws.pop_map, dtype=np.float32)
    
    # Add variation to growth rates based on local conditions
    # Base growth varies slightly by tile (representing local factors)
    rng = np.random.default_rng(rng_seed if rng_seed is not None else (ws.seed ^ ws.turn))
    
    # Growth rate variation based on parameter
    growth_variation = rng.normal(1.0, growth_variance, P.shape).astype(np.float32)
    growth_variation = np.clip(growth_variation, 0.5, 2.0)  # Prevent extreme values
    local_growth_rate = growth_rate * growth_variation
    
    # Apply settlement-based growth bonuses
    local_growth_rate = apply_growth_bonuses(local_growth_rate, ws.settlement_map)
    
    # Apply terrain penalties (mountain growth is slower)
    mountain_mask = (ws.biome_map == 2)
    local_growth_rate[mountain_mask] *= 0.5  # Mountains grow 50% slower
    
    # Basic logistic growth
    dP = (local_growth_rate * dt_years) * P * (1.0 - P / (K + 1e-6))
    P_next = P + dP

    # --- Food production and starvation effects --------------------------------
    produced = food * np.float32(200.0 * (dt_years / 1.0))
    demand = P_next * np.float32(food_per_pop * (dt_years / 1.0))
    ratio = np.divide(produced, demand, out=np.ones_like(produced), where=demand > 0)
    
    # More gradual starvation - populations don't instantly die
    starvation_factor = np.where(ratio < 1.0, 
                                np.clip(0.3 + 0.7 * ratio, 0.1, 1.0),  # Gradual decline
                                1.0)  # No bonus for excess food
    P_next = P_next * starvation_factor
    
    # --- Additional mortality factors -------------------------------------------
    # Random disasters (disease, natural disasters, etc.)
    # Small chance of population loss events
    disaster_chance = disaster_rate * dt_years
    disaster_mask = rng.random(P.shape) < disaster_chance
    disaster_severity = rng.uniform(0.7, 0.95, P.shape)  # Lose 5-30% of population
    disaster_factor = np.where(disaster_mask & (P_next > 1.0), disaster_severity, 1.0)
    P_next = P_next * disaster_factor

    P_next = np.clip(np.nan_to_num(P_next, nan=0.0, posinf=0.0, neginf=0.0), 0.0, None)
    
    # Cap unclaimed territory population to maximum of 10
    unclaimed_mask = (ws.owner_map < 0)
    P_next = np.where(unclaimed_mask, np.minimum(P_next, 10.0), P_next)
    
    # --- Urban pressure and settlement development ------------------------------
    # Apply population migration toward larger settlements
    def neighbors_axial_wrapper(q, r):
        from worldgen.hexgrid import neighbors_axial
        return neighbors_axial(q, r)
    
    P_next = apply_urban_pressure(P_next, ws.settlement_map, ws.owner_map, 
                                  neighbors_axial_wrapper, dt_years, rng)
    
    # Check for settlement upgrades and new settlement creation
    unique_civs = np.unique(ws.owner_map[ws.owner_map >= 0])
    for civ_id in unique_civs:
        # Try to upgrade existing hamlets to settlements
        upgrades = get_settlement_upgrade_candidate(
            ws.settlement_map, P_next, ws.owner_map, ws.biome_map, 
            ws.height_map, food, int(civ_id), rng
        )
        for r, c, new_type in upgrades:
            # Only upgrade if random chance succeeds (makes it gradual)
            if rng.random() < 0.7:  # 70% chance per turn when conditions are met
                ws.settlement_map[r, c] = np.uint8(new_type)
        
        # Also look for good settlement locations that should be prioritized
        from .settlements import promote_best_hamlet_locations
        promoted = promote_best_hamlet_locations(
            ws.settlement_map, P_next, ws.owner_map, ws.biome_map, 
            ws.height_map, food, int(civ_id), rng
        )
        for r, c in promoted:
            if rng.random() < 0.5:  # 50% chance for direct promotion
                ws.settlement_map[r, c] = np.uint8(1)  # Promote to village
    
    # Ensure capitals remain the most populated tile for each civilization
    for civ_id in unique_civs:
        civ_mask = (ws.owner_map == civ_id)
        if not np.any(civ_mask):
            continue
            
        # Find current capital and most populated tile
        capital_mask = (ws.settlement_map == 4) & civ_mask
        current_capital = np.argwhere(capital_mask)
        
        if len(current_capital) == 0:
            # No capital found, make the most populated tile the capital
            civ_pops = P_next[civ_mask]
            if len(civ_pops) > 0:
                max_pop_idx = np.argmax(civ_pops)
                civ_coords = np.argwhere(civ_mask)
                max_pop_coord = civ_coords[max_pop_idx]
                ws.settlement_map[max_pop_coord[0], max_pop_coord[1]] = np.uint8(4)
        else:
            # Capital exists, check if it's still the most populated
            capital_coord = current_capital[0]  # Take first if multiple (shouldn't happen)
            capital_r, capital_c = capital_coord[0], capital_coord[1]
            capital_pop = P_next[capital_r, capital_c]
            
            # Find most populated tile in this civilization
            civ_pops = P_next[civ_mask]
            max_pop = np.max(civ_pops)
            
            # If capital is not the most populated, move capital to most populated tile
            if capital_pop < max_pop - 1e-6:  # Small epsilon to avoid float precision issues
                # Remove capital status from current capital (keep as city if large enough)
                if capital_pop >= 200:
                    ws.settlement_map[capital_r, capital_c] = np.uint8(3)  # Demote to city
                elif capital_pop >= 100:
                    ws.settlement_map[capital_r, capital_c] = np.uint8(2)  # Demote to town
                else:
                    ws.settlement_map[capital_r, capital_c] = np.uint8(1)  # Demote to village
                
                # Find the most populated tile and make it capital
                max_pop_idx = np.argmax(civ_pops)
                civ_coords = np.argwhere(civ_mask)
                max_pop_coord = civ_coords[max_pop_idx]
                new_capital_r, new_capital_c = max_pop_coord[0], max_pop_coord[1]
                ws.settlement_map[new_capital_r, new_capital_c] = np.uint8(4)
                
                # Give the new capital a small population boost to help it stay on top
                P_next[new_capital_r, new_capital_c] = P_next[new_capital_r, new_capital_c] * 1.1
    
    # Enforce realistic population distribution - settlements should be population centers
    P_next = enforce_settlement_population_hierarchy(P_next, ws.settlement_map, ws.owner_map)
    
    # Occasionally add small variations to empty province populations (every ~10 turns)
    if ws.turn > 0 and ws.turn % 10 == 0:
        from .population_seeding import apply_natural_variation
        P_next = apply_natural_variation(P_next, ws.owner_map, 
                                       variation_factor=0.05, 
                                       seed=ws.seed ^ ws.turn)
    
    ws.pop_map = P_next.astype(np.float32)

    # --- Territorial expansion based on population pressure --------------------
    # Expansion happens when population pressure exceeds threshold
    owner = ws.owner_map
    pop = ws.pop_map
    h, w = owner.shape
    
    # Calculate population pressure (pop / carrying_capacity)
    pressure = np.divide(pop, K, out=np.zeros_like(pop), where=K > 0)
    # Only consider tiles with high pressure and minimum settler capability
    high_pressure_mask = (pressure >= pressure_threshold) & (pop >= (min_settle_pop + settler_cost)) & (owner >= 0)
    candidates = np.argwhere(high_pressure_mask)
    
    if candidates.size:
        # Sort by pressure (highest first) for more realistic expansion
        pressures_at_candidates = pressure[candidates[:, 0], candidates[:, 1]]
        order = np.argsort(pressures_at_candidates)[::-1]  # Descending order
        
        for idx in order:
            y, x = candidates[idx]
            civ = owner[y, x]
            current_pressure = pressure[y, x]
            
            # Probabilistic expansion based on pressure level
            # Higher pressure = higher chance to expand  
            expansion_prob = min(1.0, (current_pressure - pressure_threshold) * 3.0)
            if rng.random() > expansion_prob:
                continue
                
            # Get hex neighbors using axial coordinates (convert from array indices)
            # Array uses (row, col) but hex logic uses axial (q, r)
            current_q, current_r = x, y  # Convert array indices to axial coordinates
            
            # Get axial neighbors and convert back to array indices
            from worldgen.hexgrid import neighbors6
            neigh_axial = neighbors6(current_q, current_r)
            neigh = [(nr, nq) for nq, nr in neigh_axial if 0 <= nq < w and 0 <= nr < h]
            
            # Only consider empty land tiles (not ocean or already owned)
            # Mountains are now colonizable but with penalties
            empty = [(ny, nx) for ny, nx in neigh 
                     if owner[ny, nx] < 0 and ws.biome_map[ny, nx] != 3]  # Exclude only ocean (3)
            if not empty:
                continue
            best_food = -1.0
            best_choices: list[tuple[int, int]] = []
            for ny, nx in empty:
                fval = food[ny, nx]
                if fval > best_food + 1e-6:
                    best_food = float(fval)
                    best_choices = [(ny, nx)]
                elif abs(fval - best_food) <= 1e-6:
                    best_choices.append((ny, nx))

            if not best_choices:
                continue

            ny, nx = best_choices[0]
            if len(best_choices) > 1:
                ny, nx = best_choices[rng.integers(len(best_choices))]
            
            # Double-check that the selected tile is actually adjacent (safety check)
            # Convert array indices to axial coordinates for proper neighbor checking
            source_q, source_r = x, y  # Convert array indices to axial coordinates
            target_q, target_r = nx, ny
            
            # Verify the target is in our neighbor list using axial coordinates
            from worldgen.hexgrid import neighbors6
            valid_neighbors_axial = neighbors6(source_q, source_r)
            if (target_q, target_r) not in valid_neighbors_axial:
                continue  # Skip this expansion if somehow not adjacent
            
            # Double-check that target tile is colonizable (not ocean)
            target_biome = ws.biome_map[target_r, target_q]
            if target_biome == 3:  # Ocean only
                continue  # Skip this expansion if invalid terrain
                
            owner[ny, nx] = civ
            # Add settler population to any existing population in the new territory
            existing_pop = float(pop[ny, nx])
            
            # Mountain colonization costs more settlers and yields less initial population
            target_biome = ws.biome_map[ny, nx]
            if target_biome == 2:  # Mountain
                mountain_cost_multiplier = 2.0  # Costs 2x as many settlers
                mountain_pop_penalty = 0.5  # Settlers only establish 50% population
                actual_settler_cost = settler_cost * mountain_cost_multiplier
                initial_mountain_pop = (settler_cost + 5) * mountain_pop_penalty
                
                # Check if source has enough population for mountain colonization
                if pop[y, x] >= actual_settler_cost:
                    pop[ny, nx] = np.float32(initial_mountain_pop + existing_pop)
                    pop[y, x] = np.float32(max(0.0, pop[y, x] - actual_settler_cost))
                else:
                    # Can't afford mountain colonization, skip
                    continue
            else:
                # Normal colonization
                pop[ny, nx] = np.float32(settler_cost + 5 + existing_pop)
                pop[y, x] = np.float32(max(0.0, pop[y, x] - settler_cost))
            # New settlements start as hamlets, but check if they can be settlements at all
            # Most expanded territories should remain pure hamlets for realistic spacing
            from .settlements import has_nearby_settlements
            if has_nearby_settlements(ny, nx, ws.settlement_map, min_distance=3):
                # Too close to settlements, just remain as hamlet with limited population
                ws.settlement_map[ny, nx] = np.uint8(0)  # Hamlet
                # Cap population to maintain settlement hierarchy
                pop[ny, nx] = min(pop[ny, nx], 35)  # Lower cap for rural tiles
            else:
                ws.settlement_map[ny, nx] = np.uint8(0)  # Start as hamlet anyway
        ws.owner_map = owner
        ws.pop_map = pop
    
    # Apply smart border filling every few turns to claim enclosed areas
    if ws.turn > 0 and ws.turn % 5 == 0:
        from .border_filling import apply_smart_borders
        ws.owner_map = apply_smart_borders(ws.owner_map, ws.biome_map)

    # --- Advance calendar and turn ---------------------------------------------
    m, d, y = ws.get_date_tuple()
    m, d, y = step_date(m, d, y, ws.time_scale, steps=max(1, step_count))
    ws.set_date_tuple(m, d, y)
    ws.turn += 1

    return ws
