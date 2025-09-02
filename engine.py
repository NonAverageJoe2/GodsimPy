from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json
import random

from worldgen import apply_worldgen
from hexgrid import neighbors6
from time_model import Calendar, WEEK, MONTH, YEAR

Coord = Tuple[int, int]


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


@dataclass
class World:
    width_hex: int
    height_hex: int
    hex_size: int
    sea_level: float
    tiles: List[TileHex]
    civs: Dict[int, Civ]
    turn: int = 0
    seed: int = 42
    time_scale: str = "week"
    calendar: Calendar = field(default_factory=Calendar)

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


class SimulationEngine:
    """Pure-sim API usable by CLI, GUI, and tests."""

    def __init__(self, width: int = 48, height: int = 32, seed: int = 12345,
                 hex_size: int = 1, sea_level: float = 0.0):
        self.rng = random.Random(seed)
        self.world = self._new_world(width, height, seed, hex_size, sea_level)
        # Populate the world's terrain deterministically from the seed
        self.init_worldgen()

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
        if t.owner is not None and t.owner != cid:
            pass  # allow coexist; must colonize later
        t.owner = cid
        civ.tiles.append((q, r))
        return cid

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

    def advance_turn(self) -> None:
        w = self.world
        dt = self.delta_years()
        # Production
        for civ in w.civs.values():
            gain = 0
            for (q, r) in civ.tiles:
                t = w.get_tile(q, r)
                gain += max(0, t.pop // 2)
            civ.stock_food += gain

        # Natural growth
        for t in w.tiles:
            if t.pop > 0:
                t.pop += self.rng.choice([0, 0, 1])
                if t.pop > 9999:
                    t.pop = 9999

        # Colonization: spend 10 food to claim adjacent unowned tiles, prefer higher pop
        for civ in w.civs.values():
            tried = 0
            frontier: List[Coord] = []
            for (q, r) in civ.tiles:
                for nq, nr in w.neighbors6(q, r):
                    tt = w.get_tile(nq, nr)
                    if tt.owner is None:
                        frontier.append((nq, nr))
            frontier.sort(key=lambda c: w.get_tile(*c).pop, reverse=True)
            for (fq, fr) in frontier:
                if civ.stock_food < 10:
                    break
                tt = w.get_tile(fq, fr)
                if tt.owner is None:
                    tt.owner = civ.civ_id
                    civ.tiles.append((fq, fr))
                    civ.stock_food -= 10
                    tried += 1
                if tried >= 3:
                    break

        w.turn += 1
        w.calendar.advance_fraction(dt)

    def summary(self) -> Dict:
        w = self.world
        pop_total = sum(t.pop for t in w.tiles)
        owned = sum(1 for t in w.tiles if t.owner is not None)
        return {
            "turn": w.turn,
            "width": w.width_hex, "height": w.height_hex,
            "total_pop": pop_total,
            "owned_tiles": owned,
            "civs": {
                cid: {"name": c.name, "tiles": len(c.tiles), "food": c.stock_food}
                for cid, c in w.civs.items()
            }
        }

    def save_json(self, path: str) -> None:
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
            "tiles": [{"q": t.q, "r": t.r, "height": t.height, "biome": t.biome,
                       "pop": t.pop, "owner": t.owner, "feature": t.feature}
                      for t in w.tiles],
            "civs": {str(cid): {"civ_id": c.civ_id, "name": c.name, "stock_food": c.stock_food,
                                 "tiles": c.tiles}
                     for cid, c in w.civs.items()}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

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
                      time_scale=time_scale, calendar=Calendar(**cal_data))
            tiles = [TileHex(q=td["q"], r=td["r"], height=td.get("height", 0.0),
                             biome=td.get("biome", "ocean"), pop=td.get("pop", 0),
                             owner=td.get("owner"), feature=td.get("feature"))
                     for td in data["tiles"]]
        else:
            w = World(width_hex=data["width"], height_hex=data["height"],
                      hex_size=data.get("hex_size", 1), sea_level=data.get("sea_level", 0.0),
                      tiles=[], civs={}, turn=turn, seed=data["seed"],
                      time_scale=time_scale, calendar=Calendar(**cal_data))
            tiles = [TileHex(q=td.get("q", td["x"]), r=td.get("r", td["y"]),
                             height=td.get("height", 0.0), biome=td.get("biome", "ocean"),
                             pop=td.get("pop", 0), owner=td.get("owner"),
                             feature=td.get("feature"))
                     for td in data["tiles"]]
        w.tiles = tiles
        civs: Dict[int, Civ] = {}
        for _, cd in data["civs"].items():
            civ = Civ(civ_id=cd["civ_id"], name=cd["name"], stock_food=cd["stock_food"],
                      tiles=[tuple(t) for t in cd["tiles"]])
            civs[civ.civ_id] = civ
        w.civs = civs
        self.world = w
        self.rng = random.Random(w.seed)
