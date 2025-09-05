from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json
import logging
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

from worldgen.hexgrid import neighbors6
from worldgen.hexgrid import distance as hex_distance
from worldgen.biomes import Biome
from pathfinding import astar
from time_model import Calendar, WEEK, MONTH, YEAR
from resources import yields_for

logger = logging.getLogger(__name__)

Coord = Tuple[int, int]  # (q, r) - axial hex coordinates: q=column, r=row

# Population distribution and manpower availability by cohort
MALE_FRACTION = 0.5
# Fractions of the male population by age bracket
PRIME_MALE_FRACTION = 0.35   # ages 14-35
MATURE_MALE_FRACTION = 0.25  # ages 36-60
# Portions of each age bracket that can be drafted as manpower
PRIME_MANPOWER_SHARE = 0.5   # majority of draft comes from prime males
MATURE_MANPOWER_SHARE = 0.2  # mature males contribute less


def compute_manpower_limit(total_pop: int) -> int:
    """Return manpower cap derived from sex and age cohorts.

    Population is divided into four age ranges (0-13, 14-35, 36-60, 61+) and
    by sex. Only males aged 14-60 contribute to manpower, with the 14-35 cohort
    supplying the majority and the 36-60 cohort a reduced share.  To preserve
    reproduction and productivity, only a fraction of those eligible males are
    considered available for combat.
    """
    male_pop = total_pop * MALE_FRACTION
    prime = male_pop * PRIME_MALE_FRACTION * PRIME_MANPOWER_SHARE
    mature = male_pop * MATURE_MALE_FRACTION * MATURE_MANPOWER_SHARE
    return int(prime + mature)


def _convert_biome_from_save(biome_value) -> str:
    """Normalize biome value from save files to a lowercase string.

    Older saves may encode biomes as integers (from ``worldgen.biomes.Biome``
    enums) while newer versions use plain strings.  This helper accepts either
    form and always returns a canonical string to avoid ``int()`` casts on
    arbitrary data.
    """
    if isinstance(biome_value, str):
        return biome_value.lower()
    # Handle ``Biome`` enums or raw integers
    try:
        return Biome(int(biome_value)).name.lower()
    except Exception:
        if hasattr(biome_value, "name"):
            return str(biome_value.name).lower()
        return "ocean"


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
    _pop_float: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        # Ensure the internal float mirror matches the initial population
        self._pop_float = float(self.pop)

    def __setattr__(self, name, value):
        # Keep _pop_float in sync whenever ``pop`` is updated
        if name == "pop":
            try:
                object.__setattr__(self, "_pop_float", float(value))
            except Exception:
                object.__setattr__(self, "_pop_float", 0.0)
        object.__setattr__(self, name, value)

# Backwards compatibility
Tile = TileHex


@dataclass
class Civ:
    civ_id: int
    name: str
    stock_food: int = 0
    tiles: List[Coord] = field(default_factory=list)
    armies: List["Army"] = field(default_factory=list)
    manpower_used: int = 0
    manpower_limit: int = 0

    # --- Culture and naming ---
    main_culture: Optional[str] = "Unknown Culture"  # Name of the main culture
    linguistic_type: str = "latin"
    
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
    # Default movement speed tuned so that an army advances roughly
    # one hex per weekly turn. 52 hexes/year = 1 hex/week.
    speed_hexes_per_year: int = 52
    _movement_accumulator: float = field(default=0.0, init=False)


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
    colonize_period_years: float = 0.3  # More frequent expansion attempts for better growth
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
        """Get tile at hex coordinate (q, r). 
        Note: hex coords (q,r) map to array index [r,q] in NumPy arrays."""
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
                      mountain_thresh: float = 0.8,
                      use_advanced_biomes: bool = True) -> None:
        """Generate world terrain and biomes using enhanced system."""
        from worldgen import build_world
        from worldgen.biomes import Biome

        w = self.world.width_hex
        h = self.world.height_hex
        seed = self.world.seed

        height, biomes, sea, _ = build_world(
            w, h, seed,
            plate_count=12,
            hex_radius=12.0,
            sea_level_percentile=sea_percentile,
            mountain_h=mountain_thresh,
            use_advanced_biomes=use_advanced_biomes,
        )

        self.world.sea_level = sea
        for t in self.world.tiles:
            biome_id = biomes[t.r, t.q]
            t.biome = Biome(biome_id).name.lower()
            t.height = float(height[t.r, t.q])

    def seed_population_everywhere(self, min_pop=3, max_pop=30) -> None:
        for t in self.world.tiles:
            t.pop = self.rng.randint(min_pop, max_pop)
            t.owner = None

    def add_civ(self, name: str, at: Coord, main_culture: str = None, linguistic_type: str = None) -> int:
        """Add a civilization with explicit name and culture."""
        q, r = at
        if not self.world.in_bounds(q, r):
            raise ValueError("Civ spawn out of bounds")
        cid = self._next_civ_id()
        
        # Use provided culture info or defaults
        final_main_culture = main_culture if main_culture else "Unknown Culture"
        final_linguistic_type = linguistic_type if linguistic_type else "latin"
        
        civ = Civ(
            civ_id=cid, 
            name=name, 
            stock_food=75,
            tiles=[],
            main_culture=final_main_culture,
            linguistic_type=final_linguistic_type
        )
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

    def spawn_civ(self, at: Coord, name_generator=None) -> int:
        """Spawn a new civilization with generated name and culture."""
        # Import name generator if not provided
        if name_generator is None:
            try:
                import sys
                import os
                sys.path.append(os.path.dirname(__file__))
                from name_generator import NameGenerator
                name_generator = NameGenerator(self.world.seed + len(self.world.civs))
            except ImportError:
                # Fallback to manual naming if name generator not available
                return self.add_civ(f"Civilization {len(self.world.civs) + 1}", at)
        
        # Generate linguistic type and culture name
        civ_id_for_seed = len(self.world.civs)  
        linguistic_type = name_generator.assign_linguistic_type_to_culture(civ_id_for_seed, self.world.seed)
        culture_name = name_generator.generate_culture_name(style=linguistic_type)
        country_name = name_generator.generate_country_name(style=linguistic_type)
        
        return self.add_civ(
            name=country_name,
            at=at,
            main_culture=culture_name,
            linguistic_type=linguistic_type
        )

    def add_army(self, civ_id: int, at: Coord, strength: int = 10,
                 supply: int = 100) -> Army:
        q, r = at
        if civ_id not in self.world.civs:
            raise ValueError("Unknown civ")
        
        civ = self.world.civs[civ_id]
        ARMY_FOOD_COST = strength * 2  # Food cost scales with army strength
        
        if civ.stock_food < ARMY_FOOD_COST:
            raise ValueError(f"Not enough food to create army (need {ARMY_FOOD_COST}, have {civ.stock_food})")

        civ.stock_food -= ARMY_FOOD_COST
        army = Army(civ_id=civ_id, q=q, r=r, strength=strength, supply=supply)
        self.world.armies.append(army)
        self.world.civs[civ_id].armies.append(army)
        civ.manpower_used += strength
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
                    logger.info(
                        "[Turn %s] %s has discovered %s!", w.turn, civ.name, tech.name
                    )

        # --- Economy & demographic growth with tech bonuses --------------------
        BASE_K = 100.0
        R = 0.5  # intrinsic growth rate per year
        POP_MAX = 1_000_000_000

        gains = {cid: 0.0 for cid in w.civs}
        manpower_penalties: Dict[int, float] = {}
        for cid, civ in w.civs.items():
            total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
            limit = compute_manpower_limit(total_pop)
            civ.manpower_limit = limit
            used = civ.manpower_used
            if limit > 0 and used > limit:
                over_ratio = (used - limit) / limit
                manpower_penalties[cid] = min(1.0, over_ratio)
            else:
                manpower_penalties[cid] = 0.0

        for t in w.tiles:
            base_food, base_prod = yields_for(t)

            if t.owner is not None and t.owner in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(t.owner)
                food_yield, _prod_yield = apply_tech_bonuses_to_tile(
                    t, bonuses, base_food, base_prod
                )
            else:
                food_yield = base_food

            penalty = manpower_penalties.get(t.owner, 0.0) if t.owner is not None else 0.0
            if t.owner is not None:
                food_yield *= (1 - penalty)
                gains[t.owner] += food_yield * dt

            growth_bonus = 0.0
            if t.owner is not None and t.owner in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(t.owner)
                growth_bonus = bonuses.population_growth_rate

            K = BASE_K * food_yield
            K_eff = max(K, 1.0)
            actual_r = (R + growth_bonus) * (1 - penalty)

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
            # Bypass __setattr__ to preserve fractional _pop_float across steps
            object.__setattr__(t, "pop", int(pop_int))

        for cid, g in gains.items():
            civ = w.civs[cid]
            # Increase food cap scaling with territory size to support larger civilizations
            max_food = max(1000, len(w.civs[cid].tiles) * 200)
            civ.stock_food = max(0, min(civ.stock_food + int(g), max_food))

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
        POP_THRESHOLD_BASE = 30  # Reduced threshold to allow expansion when population is stable
        SETTLER_COST = 10
        FOOD_COST_FOR_EXPANSION = 20  # Balanced food cost for sustainable expansion
        actions: List[Tuple[int, Coord, Coord]] = []
        claimed: set[Coord] = set()

        for cid in sorted(w.civs.keys()):
            civ = w.civs[cid]

            # Check if civ has enough food for expansion
            if civ.stock_food < FOOD_COST_FOR_EXPANSION:
                continue

            # Expansion bonus reduces threshold (more likely to expand)
            expansion_bonus = 0.0
            if cid in self.tech_system.civ_states:
                bonuses = self.tech_system.get_civ_bonuses(cid)
                expansion_bonus = bonuses.territory_expansion_rate
            pop_threshold = POP_THRESHOLD_BASE * (1 - 0.3 * expansion_bonus)
            
            # Limit expansions per turn based on civ size to prevent runaway growth
            current_tiles = len(civ.tiles)
            max_expansions_this_turn = max(1, min(3, current_tiles // 10))  # 1-3 expansions max, scaling with size
            expansions_this_turn = 0

            for (q, r) in sorted(civ.tiles):
                # Stop if this civ has reached its expansion limit for this turn
                if expansions_this_turn >= max_expansions_this_turn:
                    break
                    
                t = w.get_tile(q, r)
                if t.pop < pop_threshold:
                    continue
                neighbors = list(w.neighbors6(q, r))
                self.rng.shuffle(neighbors)  # Randomize expansion direction for more natural patterns
                for nq, nr in neighbors:
                    if (nq, nr) in claimed:
                        continue
                    tt = w.get_tile(nq, nr)
                    if tt.owner is None:
                        actions.append((cid, (q, r), (nq, nr)))
                        claimed.add((nq, nr))
                        expansions_this_turn += 1
                        break  # Only expand to one neighbor per tile per pass

        for cid, (sq, sr), (dq, dr) in actions:
            src = w.get_tile(sq, sr)
            dst = w.get_tile(dq, dr)
            civ = w.civs[cid]
            
            # Consume food for expansion
            civ.stock_food = max(0, civ.stock_food - FOOD_COST_FOR_EXPANSION)
            
            src.pop = max(0, src.pop - SETTLER_COST)
            src._pop_float = float(src.pop)
            dst.owner = cid
            dst.pop = SETTLER_COST
            dst._pop_float = float(dst.pop)
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
                
                # Accumulate movement points to handle fractional movement properly
                army._movement_accumulator += base_speed * dt
                steps = int(army._movement_accumulator)  # Take integer part
                army._movement_accumulator -= steps     # Keep fractional remainder
                
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
            biome = tile.biome
            if isinstance(biome, Biome):
                is_mountain = biome == Biome.MOUNTAIN
            else:
                is_mountain = str(biome).lower() == "mountain"
            if is_mountain or min_dist > 5:
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
                
                armies_to_remove = []

                if s1 > s2:
                    damage = math.ceil(a2.strength * 0.5)
                    a1.strength = max(1, a1.strength - damage)  # winner takes some damage
                    armies_to_remove.append(a2)
                elif s2 > s1:
                    damage = math.ceil(a1.strength * 0.5)
                    a2.strength = max(1, a2.strength - damage)
                    armies_to_remove.append(a1)
                else:
                    # Mutual attrition
                    a1.strength -= 1
                    a2.strength -= 1
                    if a1.strength <= 0:
                        armies_to_remove.append(a1)
                    if a2.strength <= 0:
                        armies_to_remove.append(a2)
                
                # Remove defeated armies from all lists
                for army_to_remove in armies_to_remove:
                    if army_to_remove in armies:
                        armies.remove(army_to_remove)
                    if army_to_remove in w.armies:
                        w.armies.remove(army_to_remove)
                    if army_to_remove in self.world.civs[army_to_remove.civ_id].armies:
                        self.world.civs[army_to_remove.civ_id].armies.remove(army_to_remove)

                civs = {a.civ_id for a in armies}
        for cid, civ in self.world.civs.items():
            civ.manpower_used = sum(a.strength for a in civ.armies)
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
            "tiles": [
                {
                    "q": t.q,
                    "r": t.r,
                    "height": t.height,
                    "biome": _convert_biome_from_save(t.biome),
                    "pop": t.pop,
                    "owner": t.owner,
                    "feature": t.feature,
                }
                for t in w.tiles
            ],
            "civs": {
                str(cid): {
                    "civ_id": c.civ_id,
                    "name": c.name,
                    "stock_food": c.stock_food,
                    "tiles": c.tiles,
                    # culture information
                    "main_culture": c.main_culture,
                    "linguistic_type": c.linguistic_type,
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
        from sim.safe_parse import to_int, to_float
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
            tiles = []
            for td in data["tiles"]:
                owner_val = td.get("owner")
                tiles.append(
                    TileHex(
                        q=td["q"],
                        r=td["r"],
                        height=to_float(td.get("height", 0.0)),
                        biome=_convert_biome_from_save(td.get("biome", "ocean")),
                        pop=to_int(td.get("pop", 0)),
                        owner=to_int(owner_val, default=0) if owner_val is not None else None,
                        feature=td.get("feature"),
                    )
                )
        else:
            w = World(width_hex=data["width"], height_hex=data["height"],
                      hex_size=data.get("hex_size", 1), sea_level=data.get("sea_level", 0.0),
                      tiles=[], civs={}, turn=turn, seed=data["seed"],
                      time_scale=time_scale, calendar=Calendar(**cal_data),
                      colonize_period_years=data.get("colonize_period_years", 0.25),
                      colonize_elapsed=data.get("colonize_elapsed", 0.0))
            tiles = []
            for td in data["tiles"]:
                owner_val = td.get("owner")
                tiles.append(
                    TileHex(
                        q=td.get("q", td["x"]),
                        r=td.get("r", td["y"]),
                        height=to_float(td.get("height", 0.0)),
                        biome=_convert_biome_from_save(td.get("biome", "ocean")),
                        pop=to_int(td.get("pop", 0)),
                        owner=to_int(owner_val, default=0) if owner_val is not None else None,
                        feature=td.get("feature"),
                    )
                )
        w.tiles = tiles

        # Civs with tech mirrors (true tech state loaded from blob below)
        civs: Dict[int, Civ] = {}
        for _, cd in data["civs"].items():
            civ = Civ(
                civ_id=cd["civ_id"],
                name=cd["name"],
                stock_food=cd["stock_food"],
                tiles=[tuple(t) for t in cd["tiles"]],
                # culture information with backwards compatibility
                main_culture=cd.get("main_culture", cd.get("culture_name", "Unknown Culture")),
                linguistic_type=cd.get("linguistic_type", "latin"),
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
