from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json
import random

Coord = Tuple[int, int]

@dataclass
class Tile:
    x: int
    y: int
    pop: int = 0
    owner: Optional[int] = None  # civ_id or None

@dataclass
class Civ:
    civ_id: int
    name: str
    stock_food: int = 0
    tiles: List[Coord] = field(default_factory=list)

@dataclass
class World:
    width: int
    height: int
    tiles: List[Tile]
    civs: Dict[int, Civ]
    week: int = 0
    seed: int = 42

    def idx(self, x: int, y: int) -> int:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            raise IndexError("tile OOB")
        return y * self.width + x

    def get_tile(self, x: int, y: int) -> Tile:
        return self.tiles[self.idx(x, y)]

    def neighbors4(self, x: int, y: int) -> List[Coord]:
        out: List[Coord] = []
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                out.append((nx, ny))
        return out

class SimulationEngine:
    """Pure-sim API usable by CLI, GUI, and tests."""
    def __init__(self, width: int = 48, height: int = 32, seed: int = 12345):
        self.rng = random.Random(seed)
        self.world = self._new_world(width, height, seed)

    def _new_world(self, w: int, h: int, seed: int) -> World:
        tiles = [Tile(x=i % w, y=i // w, pop=0, owner=None) for i in range(w*h)]
        return World(width=w, height=h, tiles=tiles, civs={}, week=0, seed=seed)

    def seed_population_everywhere(self, min_pop=3, max_pop=30) -> None:
        for t in self.world.tiles:
            t.pop = self.rng.randint(min_pop, max_pop)
            t.owner = None

    def add_civ(self, name: str, at: Coord) -> int:
        if not self._in_bounds(at):
            raise ValueError("Civ spawn out of bounds")
        cid = self._next_civ_id()
        civ = Civ(civ_id=cid, name=name, stock_food=50, tiles=[])
        self.world.civs[cid] = civ
        x, y = at
        t = self.world.get_tile(x, y)
        if t.owner is not None and t.owner != cid:
            pass  # allow coexist; must colonize later
        t.owner = cid
        civ.tiles.append(at)
        return cid

    def _next_civ_id(self) -> int:
        i = 0
        while i in self.world.civs:
            i += 1
        return i

    def _in_bounds(self, c: Coord) -> bool:
        x, y = c
        return 0 <= x < self.world.width and 0 <= y < self.world.height

    def advance_week(self) -> None:
        w = self.world
        # Production
        for civ in w.civs.values():
            gain = 0
            for (x, y) in civ.tiles:
                t = w.get_tile(x, y)
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
            for (x, y) in civ.tiles:
                for nx, ny in w.neighbors4(x, y):
                    tt = w.get_tile(nx, ny)
                    if tt.owner is None:
                        frontier.append((nx, ny))
            frontier.sort(key=lambda c: w.get_tile(*c).pop, reverse=True)
            for (fx, fy) in frontier:
                if civ.stock_food < 10:
                    break
                tt = w.get_tile(fx, fy)
                if tt.owner is None:
                    tt.owner = civ.civ_id
                    civ.tiles.append((fx, fy))
                    civ.stock_food -= 10
                    tried += 1
                if tried >= 3:
                    break

        w.week += 1

    def summary(self) -> Dict:
        w = self.world
        pop_total = sum(t.pop for t in w.tiles)
        owned = sum(1 for t in w.tiles if t.owner is not None)
        return {
            "week": w.week,
            "width": w.width, "height": w.height,
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
            "width": w.width, "height": w.height, "week": w.week, "seed": w.seed,
            "tiles": [{"x": t.x, "y": t.y, "pop": t.pop, "owner": t.owner} for t in w.tiles],
            "civs": {str(cid): {"civ_id": c.civ_id, "name": c.name, "stock_food": c.stock_food, "tiles": c.tiles}
                     for cid, c in w.civs.items()}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load_json(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        w = World(width=data["width"], height=data["height"], tiles=[], civs={}, week=data["week"], seed=data["seed"])
        tiles = [Tile(x=td["x"], y=td["y"], pop=td["pop"], owner=td["owner"]) for td in data["tiles"]]
        w.tiles = tiles
        civs: Dict[int, Civ] = {}
        for _, cd in data["civs"].items():
            civ = Civ(civ_id=cd["civ_id"], name=cd["name"], stock_food=cd["stock_food"],
                      tiles=[tuple(t) for t in cd["tiles"]])
            civs[civ.civ_id] = civ
        w.civs = civs
        self.world = w
        self.rng = random.Random(w.seed)
