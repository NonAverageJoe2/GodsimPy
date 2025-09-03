from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json
import random
import math

# --- Tech system integration ---------------------------------------------------
# If you want to allow running without technology.py present, wrap this in try/except
# and set a no-op TechnologySystem. For now we require technology.py to exist.
from technology import (
    TechnologySystem, TechBonus, Age, TechTree, CivTechState,
    calculate_civ_science_output, detect_resources_in_territory,
    apply_tech_bonuses_to_tile
)

from worldgen import apply_worldgen
from worldgen.hexgrid import neighbors6
from worldgen.hexgrid import distance as hex_distance
from pathfinding import astar
from time_model import Calendar, WEEK, MONTH, YEAR
from resources import yields_for

Coord = Tuple[int, int]


# =============================== DATA TYPES ===================================

@dataclass
class TileHex:
    q: int
    r: int
    height: float = 0.0
    biome: str = "ocean"
    pop: int = 0
    owner: Optional[int] = None  # civ_id or None
    feature: Optional[str] = None

# Backwards compatibility
Tile = TileHex


@dataclass
class Civ:
    civ_id: int
    name: str
    stock_food: int = 0
    tiles: List[Coord] = field(default_factory=list)
    armies: List["Army"] = field(default_factory=list)

    # --- Technology display/state mirrors (kept here for quick summary/save) ---
    current_age: str = "Age of Dissemination"
    tech_count: int = 0
    current_research: Optional[str] = None
    research_progress: float = 0.0  # 0-100 like progress text; internal points live in tech_system


@dataclass
class Army:
    civ_id: int
    q: int
    r: int
    strength: int = 10
    target: Optional[Coord] = None
    path: List[Coord] = field(default_factory=list)
    supply: int = 100
    speed_hexes_per_year: int = 12


@dataclass
class World:
    width_hex: int
    height_hex: int
    hex_size: int
    sea_level: float
    tiles: List[TileHex]
    civs: Dict[int, Civ]
    armies: List[Army] = field(default_factory=list)
    turn: int = 0
    seed: int = 42
    time_scale: str = "week"
    calendar: Calendar = field(default_factory=Calendar)
    colonize_period_years: float = 0.25
    colonize_elapsed: float = 0.0

    @property
    def width(self) -> int:  # compat
        return self.width_hex

    @property
    def height(self) -> int:  # compat
        return self.height_hex

    def idx(self, q: int, r: int) -> int:
        if q < 0 or r < 0 or q >= self.width_hex or r >= self.height_hex:
            raise IndexError("tile OOB")
        return r * self.width_hex + q

    def get_tile(self, q: int, r: int) -> TileHex:
        return self.tiles[self.idx(q, r)]

    def in_bounds(self, q: int, r: int) -> bool:
        return 0 <= q < self.width_hex and 0 <= r < self.height_hex

    def neighbors6(self, q: int, r: int) -> List[Coord]:
        out: List[Coord] = []
        for nq, nr in neighbors6(q, r):
            if self.in_bounds(nq, nr):
                out.append((nq, nr))
        return out


# =============================== ENGINE =======================================

class SimulationEngine:
    """Pure-sim API usable by CLI, GUI, and tests, now with TechnologySystem integration."""

    def __init__(self, width: int = 48, height: int = 32, seed: int = 12345,
                 hex_size: int = 1, sea_level: float = 0.0):
        self.rng = random.Random(seed)
        self.world = self._new_world(width, height, seed, hex_size, sea_level)
        # Populate the world's terrain deterministically from the seed
        self.init_worldgen()

        # --- Technology System ---
        self.tech_system = TechnologySystem()

    def _new_world(self, w: int, h: int, seed: int, hex_size: int, sea_level: float) -> World:
        tiles = [TileHex(q=i % w, r=i // w) for i in range(w * h)]
        return World(width_hex=w, height_hex=h, hex_size=hex_size,
                     sea_level=sea_level, tiles=tiles, civs={},
                     turn=0, seed=seed)

    def init_worldgen(self, sea_percentile: float = 0.35,
                      mountain_thresh: float = 0.8) -> None:
        """(Re)generate world terrain and biomes using deterministic worldgen."""
        apply_worldgen(self, sea_percentile=sea_percentile,
                       mountain_thresh=mountain_thresh)

    def seed_population_everywhere(self, min_pop=3, max_pop=30) -> None:
        for t in self.world.tiles:
            t.pop = self.rng.randint(min_pop, max_pop)
            t.owner = None

    def add_civ(self, name: str, at: Coord) -> int:
        q, r = at
        if not self.world.in_bounds(q, r):
            raise ValueError("Civ spawn out of bounds")
        cid = self._next_civ_id()
        civ = Civ(civ_id=cid, name=name, stock_food=50, tiles=[])
        self.world.civs[cid] = civ

        t = self.world.get_tile(q, r)
        # allow coexistence; must colonize later if occupied
        if t.owner is not None and t.owner != cid:
            pass
        t.owner = cid
        civ.tiles.append((q, r))

        # --- Initialize technology state for this civ from territory resources ---
        initial_resources = detect_resources_in_territory(civ, self.world)
        self.tech_system.initialize_civ(cid, initial_resources)

        # Mirror display fields on Civ (handy for save/summary)
        state = self.tech_system.civ_states.get(cid, None)
        if state:
            civ.current_age = state.current_age.value
            civ.tech_count = len(state.researched_techs)
            civ.current_research = state.current_research
            civ.research_progress = state.research_progress

        return cid

    def add_army(self, civ_id: int, at: Coord, strength: int = 10,
                 supply: int = 100) -> Army:
        q, r = at
        if civ_id not in self.world.civs:
            raise ValueError("Unknown civ")
        army = Army(civ_id=civ_id, q=q, r=r, strength=strength, supply=supply)
        self.world.armies.append(army)
        self.world.civs[civ_id].armies.append(army)
        return army

    def set_army_target(self, army: Army, target: Coord) -> None:
        army.target = target
        army.path = astar(self.world, (army.q, army.r), target)

    def _next_civ_id(self) -> int:
        i = 0
        while i in self.world.civs:
            i += 1
        return i

    def delta_years(self) -> float:
        scale = self.world.time_scale
        if scale == "week":
            return WEEK
        if scale == "month":
            return MONTH
        return YEAR

    # ------------------------ Core Turn (tech-aware) ---------------------------

    def advance_turn(self, dt: float | None = None) -> None:
        """Advance one turn with technology processing integrated."""
        w = self.world
        if dt is None:
            dt = self.delta_years()

        # --- Technology: update resources & run research for each civ -----------
        for cid, civ in w.civs.items():
            resources = detect_resources_in_territory(civ, w)
            self.tech_system.update_civ_resources(cid, resources)

            science_output = calculate_civ_science_output(civ, w)
            completed = self.tech_system.process_research(cid, science_output * dt)

            # Update display mirrors on Civ
            state = self.tech_system.civ_states.get(cid, None)
            if state:
                civ.current_age = state.current_age.value
                civ.tech_count = len(state.researched_techs)
                civ.current_research = state.current_research
                civ.research_progress = state.research_progress

            for tech_id in completed:
                tech = self.tech_system.tech_tree.technologies.get(tech_id)
                if tech:
                    print(f"[Turn {w.turn}] {civ.name} has discovered {tech.name}!")

        # --- Economy & demographic growth with tech bonuses --------------------
        BASE_K = 100.0
        R = 0.5  # intrinsic growth rate per year
        POP_MAX = 1_000_000_000

        gains = {cid: 0.0 for cid in w.civs}

        for t in w.tiles:
            base_food, base_prod = yields_for(t)

            # If owned, apply tile yield bonuses from tech
            if t.owner is not None and t.owner in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(t.owner)
                food_yield, _prod_yield = apply_tech_bonuses_to_tile(
                    t, bonuses, base_food, base_prod
                )
                gains[t.owner] += food_yield * dt
            else:
                food_yield = base_food

            if not hasattr(t, "_pop_float"):
                t._pop_float = float(t.pop)

            # Growth bonus (e.g., improved medicine/agriculture)
            growth_bonus = 0.0
            if t.owner is not None and t.owner in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(t.owner)
                growth_bonus = bonuses.population_growth_rate

            K = BASE_K * food_yield
            K_eff = max(K, 1.0)
            actual_r = R + growth_bonus

            if t._pop_float > 0:
                ratio = (K_eff - t._pop_float) / t._pop_float
                t._pop_float = K_eff / (1.0 + ratio * math.exp(-actual_r * dt))
            else:
                t._pop_float = 0.0

            pop_int = math.floor(t._pop_float)
            if pop_int < 0:
                pop_int = 0
            if pop_int > POP_MAX:
                pop_int = POP_MAX
            t.pop = int(pop_int)

        for cid, g in gains.items():
            civ = w.civs[cid]
            civ.stock_food = max(0, min(civ.stock_food + int(g), POP_MAX))

        # --- Periodic colonization with tech expansion modifier ----------------
        w.colonize_elapsed += dt
        if w.colonize_elapsed >= w.colonize_period_years:
            self._colonization_pass_with_tech()
            w.colonize_elapsed %= w.colonize_period_years

        # --- Army movement/combat with tech modifiers --------------------------
        self._advance_armies_with_tech(dt)

        w.turn += 1
        w.calendar.advance_fraction(dt)

    def _colonization_pass_with_tech(self) -> None:
        w = self.world
        POP_THRESHOLD_BASE = 50
        SETTLER_COST = 10
        actions: List[Tuple[int, Coord, Coord]] = []
        claimed: set[Coord] = set()

        for cid in sorted(w.civs.keys()):
            civ = w.civs[cid]

            # Expansion bonus reduces threshold (more likely to expand)
            expansion_bonus = 0.0
            if cid in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(cid)
                expansion_bonus = bonuses.territory_expansion_rate
            pop_threshold = POP_THRESHOLD_BASE * (1 - 0.3 * expansion_bonus)

            for (q, r) in sorted(civ.tiles):
                t = w.get_tile(q, r)
                if t.pop < pop_threshold:
                    continue
                neighbors = sorted(w.neighbors6(q, r))
                for nq, nr in neighbors:
                    if (nq, nr) in claimed:
                        continue
                    tt = w.get_tile(nq, nr)
                    if tt.owner is None:
                        actions.append((cid, (q, r), (nq, nr)))
                        claimed.add((nq, nr))
                        break

        for cid, (sq, sr), (dq, dr) in actions:
            src = w.get_tile(sq, sr)
            dst = w.get_tile(dq, dr)
            src.pop = max(0, src.pop - SETTLER_COST)
            if hasattr(src, "_pop_float"):
                src._pop_float = float(src.pop)
            dst.owner = cid
            dst.pop = SETTLER_COST
            dst._pop_float = float(dst.pop)
            civ = w.civs[cid]
            civ.tiles.append((dq, dr))

    def _advance_armies_with_tech(self, dt: float) -> None:
        w = self.world
        armies_copy = list(w.armies)
        for army in armies_copy:
            # Movement speed bonus
            movement_bonus = 0.0
            if army.civ_id in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(army.civ_id)
                movement_bonus = bonuses.movement_speed

            if army.target and (army.q, army.r) != army.target:
                if (not army.path) or (army.path and army.path[-1] != army.target):
                    army.path = astar(w, (army.q, army.r), army.target)
                base_speed = army.speed_hexes_per_year * (1 + movement_bonus)
                steps = max(0, math.ceil(base_speed * dt))
                for _ in range(steps):
                    if not army.path:
                        break
                    nq, nr = army.path.pop(0)
                    army.q, army.r = nq, nr

            # Supply & attrition
            tile = w.get_tile(army.q, army.r)
            civ_tiles = self.world.civs[army.civ_id].tiles
            if civ_tiles:
                min_dist = min(hex_distance(army.q, army.r, tq, tr) for tq, tr in civ_tiles)
            else:
                min_dist = float("inf")
            if tile.biome == "mountain" or min_dist > 5:
                army.supply = max(0, army.supply - 1)
                if army.supply <= 0:
                    army.strength = max(0, army.strength - 1)
            if army.strength <= 0:
                if army in w.armies:
                    w.armies.remove(army)
                if army in self.world.civs[army.civ_id].armies:
                    self.world.civs[army.civ_id].armies.remove(army)

        # Combat at shared tiles
        loc_map: Dict[Coord, List[Army]] = {}
        for army in w.armies:
            loc_map.setdefault((army.q, army.r), []).append(army)

        for armies in loc_map.values():
            civs = {a.civ_id for a in armies}
            while len(civs) > 1 and len(armies) > 1:
                # Apply temporary effective strength with military tech bonus
                eff_strengths: Dict[int, int] = {}
                for a in armies:
                    bonus = 0
                    if a.civ_id in self.tech_system.civ_states:
                        bonus = self.tech_system.get_civ_bonuses(a.civ_id).military_strength
                    eff_strengths[id(a)] = a.strength + max(0, int(bonus))

                armies.sort(key=lambda a: eff_strengths[id(a)], reverse=True)
                a1 = armies[0]
                a2 = next((a for a in armies[1:] if a.civ_id != a1.civ_id), None)
                if a2 is None:
                    break

                s1 = eff_strengths[id(a1)]
                s2 = eff_strengths[id(a2)]

                if s1 > s2:
                    damage = math.ceil(a2.strength * 0.5)
                    a1.strength = max(1, a1.strength - damage)  # winner takes some damage
                    armies.remove(a2)
                    if a2 in w.armies:
                        w.armies.remove(a2)
                    if a2 in self.world.civs[a2.civ_id].armies:
                        self.world.civs[a2.civ_id].armies.remove(a2)
                elif s2 > s1:
                    damage = math.ceil(a1.strength * 0.5)
                    a2.strength = max(1, a2.strength - damage)
                    armies.remove(a1)
                    if a1 in w.armies:
                        w.armies.remove(a1)
                    if a1 in self.world.civs[a1.civ_id].armies:
                        self.world.civs[a1.civ_id].armies.remove(a1)
                else:
                    # Mutual attrition
                    a1.strength -= 1
                    a2.strength -= 1
                    if a1.strength <= 0:
                        armies.remove(a1)
                        if a1 in w.armies:
                            w.armies.remove(a1)
                        if a1 in self.world.civs[a1.civ_id].armies:
                            self.world.civs[a1.civ_id].armies.remove(a1)
                    if a2.strength <= 0:
                        armies.remove(a2)
                        if a2 in w.armies:
                            w.armies.remove(a2)
                        if a2 in self.world.civs[a2.civ_id].armies:
                            self.world.civs[a2.civ_id].armies.remove(a2)

                civs = {a.civ_id for a in armies}

    # ----------------------------- Summary/Save/Load ---------------------------

    def summary(self) -> Dict:
        w = self.world
        pop_total = sum(t.pop for t in w.tiles)
        owned = sum(1 for t in w.tiles if t.owner is not None)
        out_civs: Dict[int, Dict] = {}
        for cid, c in w.civs.items():
            tech_info = {}
            state = self.tech_system.civ_states.get(cid, None)
            if state:
                tech_info = {
                    "age": state.current_age.value,
                    "techs_researched": len(state.researched_techs),
                    "current_research": state.current_research,
                    "research_progress": f"{state.research_progress:.1f}" if state.current_research else "N/A",
                    "total_research_points": f"{state.research_points_accumulated:.1f}"
                }
            out_civs[cid] = {
                "name": c.name,
                "tiles": len(c.tiles),
                "food": c.stock_food,
                "technology": tech_info
            }

        return {
            "turn": w.turn,
            "width": w.width_hex, "height": w.height_hex,
            "total_pop": pop_total,
            "owned_tiles": owned,
            "civs": out_civs
        }

    def save_json(self, path: str) -> None:
        """Save world INCLUDING technology system state."""
        w = self.world
        data = {
            "width_hex": w.width_hex,
            "height_hex": w.height_hex,
            "width": w.width_hex,
            "height": w.height_hex,
            "hex_size": w.hex_size,
            "sea_level": w.sea_level,
            "turn": w.turn, "seed": w.seed,
            "time_scale": w.time_scale,
            "calendar": {"year": w.calendar.year, "month": w.calendar.month, "day": w.calendar.day},
            "colonize_period_years": w.colonize_period_years,
            "colonize_elapsed": w.colonize_elapsed,
            "tiles": [{"q": t.q, "r": t.r, "height": t.height, "biome": t.biome,
                       "pop": t.pop, "owner": t.owner, "feature": t.feature}
                      for t in w.tiles],
            "civs": {
                str(cid): {
                    "civ_id": c.civ_id,
                    "name": c.name,
                    "stock_food": c.stock_food,
                    "tiles": c.tiles,
                    # tech mirrors useful for quick UI (true state in technology blob)
                    "current_age": c.current_age,
                    "tech_count": c.tech_count,
                    "current_research": c.current_research,
                    "research_progress": c.research_progress,
                }
                for cid, c in w.civs.items()
            },
            "armies": [{"civ_id": a.civ_id, "q": a.q, "r": a.r, "strength": a.strength,
                         "target": a.target, "supply": a.supply}
                        for a in w.armies],
            # --- Technology system serialized blob ---
            "technology": self.tech_system.save_state()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_json(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        turn = data.get("turn", data.get("week", 0))
        cal_data = data.get("calendar", {"year": 0, "month": 1, "day": 1})
        time_scale = data.get("time_scale", "week")
        if "width_hex" in data:
            w = World(width_hex=data["width_hex"], height_hex=data["height_hex"],
                      hex_size=data.get("hex_size", 1), sea_level=data.get("sea_level", 0.0),
                      tiles=[], civs={}, turn=turn, seed=data["seed"],
                      time_scale=time_scale, calendar=Calendar(**cal_data),
                      colonize_period_years=data.get("colonize_period_years", 0.25),
                      colonize_elapsed=data.get("colonize_elapsed", 0.0))
            tiles = [TileHex(q=td["q"], r=td["r"], height=td.get("height", 0.0),
                             biome=td.get("biome", "ocean"), pop=td.get("pop", 0),
                             owner=td.get("owner"), feature=td.get("feature"))
                     for td in data["tiles"]]
        else:
            w = World(width_hex=data["width"], height_hex=data["height"],
                      hex_size=data.get("hex_size", 1), sea_level=data.get("sea_level", 0.0),
                      tiles=[], civs={}, turn=turn, seed=data["seed"],
                      time_scale=time_scale, calendar=Calendar(**cal_data),
                      colonize_period_years=data.get("colonize_period_years", 0.25),
                      colonize_elapsed=data.get("colonize_elapsed", 0.0))
            tiles = [TileHex(q=td.get("q", td["x"]), r=td.get("r", td["y"]),
                             height=td.get("height", 0.0), biome=td.get("biome", "ocean"),
                             pop=td.get("pop", 0), owner=td.get("owner"),
                             feature=td.get("feature"))
                     for td in data["tiles"]]
        w.tiles = tiles

        # Civs with tech mirrors (true tech state loaded from blob below)
        civs: Dict[int, Civ] = {}
        for _, cd in data["civs"].items():
            civ = Civ(
                civ_id=cd["civ_id"],
                name=cd["name"],
                stock_food=cd["stock_food"],
                tiles=[tuple(t) for t in cd["tiles"]],
                current_age=cd.get("current_age", "Age of Dissemination"),
                tech_count=cd.get("tech_count", 0),
                current_research=cd.get("current_research"),
                research_progress=cd.get("research_progress", 0.0)
            )
            civs[civ.civ_id] = civ
        w.civs = civs

        armies: List[Army] = []
        for ad in data.get("armies", []):
            a = Army(civ_id=ad["civ_id"], q=ad["q"], r=ad["r"],
                     strength=ad.get("strength", 10),
                     target=tuple(ad["target"]) if ad.get("target") else None,
                     supply=ad.get("supply", 100))
            armies.append(a)
            if a.civ_id in w.civs:
                w.civs[a.civ_id].armies.append(a)
        w.armies = armies

        self.world = w
        self.rng = random.Random(w.seed)

        # --- Restore Technology System state (authoritative) ---
        if "technology" in data:
            self.tech_system.load_state(data["technology"])

        # After loading tech state, refresh civ mirrors for consistency
        for cid, civ in self.world.civs.items():
            state = self.tech_system.civ_states.get(cid, None)
            if state:
                civ.current_age = state.current_age.value
                civ.tech_count = len(state.researched_techs)
                civ.current_research = state.current_research
                civ.research_progress = state.research_progress