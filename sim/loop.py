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
    food_per_pop: float = 1.0,
    expansion_every: int | None = None,
    min_settle_pop: float = 60.0,
    settler_cost: float = 10.0,
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
        Logistic growth rate per year.
    food_per_pop : float, default 1.0
        Food demand per population unit per year.
    expansion_every : int or None, default None
        If provided, trigger territorial expansion every ``n`` turns.
    min_settle_pop : float, default 60.0
        Minimum population required to send out a settler.
    settler_cost : float, default 10.0
        Population cost of founding a new settlement.
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

    # --- Logistic growth with food budget --------------------------------------
    P = np.asarray(ws.pop_map, dtype=np.float32)
    dP = (growth_rate * dt_years) * P * (1.0 - P / (K + 1e-6))
    P_next = P + dP

    produced = food * np.float32(50.0 * (dt_years / 1.0))
    demand = P_next * np.float32(food_per_pop * (dt_years / 1.0))
    ratio = np.divide(produced, demand, out=np.ones_like(produced), where=demand > 0)
    P_next = P_next * np.clip(ratio, 0.0, 1.0)

    P_next = np.clip(np.nan_to_num(P_next, nan=0.0, posinf=0.0, neginf=0.0), 0.0, None)
    ws.pop_map = P_next.astype(np.float32)

    # --- Territorial expansion --------------------------------------------------
    if (
        expansion_every is not None
        and expansion_every > 0
        and ws.turn % expansion_every == 0
    ):
        rng = np.random.default_rng(
        rng_seed if rng_seed is not None else (ws.seed ^ ws.turn)
        )
        owner = ws.owner_map
        pop = ws.pop_map
        h, w = owner.shape
        candidates = np.argwhere(pop >= (min_settle_pop + settler_cost))
        if candidates.size:
            order = rng.permutation(len(candidates))
            for idx in order:
                y, x = candidates[idx]
                civ = owner[y, x]
                if civ < 0:
                    continue
                neigh = []
                if y > 0:
                    neigh.append((y - 1, x))
                if y < h - 1:
                    neigh.append((y + 1, x))
                if x > 0:
                    neigh.append((y, x - 1))
                if x < w - 1:
                    neigh.append((y, x + 1))
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
