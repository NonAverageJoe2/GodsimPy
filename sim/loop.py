from __future__ import annotations

import numpy as np

from .resources import yields_with_features, carrying_capacity
from .time import scale_to_years, step_date


def advance_turn(
    ws,
    *,
    feature_map=None,
    rng_seed=None,
    growth_rate: float = 0.04,
    growth_variance: float = 0.2,
    food_per_pop: float = 1.0,
    disaster_rate: float = 0.02,
    min_settle_pop: float = 40.0,
    settler_cost: float = 15.0,
    pressure_threshold: float = 0.8,
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

    # --- Logistic growth with realistic variation and food budget --------------
    P = np.asarray(ws.pop_map, dtype=np.float32)
    
    # Add variation to growth rates based on local conditions
    # Base growth varies slightly by tile (representing local factors)
    rng = np.random.default_rng(rng_seed if rng_seed is not None else (ws.seed ^ ws.turn))
    
    # Growth rate variation based on parameter
    growth_variation = rng.normal(1.0, growth_variance, P.shape).astype(np.float32)
    growth_variation = np.clip(growth_variation, 0.5, 2.0)  # Prevent extreme values
    local_growth_rate = growth_rate * growth_variation
    
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
            expansion_prob = min(1.0, (current_pressure - pressure_threshold) * 2.0)
            if rng.random() > expansion_prob:
                continue
                
            # Use proper hex grid neighbors instead of square grid
            from worldgen.hexgrid import neighbors_axial, in_bounds
            q, r = x, y  # Convert from array indices to axial coordinates
            neigh = []
            for nq, nr in neighbors_axial(q, r):
                if in_bounds(nq, nr, w, h):
                    neigh.append((nr, nq))  # Convert back to array indices (y, x)
            empty = [(ny, nx) for ny, nx in neigh if owner[ny, nx] < 0]
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
                owner[ny, nx] = civ
                pop[ny, nx] = np.float32(settler_cost)
                pop[y, x] = np.float32(max(0.0, pop[y, x] - settler_cost))
        ws.owner_map = owner
        ws.pop_map = pop

    # --- Advance calendar and turn ---------------------------------------------
    m, d, y = ws.get_date_tuple()
    m, d, y = step_date(m, d, y, ws.time_scale, steps=max(1, step_count))
    ws.set_date_tuple(m, d, y)
    ws.turn += 1

    return ws
