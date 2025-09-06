"""
Enhanced Colonization and Migration System for GodsimPy

- Internal migration (push/pull, connectivity, friction to avoid ping-pong)
- Strategic colonization with multiple strategies
- Cultural pressure & tile flips (guarded by core pop threshold)
- Trade routes and connectivity bonuses
- Deterministic RNG support
- dt-aware rates
- Safe bounds checks and clamping
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List, Set
from enum import Enum, auto
from collections import defaultdict, deque
import random
import math
import numpy as np

from . import config_colonization as C
from modifiers import MODIFIERS


# ----------- Strategy Enum ----------------------------------------------------

class ColonizationStrategy(Enum):
    EXPANSIONIST = auto()
    DEFENSIVE = auto()
    RESOURCE_FOCUSED = auto()
    COASTAL = auto()
    AGGRESSIVE = auto()


# ----------- Data classes -----------------------------------------------------

@dataclass
class MigrationPressure:
    push_factors: float = 0.0
    pull_factors: float = 0.0
    cultural_influence: float = 0.0
    connectivity: float = 0.0
    strategic_value: float = 0.0


# ----------- Helper utilities (robust to missing engine bits) ----------------

def _safe_get_tile(world, q: int, r: int):
    if q < 0 or r < 0 or q >= getattr(world, "width_hex", 0) or r >= getattr(world, "height_hex", 0):
        return None
    t = world.get_tile(q, r)
    return t

def _neighbors6(world, q: int, r: int):
    if hasattr(world, "neighbors6"):
        for nq, nr in world.neighbors6(q, r):
            yield nq, nr
        return
    # Fallback to worldgen.hexgrid if exposed
    try:
        from worldgen.hexgrid import neighbors6
        for pair in neighbors6(q, r):
            yield pair
    except Exception:
        # Degenerate fallback (no neighbors)
        return

def _distance(world, q1: int, r1: int, q2: int, r2: int) -> int:
    if hasattr(world, "distance"):
        return int(world.distance(q1, r1, q2, r2))
    try:
        from worldgen.hexgrid import distance
        return int(distance(q1, r1, q2, r2))
    except Exception:
        # axial Manhattan-ish fallback (approx)
        return abs(q1 - q2) + abs(r1 - r2)


def _yields_for(tile) -> Tuple[float, float]:
    """Return (food, prod). Robust if resources.yields_for isn't available."""
    try:
        from resources import yields_for as yf
        f, p = yf(tile)
        # sanitize
        if not (isinstance(f, (int, float)) and isinstance(p, (int, float))):
            return 0.0, 0.0
        if math.isnan(f) or math.isnan(p):
            return 0.0, 0.0
        return float(f), float(p)
    except Exception:
        # Fallback heuristic by biome if resources not available
        biome = getattr(tile, "biome", "unknown")
        if biome in ("grass", "plains"):
            return 1.0, 1.0
        if biome == "forest":
            return 0.8, 1.2
        if biome == "mountain":
            return 0.1, 1.5
        if biome == "desert":
            return 0.2, 0.4
        if biome == "ocean":
            return 0.1, 0.2
        return 0.5, 0.5


# ----------- Main system ------------------------------------------------------

class EnhancedColonizationSystem:
    def __init__(self, world, tech_system=None, rng: Optional[random.Random] = None, seed: Optional[int] = None):
        self.world = world
        self.tech_system = tech_system
        self.rng = rng or random.Random(seed if seed is not None else 0)
        self.migration_history: Dict[Tuple[int, int], deque[Tuple[int, float]]] = defaultdict(lambda: deque(maxlen=64))
        # store (turn, amount) of received migrants for friction
        self.recent_received_turns: Dict[Tuple[int, int], deque[int]] = defaultdict(lambda: deque(maxlen=64))
        self.trade_routes: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
        self.cultural_map = np.zeros((getattr(world, "height_hex", 0), getattr(world, "width_hex", 0)), dtype=np.float32)

    # ----- Pressure calculations ---------------------------------------------

    def calculate_migration_pressure(self, q: int, r: int) -> MigrationPressure:
        t = _safe_get_tile(self.world, q, r)
        if t is None:
            return MigrationPressure()

        pressure = MigrationPressure()
        pop = float(getattr(t, "_pop_float", getattr(t, "pop", 0.0)))

        food, prod = _yields_for(t)
        cap_per_food = max(
            MODIFIERS.min_food_eps,
            MODIFIERS.carrying_capacity_per_food * max(food, 0.0),
        )
        crowding = pop / cap_per_food

        # Push factors (crowding)
        if crowding > 0.8:
            pressure.push_factors += (crowding - 0.8) * 2.0
        elif crowding < 0.3:
            pressure.push_factors -= 0.5  # acts like pull

        # Pull factors (resources + terrain)
        pressure.pull_factors = max(0.0, food * 0.5 + prod * 0.3)
        biome = getattr(t, "biome", "unknown")
        if biome == "grass":
            pressure.pull_factors += 0.3
        elif biome == "mountain":
            pressure.pull_factors -= 0.5
            pressure.push_factors += 0.2
        elif biome == "ocean":
            pressure.pull_factors -= 1.0
            pressure.push_factors += 1.0

        # Connectivity (to civ core)
        owner = getattr(t, "owner", None)
        if owner is not None and hasattr(self.world, "civs") and owner in self.world.civs:
            civ = self.world.civs[owner]
            pressure.connectivity = self._calculate_connectivity(q, r, civ)

        # Cultural & strategic
        pressure.cultural_influence = self._calculate_cultural_influence(q, r)
        pressure.strategic_value = self._calculate_strategic_value(q, r)
        return pressure

    def _calculate_connectivity(self, q: int, r: int, civ) -> float:
        tiles: List[Tuple[int, int]] = list(getattr(civ, "tiles", []))
        if not tiles:
            return 0.0

        # top-N by population
        def pop_at(pair):
            tq, tr = pair
            tt = _safe_get_tile(self.world, tq, tr)
            return int(getattr(tt, "pop", 0)) if tt is not None else 0

        top = sorted(tiles, key=pop_at, reverse=True)[:C.CONNECTIVITY_CENTER_TOP_N]
        total_pop = sum(max(1, pop_at(p)) for p in top)
        if total_pop <= 0:
            return 0.0

        wq = sum(tq * max(1, pop_at((tq, tr))) for tq, tr in top)
        wr = sum(tr * max(1, pop_at((tq, tr))) for tq, tr in top)
        cq = wq / total_pop
        cr = wr / total_pop

        dist = _distance(self.world, q, r, int(cq), int(cr))
        connectivity = max(0.0, 1.0 - dist / C.CONNECTIVITY_DIST_DENOM)

        # adjacency bonus
        adj_owned = 0
        for nq, nr in _neighbors6(self.world, q, r):
            nt = _safe_get_tile(self.world, nq, nr)
            if nt is not None and getattr(nt, "owner", None) == getattr(civ, "civ_id", None):
                adj_owned += 1
        connectivity += adj_owned * C.CONNECTIVITY_ADJACENT_BONUS

        if self._has_trade_route(q, r):
            connectivity += C.CONNECTIVITY_TRADE_BONUS

        return min(C.CONNECTIVITY_MAX, connectivity)

    def _calculate_cultural_influence(self, q: int, r: int) -> float:
        t = _safe_get_tile(self.world, q, r)
        if t is None:
            return 0.0

        own_c = 0.0
        foreign_c = 0.0
        for dr in range(max(0, r - 2), min(getattr(self.world, "height_hex", 0), r + 3)):
            for dq in range(max(0, q - 2), min(getattr(self.world, "width_hex", 0), q + 3)):
                if _distance(self.world, q, r, dq, dr) <= 2:
                    n = _safe_get_tile(self.world, dq, dr)
                    if n is None:
                        continue
                    owner = getattr(n, "owner", None)
                    if owner is None:
                        continue
                    culture_strength = float(getattr(n, "pop", 0.0)) / float(_distance(self.world, q, r, dq, dr) + 1)
                    if owner == getattr(t, "owner", None):
                        own_c += culture_strength
                    else:
                        foreign_c += culture_strength
        return (own_c - foreign_c) / 100.0

    def _calculate_strategic_value(self, q: int, r: int) -> float:
        val = 0.0
        t = _safe_get_tile(self.world, q, r)
        if t is None:
            return 0.0
        food, prod = _yields_for(t)
        val += food * 0.3 + prod * 0.5

        # coastal
        for nq, nr in _neighbors6(self.world, q, r):
            n = _safe_get_tile(self.world, nq, nr)
            if n is not None and getattr(n, "biome", None) == "ocean":
                val += 0.5
                break

        # chokepoints
        mtn = 0
        for nq, nr in _neighbors6(self.world, q, r):
            n = _safe_get_tile(self.world, nq, nr)
            if n is not None and getattr(n, "biome", None) == "mountain":
                mtn += 1
        if mtn >= 2:
            val += 1.0

        # border tension
        owner = getattr(t, "owner", None)
        if owner is not None:
            for nq, nr in _neighbors6(self.world, q, r):
                n = _safe_get_tile(self.world, nq, nr)
                if n is not None and getattr(n, "owner", None) is not None and getattr(n, "owner", None) != owner:
                    val += 0.8
                    break
        return val

    # ----- Trade routes -------------------------------------------------------

    def _has_trade_route(self, q: int, r: int) -> bool:
        coord = (q, r)
        for a, b in self.trade_routes:
            if coord == a or coord == b:
                return True
        return False

    def establish_trade_routes(self):
        if not hasattr(self.world, "civs"):
            return
        for civ_id, civ in self.world.civs.items():
            tiles = list(getattr(civ, "tiles", []))
            if len(tiles) < 5:
                continue
            pairs: List[Tuple[Tuple[int, int], Tuple[int, int], float]] = []
            for i, (q1, r1) in enumerate(tiles):
                for q2, r2 in tiles[i + 1:]:
                    dist = _distance(self.world, q1, r1, q2, r2)
                    if C.TRADE_ROUTE_MIN_DIST <= dist <= C.TRADE_ROUTE_MAX_DIST:
                        t1 = _safe_get_tile(self.world, q1, r1)
                        t2 = _safe_get_tile(self.world, q2, r2)
                        if t1 is None or t2 is None:
                            continue
                        score = (int(getattr(t1, "pop", 0)) + int(getattr(t2, "pop", 0))) / max(1, dist)
                        pairs.append(((q1, r1), (q2, r2), score))
            pairs.sort(key=lambda x: x[2], reverse=True)
            added = 0
            for (a, b, _score) in pairs:
                if added >= C.TRADE_ROUTE_MAX_PER_CIV:
                    break
                # normalize to avoid duplicates regardless of order
                route = (a, b) if a <= b else (b, a)
                if route not in self.trade_routes:
                    self.trade_routes.add(route)
                    added += 1

    # ----- Migration ----------------------------------------------------------

    def process_migration(self, dt_years: float = 0.25) -> Dict[int, List[Tuple[int, int, int, int, float]]]:
        """Returns civ_id -> list of (from_q, from_r, to_q, to_r, pop_moved)."""
        out: Dict[int, List[Tuple[int, int, int, int, float]]] = defaultdict(list)
        if not hasattr(self.world, "civs"):
            return out

        turn = int(getattr(self.world, "turn", 0))
        for civ_id, civ in self.world.civs.items():
            tiles = list(getattr(civ, "tiles", []))
            if not tiles:
                continue

            pressures: Dict[Tuple[int, int], MigrationPressure] = {}
            for (q, r) in tiles:
                pressures[(q, r)] = self.calculate_migration_pressure(q, r)

            # Top sources by push
            sources = sorted(pressures.items(), key=lambda kv: kv[1].push_factors, reverse=True)
            sources = [s for s in sources if s[1].push_factors > 0.0][:C.MIGRATION_TOP_PRESSURE_TILES]

            for (sq, sr), sp in sources:
                st = _safe_get_tile(self.world, sq, sr)
                if st is None:
                    continue
                if int(getattr(st, "pop", 0)) < C.MIGRATION_MIN_SOURCE_POP:
                    continue

                # Find best destination within civ
                best = None
                best_score = -1e18
                for (dq, dr), dp in pressures.items():
                    if (dq, dr) == (sq, sr):
                        continue
                    dist = _distance(self.world, sq, sr, dq, dr)
                    distance_factor = (1.0 / (1.0 + dist * 0.2)) if dist > 1 else 0.5
                    score = (dp.pull_factors * 2.0 + dp.connectivity * 1.5 - dp.push_factors * 1.0) * distance_factor
                    if score > best_score:
                        best_score = score
                        best = (dq, dr)

                if best is None or best_score <= 0.0:
                    continue

                # Base amount scaled by dt and global pace
                base = int(getattr(st, "pop", 0)) * C.MIGRATION_BASE_RATE * max(0.0, sp.push_factors)
                base *= dt_years * C.PACE_MULTIPLIER

                # Tech bonus
                if self.tech_system and hasattr(self.tech_system, "get_civ_bonuses") and civ_id in getattr(self.tech_system, "civ_states", {}):
                    try:
                        bonuses = self.tech_system.get_civ_bonuses(civ_id)
                        base *= (1.0 + float(getattr(bonuses, "territory_expansion_rate", 0.0)))
                    except Exception:
                        pass

                # friction if destination recently received migrants
                dq, dr = best
                friction = 1.0
                recent = self.recent_received_turns[(dq, dr)]
                if any(turn - t <= C.MIGRATION_RECENT_WINDOW for t in recent):
                    friction *= C.MIGRATION_RECENT_FRICTION

                move = int(max(0.0, base) * friction)
                move = min(move, int(getattr(st, "pop", 0)) - 10)  # keep at least 10
                if move <= 0:
                    continue

                dtile = _safe_get_tile(self.world, dq, dr)
                if dtile is None:
                    continue

                # Apply
                st.pop = max(0, int(getattr(st, "pop", 0)) - move)
                dtile.pop = max(0, int(getattr(dtile, "pop", 0)) + move)

                out[civ_id].append((sq, sr, dq, dr, float(move)))
                self.migration_history[(dq, dr)].append((turn, float(move)))
                self.recent_received_turns[(dq, dr)].append(turn)

        return out

    # ----- Colonization -------------------------------------------------------

    def strategic_colonization(self, civ_id: int, strategy: ColonizationStrategy = ColonizationStrategy.EXPANSIONIST) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        if not hasattr(self.world, "civs") or civ_id not in self.world.civs:
            return None
        civ = self.world.civs[civ_id]
        tiles = list(getattr(civ, "tiles", []))
        if not tiles:
            return None

        sources: List[Tuple[int, int, int]] = []
        for q, r in tiles:
            t = _safe_get_tile(self.world, q, r)
            if t is None:
                continue
            if int(getattr(t, "pop", 0)) >= C.COLONIZE_SOURCE_MIN_POP:
                sources.append((q, r, int(getattr(t, "pop", 0))))
        if not sources:
            return None

        potentials: List[Tuple[Tuple[int, int], Tuple[int, int], float]] = []
        for sq, sr, _pop in sources:
            for nq, nr in _neighbors6(self.world, sq, sr):
                tgt = _safe_get_tile(self.world, nq, nr)
                if tgt is None:
                    continue
                if getattr(tgt, "owner", None) is None and getattr(tgt, "biome", None) != "ocean":
                    score = self._score_colonization_target(nq, nr, civ_id, strategy)
                    potentials.append(((sq, sr), (nq, nr), score))

        if not potentials:
            return None
        potentials.sort(key=lambda x: x[2], reverse=True)
        src, dst, score = potentials[0]
        if score > 0.0:
            return src, dst
        return None

    def _score_colonization_target(self, q: int, r: int, civ_id: int, strategy: ColonizationStrategy) -> float:
        t = _safe_get_tile(self.world, q, r)
        if t is None:
            return 0.0
        food, prod = _yields_for(t)
        base = food * 1.5 + prod * 1.0

        if strategy == ColonizationStrategy.EXPANSIONIST:
            unclaimed = sum(1 for nq, nr in _neighbors6(self.world, q, r)
                            if (_safe_get_tile(self.world, nq, nr) is not None and
                                getattr(_safe_get_tile(self.world, nq, nr), "owner", None) is None))
            # Much higher bonus for unclaimed neighbors to prioritize rapid expansion
            return base + unclaimed * 2.0  # Increased from 0.5 to 2.0

        if strategy == ColonizationStrategy.DEFENSIVE:
            owned = sum(1 for nq, nr in _neighbors6(self.world, q, r)
                        if (_safe_get_tile(self.world, nq, nr) is not None and
                            getattr(_safe_get_tile(self.world, nq, nr), "owner", None) == civ_id))
            return base + owned * 0.8

        if strategy == ColonizationStrategy.RESOURCE_FOCUSED:
            return food * 3.0 + prod * 2.0

        if strategy == ColonizationStrategy.COASTAL:
            coastal = any(_safe_get_tile(self.world, nq, nr) is not None and
                          getattr(_safe_get_tile(self.world, nq, nr), "biome", None) == "ocean"
                          for nq, nr in _neighbors6(self.world, q, r))
            return base + (2.0 if coastal else -1.0)

        if strategy == ColonizationStrategy.AGGRESSIVE:
            enemy_prox = 0.0
            for nq, nr in _neighbors6(self.world, q, r):
                n = _safe_get_tile(self.world, nq, nr)
                if n is None:
                    continue
                own = getattr(n, "owner", None)
                if own is not None and own != civ_id:
                    enemy_prox += 2.0
            return base + enemy_prox

        return base

    # ----- Cultural pressure --------------------------------------------------

    def apply_cultural_pressure(self, dt_years: float = 0.25) -> List[Tuple[int, int, int, int]]:
        flips: List[Tuple[int, int, int, int]] = []
        H = getattr(self.world, "height_hex", 0)
        W = getattr(self.world, "width_hex", 0)
        turn = int(getattr(self.world, "turn", 0))

        for r in range(H):
            for q in range(W):
                t = _safe_get_tile(self.world, q, r)
                if t is None:
                    continue
                owner = getattr(t, "owner", None)
                if owner is None or getattr(t, "biome", None) == "ocean":
                    continue
                pop = int(getattr(t, "pop", 0))
                if pop >= C.POP_CORE_THRESHOLD:
                    continue  # core tiles never flip

                pressures: Dict[int, float] = defaultdict(float)
                for dr in range(max(0, r - C.CULTURAL_RADIUS), min(H, r + C.CULTURAL_RADIUS + 1)):
                    for dq in range(max(0, q - C.CULTURAL_RADIUS), min(W, q + C.CULTURAL_RADIUS + 1)):
                        dist = _distance(self.world, q, r, dq, dr)
                        if dist == 0 or dist > C.CULTURAL_RADIUS:
                            continue
                        n = _safe_get_tile(self.world, dq, dr)
                        if n is None:
                            continue
                        own = getattr(n, "owner", None)
                        if own is None:
                            continue
                        pres = float(getattr(n, "pop", 0)) / float(dist ** 2)
                        # tech bonus
                        if self.tech_system and hasattr(self.tech_system, "get_civ_bonuses") and own in getattr(self.tech_system, "civ_states", {}):
                            try:
                                bonuses = self.tech_system.get_civ_bonuses(own)
                                pres *= (1.0 + float(getattr(bonuses, "territory_expansion_rate", 0.0)) * 0.5)
                            except Exception:
                                pass
                        pressures[own] += pres

                if not pressures:
                    continue
                max_civ, max_p = max(pressures.items(), key=lambda kv: kv[1])
                own_p = pressures.get(owner, 0.0)
                if max_civ != owner and max_p > own_p * 3.0 and pop < 30:
                    # probability scaled by dt and capped
                    chance = min(C.CULTURAL_FLIP_MAX_CHANCE, max(0.0, (max_p - own_p) / 1000.0))
                    chance *= dt_years * C.PACE_MULTIPLIER
                    if self.rng.random() < chance:
                        flips.append((q, r, owner, max_civ))

        # apply flips
        for q, r, old_owner, new_owner in flips:
            t = _safe_get_tile(self.world, q, r)
            if t is None:
                continue
            t.owner = new_owner
            # civ tiles lists (safe)
            if hasattr(self.world, "civs"):
                if old_owner in self.world.civs:
                    civ_old = self.world.civs[old_owner]
                    if (q, r) in getattr(civ_old, "tiles", []):
                        civ_old.tiles.remove((q, r))
                if new_owner in self.world.civs:
                    civ_new = self.world.civs[new_owner]
                    if (q, r) not in getattr(civ_new, "tiles", []):
                        civ_new.tiles.append((q, r))

        return flips

    # ----- Serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        routes = [((a[0], a[1]), (b[0], b[1])) for (a, b) in self.trade_routes]
        # store only last K migration entries per tile
        mig = {f"{q},{r}": list(self.migration_history[(q, r)]) for (q, r) in self.migration_history.keys()}
        return {"trade_routes": routes, "migration_history": mig}

    def from_dict(self, data: dict) -> None:
        self.trade_routes.clear()
        for a, b in data.get("trade_routes", []):
            a = (int(a[0]), int(a[1]))
            b = (int(b[0]), int(b[1]))
            route = (a, b) if a <= b else (b, a)
            self.trade_routes.add(route)
        self.migration_history.clear()
        for key, entries in data.get("migration_history", {}).items():
            q, r = map(int, key.split(","))
            dq = deque(maxlen=64)
            for tup in entries:
                # accept (turn, amt) tuples or lists
                try:
                    turn, amt = int(tup[0]), float(tup[1])
                    dq.append((turn, amt))
                except Exception:
                    continue
            self.migration_history[(q, r)] = dq


# ----------- Integration helpers ---------------------------------------------

def determine_colonization_strategy(engine, civ_id: int) -> ColonizationStrategy:
    civ = engine.world.civs[civ_id]
    tiles = list(getattr(civ, "tiles", []))
    owned = len(tiles)
    border = 0
    coastal = 0
    total_unclaimed = 0
    
    # Count unclaimed neighbors and border pressure
    for q, r in tiles:
        for nq, nr in _neighbors6(engine.world, q, r):
            n = _safe_get_tile(engine.world, nq, nr)
            if n is None:
                continue
            owner = getattr(n, "owner", None)
            if owner is None:
                total_unclaimed += 1
            elif owner != civ_id:
                border += 1
                break
            if getattr(n, "biome", None) == "ocean":
                coastal += 1
    
    # Stay expansionist much longer if there's unclaimed land
    if owned < 15 or total_unclaimed > owned * 0.5:  # Expanded from 5 to 15, or if lots of unclaimed land
        return ColonizationStrategy.EXPANSIONIST
    if border > owned * 0.4:  # Increased threshold for defensive
        return ColonizationStrategy.DEFENSIVE
    if coastal > owned * 0.3:  # Increased threshold for coastal
        return ColonizationStrategy.COASTAL
    if owned > 25 and border > 8:  # Increased thresholds for aggressive
        return ColonizationStrategy.AGGRESSIVE
    return ColonizationStrategy.RESOURCE_FOCUSED


def integrate_enhanced_colonization(engine) -> None:
    """
    Wrap engine._colonization_pass with enhanced logic.
    Safe to call once in engine.__init__ when a flag is enabled.
    """
    # Attach system if missing
    if not hasattr(engine, "colonization_system") or engine.colonization_system is None:
        seed = int(getattr(engine, "seed", 0))
        rng = getattr(engine, "rng", None)
        engine.colonization_system = EnhancedColonizationSystem(engine.world, getattr(engine, "tech_system", None), rng=rng, seed=seed)

    # Ensure base colonization pass exists
    if not hasattr(engine, "_colonization_pass") or engine._colonization_pass is None:
        def _noop():
            return None
        engine._colonization_pass = _noop

    original = engine._colonization_pass

    def enhanced_colonization_pass():
        # Base system first
        original()

        sys: EnhancedColonizationSystem = engine.colonization_system
        dt_years = float(engine.delta_years()) if hasattr(engine, "delta_years") else 0.25

        # Internal migration
        migrations = sys.process_migration(dt_years)
        if getattr(engine.world, "turn", 0) % 10 == 0:
            for civ_id, mlst in migrations.items():
                for sq, sr, dq, dr, moved in mlst:
                    print(f"[Migration] Civ {civ_id}: {moved:.0f} moved {sq},{sr} -> {dq},{dr}")

        # Strategic colonization - attempt multiple colonizations per civ per turn
        if hasattr(engine.world, "civs"):
            for civ_id in list(engine.world.civs.keys()):
                strat = determine_colonization_strategy(engine, civ_id)
                
                # Try multiple colonization attempts per turn for aggressive expansion
                max_colonies_per_turn = 3 if strat == ColonizationStrategy.EXPANSIONIST else 1
                colonies_created = 0
                
                for attempt in range(max_colonies_per_turn):
                    res = sys.strategic_colonization(civ_id, strat)
                    if not res:
                        break  # No more valid colonization targets
                        
                    (sq, sr), (dq, dr) = res
                    st = _safe_get_tile(engine.world, sq, sr)
                    tt = _safe_get_tile(engine.world, dq, dr)
                    if st is None or tt is None:
                        continue
                        
                    if int(getattr(st, "pop", 0)) >= C.COLONIZE_SOURCE_MIN_POP and getattr(tt, "owner", None) is None:
                        # Calculate smart colonization - keep capitals substantial but not overpopulated
                        source_pop = int(getattr(st, "pop", 0))
                        colony_size = C.COLONIZE_COLONY_SEED
                        
                        # If source is capital, only colonize if it has excess population
                        is_capital = hasattr(civ, 'capital') and civ.capital == (sr, sq)
                        if is_capital and source_pop > 120:  # Capital has excess population
                            colony_size = min(colony_size, source_pop - 100)  # Keep at least 100 in capital
                        elif is_capital:
                            continue  # Don't drain capital below 120
                        
                        # Proceed with colonization
                        st.pop = max(0, source_pop - colony_size)
                        tt.owner = civ_id
                        tt.pop = max(0, int(getattr(tt, "pop", 0)) + colony_size)
                        civ = engine.world.civs[civ_id]
                        if (dq, dr) not in getattr(civ, "tiles", []):
                            civ.tiles.append((dq, dr))
                        colonies_created += 1
                        
                        # Print expansion info occasionally
                        if getattr(engine.world, "turn", 0) % 10 == 0:
                            print(f"[Expansion] Civ {civ_id} colonized ({dq},{dr}) from ({sq},{sr}) with {colony_size} people")
                    else:
                        break  # Source doesn't have enough population

        # Cultural pressure
        flips = sys.apply_cultural_pressure(dt_years)
        if getattr(engine.world, "turn", 0) % 10 == 0:
            for q, r, old_o, new_o in flips:
                print(f"[Cultural Flip] ({q},{r}) {old_o} -> {new_o}")

        # Trade routes (periodic)
        if getattr(engine.world, "turn", 0) % 20 == 0:
            sys.establish_trade_routes()

    engine._colonization_pass = enhanced_colonization_pass
