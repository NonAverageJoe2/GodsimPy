from __future__ import annotations

"""Simple trade goods system with support for metal ores and refined goods."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Tuple, Optional


class TradeGood(Enum):
    """Enumeration of available trade goods.

    The list distinguishes between raw ores and their processed counterparts so
    that technology requirements can track where minerals are mined and how
    they are refined.  ``*_ORE`` entries represent the raw material while the
    plain names represent ingots or worked metal.
    """

    GRAIN = auto()
    CATTLE = auto()
    WOOD = auto()
    WOOL = auto()
    STONE = auto()
    COPPER_ORE = auto()
    TIN_ORE = auto()
    IRON_ORE = auto()
    COPPER = auto()
    IRON = auto()
    BRONZE = auto()
    TOOLS = auto()
    WEAPONS = auto()
    CLOTH = auto()
    POTTERY = auto()
    FURNITURE = auto()
    WINE = auto()
    SILK = auto()
    JEWELRY = auto()
    SPICES = auto()
    INCENSE = auto()


# Basic colour mapping used by the visualisation helpers.  The palette only
# needs to be stable, it does not need to be perfect.
GOOD_COLOURS: Dict[TradeGood, Tuple[int, int, int]] = {
    TradeGood.GRAIN: (210, 185, 60),
    TradeGood.CATTLE: (160, 100, 60),
    TradeGood.WOOD: (92, 64, 51),
    TradeGood.WOOL: (200, 200, 200),
    TradeGood.STONE: (130, 130, 130),
    TradeGood.COPPER_ORE: (130, 80, 40),
    TradeGood.TIN_ORE: (180, 180, 180),
    TradeGood.IRON_ORE: (60, 60, 60),
    TradeGood.COPPER: (184, 115, 51),
    TradeGood.IRON: (80, 80, 80),
    TradeGood.BRONZE: (140, 120, 70),
    TradeGood.TOOLS: (120, 120, 150),
    TradeGood.WEAPONS: (80, 80, 120),
    TradeGood.CLOTH: (150, 120, 180),
    TradeGood.POTTERY: (190, 120, 80),
    TradeGood.FURNITURE: (150, 100, 60),
    TradeGood.WINE: (150, 0, 0),
    TradeGood.SILK: (200, 150, 200),
    TradeGood.JEWELRY: (255, 215, 0),
    TradeGood.SPICES: (210, 90, 40),
    TradeGood.INCENSE: (180, 170, 160),
}


@dataclass
class TradeGoodProduction:
    """Production data for a single trade good on a tile."""

    percentage: float = 0.0   # Share of workers devoted to this good (0-100)
    workers: int = 0          # Number of workers
    efficiency: float = 1.0   # Production efficiency multiplier
    amount: float = 0.0       # Accumulated production output


@dataclass
class TileTradeGoods:
    """Trade goods state for a specific tile."""

    ideal_goods: List[TradeGood]
    max_goods_types: int
    active_goods: Dict[TradeGood, TradeGoodProduction] = field(default_factory=dict)


class TradeGoodsManager:
    """Manages trade goods production for every tile in the world."""

    def __init__(self, world):
        self.world = world
        self.tile_goods: Dict[Tuple[int, int], TileTradeGoods] = {}
        self._initialize_tiles()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------
    def _initialize_tiles(self) -> None:
        for tile in self.world.tiles:
            goods = self._ideal_goods_for_biome(tile.biome)
            settlement = getattr(tile, "settlement", "hamlet")
            max_types = self._max_goods_for_settlement(settlement)
            self.tile_goods[(tile.q, tile.r)] = TileTradeGoods(
                ideal_goods=goods, max_goods_types=max_types)

    def _ideal_goods_for_biome(self, biome: str) -> List[TradeGood]:
        mapping = {
            "grass": [TradeGood.GRAIN, TradeGood.CATTLE, TradeGood.WOOL],
            "forest": [TradeGood.WOOD, TradeGood.FURS if hasattr(TradeGood, 'FURS') else TradeGood.WOOL],
            "mountain": [
                TradeGood.STONE,
                TradeGood.COPPER_ORE,
                TradeGood.TIN_ORE,
                TradeGood.IRON_ORE,
            ],
            "desert": [TradeGood.SPICES, TradeGood.INCENSE],
            "coast": [TradeGood.FISH if hasattr(TradeGood, 'FISH') else TradeGood.GRAIN],
            "ocean": [TradeGood.FISH if hasattr(TradeGood, 'FISH') else TradeGood.GRAIN],
        }
        return mapping.get(biome, [TradeGood.GRAIN])

    def _max_goods_for_settlement(self, settlement: str) -> int:
        mapping = {
            "hamlet": 3,
            "village": 5,
            "town": 7,
            "city": 10,
            "capital": 10,
        }
        return mapping.get(settlement, 3)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_json(self) -> Dict:
        data = {}
        for (q, r), tg in self.tile_goods.items():
            data[f"{q},{r}"] = {
                "ideal_goods": [g.name for g in tg.ideal_goods],
                "max_goods_types": tg.max_goods_types,
                "active_goods": {
                    g.name: vars(prod) for g, prod in tg.active_goods.items()
                },
            }
        return data

    def load_json(self, data: Dict) -> None:
        self.tile_goods.clear()
        for key, tg_data in data.items():
            q, r = map(int, key.split(","))
            tg = TileTradeGoods(
                ideal_goods=[TradeGood[g] for g in tg_data.get("ideal_goods", [])],
                max_goods_types=tg_data.get("max_goods_types", 3),
                active_goods={
                    TradeGood[g]: TradeGoodProduction(**prod)
                    for g, prod in tg_data.get("active_goods", {}).items()
                },
            )
            self.tile_goods[(q, r)] = tg

    # ------------------------------------------------------------------
    # Simulation logic
    # ------------------------------------------------------------------
    def evolve_production(self, q: int, r: int, dt: float) -> None:
        tg = self.tile_goods.get((q, r))
        if tg is None:
            return
        for prod in tg.active_goods.values():
            prod.amount += prod.percentage / 100.0 * prod.efficiency * dt

    def get_province_trade_summary(self, tiles: List[Tuple[int, int]]) -> Dict[str, float]:
        summary: Dict[str, float] = {}
        for coord in tiles:
            tg = self.tile_goods.get(tuple(coord))
            if tg is None:
                continue
            for good, prod in tg.active_goods.items():
                summary[good.name] = summary.get(good.name, 0.0) + prod.amount
        return summary
