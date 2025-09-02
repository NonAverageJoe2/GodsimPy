from __future__ import annotations

"""World state persistence helpers."""

from dataclasses import dataclass
from typing import Any, Dict
import numpy as np


@dataclass
class WorldState:
    """Container for persistent world/civilization simulation state."""

    width: int
    height: int
    turn: int
    seed: int

    height_map: np.ndarray
    biome_map: np.ndarray
    owner_map: np.ndarray
    pop_map: np.ndarray

    sea_level: float
    hex_radius: float

    # Calendar and simulation control fields
    date_month: int = 1
    date_day: int = 1
    date_year: int = 1
    time_scale: str = "week"
    paused: bool = False

    def __post_init__(self) -> None:
        expected = (self.height, self.width)
        checks = (
            ("height_map", self.height_map, np.float32),
            ("biome_map", self.biome_map, np.uint8),
            ("owner_map", self.owner_map, np.int32),
            ("pop_map", self.pop_map, np.float32),
        )
        for name, arr, dtype in checks:
            if arr.shape != expected:
                raise ValueError(f"{name} shape {arr.shape} != {expected}")
            if arr.dtype != dtype:
                raise ValueError(f"{name} dtype {arr.dtype} != {dtype}")

        if self.date_month < 1 or self.date_day < 1 or self.date_year < 1:
            raise ValueError("date components must be >=1")
        if self.time_scale not in {"week", "month", "year"}:
            raise ValueError(f"invalid time_scale {self.time_scale!r}")

    def get_date_tuple(self) -> tuple[int, int, int]:
        """Return (month, day, year) tuple."""
        return (self.date_month, self.date_day, self.date_year)

    def set_date_tuple(self, m: int, d: int, y: int) -> None:
        """Update date fields after validating positivity."""
        if m < 1 or d < 1 or y < 1:
            raise ValueError("date components must be >=1")
        self.date_month = int(m)
        self.date_day = int(d)
        self.date_year = int(y)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable dictionary matching NPZ keys."""
        return {
            "width": self.width,
            "height": self.height,
            "turn": self.turn,
            "seed": self.seed,
            "sea_level": np.float32(self.sea_level),
            "hex_radius": np.float32(self.hex_radius),
            "height_map": self.height_map,
            "biome_map": self.biome_map,
            "owner_map": self.owner_map,
            "pop_map": self.pop_map,
            "date_m": np.int32(self.date_month),
            "date_d": np.int32(self.date_day),
            "date_y": np.int32(self.date_year),
            "time_scale": self.time_scale,
            "paused": np.bool_(self.paused),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldState":
        """Build a :class:`WorldState` from ``to_dict`` output."""
        required = {
            "width",
            "height",
            "turn",
            "seed",
            "sea_level",
            "hex_radius",
            "height_map",
            "biome_map",
            "owner_map",
            "pop_map",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"missing keys: {sorted(missing)}")

        width = int(data["width"])
        height = int(data["height"])
        turn = int(data["turn"])
        seed = int(data["seed"])
        sea_level = float(data["sea_level"])
        hex_radius = float(data["hex_radius"])
        expected = (height, width)

        date_m = int(data.get("date_m", 1))
        date_d = int(data.get("date_d", 1))
        date_y = int(data.get("date_y", 1))
        if date_m < 1 or date_d < 1 or date_y < 1:
            raise ValueError("date components must be >=1")

        time_scale = str(data.get("time_scale", "week"))
        if time_scale not in {"week", "month", "year"}:
            raise ValueError(f"invalid time_scale {time_scale!r}")

        p_val = data.get("paused", False)
        if isinstance(p_val, np.ndarray):
            if p_val.shape != ():
                raise ValueError("paused must be scalar")
            p_val = p_val.item()
        if not isinstance(p_val, (bool, np.bool_, int, np.integer)):
            raise ValueError("paused must be boolean")
        paused = bool(p_val)

        def check(name: str, arr: Any, dtype: np.dtype) -> np.ndarray:
            a = np.asarray(arr)
            if a.shape != expected:
                raise ValueError(f"{name} shape {a.shape} != {expected}")
            if a.dtype != dtype:
                raise ValueError(f"{name} dtype {a.dtype} != {dtype}")
            return a

        height_map = check("height_map", data["height_map"], np.float32)
        biome_map = check("biome_map", data["biome_map"], np.uint8)
        owner_map = check("owner_map", data["owner_map"], np.int32)
        pop_map = check("pop_map", data["pop_map"], np.float32)

        return cls(
            width=width,
            height=height,
            turn=turn,
            seed=seed,
            height_map=height_map,
            biome_map=biome_map,
            owner_map=owner_map,
            pop_map=pop_map,
            sea_level=sea_level,
            hex_radius=hex_radius,
            date_month=date_m,
            date_day=date_d,
            date_year=date_y,
            time_scale=time_scale,
            paused=paused,
        )


def from_worldgen(height_map: np.ndarray, biome_map: np.ndarray, sea_level: float,
                   width: int, height: int, hex_radius: float, seed: int) -> WorldState:
    """Construct initial world state from world generation output."""
    expected = (height, width)
    h = np.asarray(height_map, dtype=np.float32)
    if h.shape != expected:
        raise ValueError(f"height_map shape {h.shape} != {expected}")
    b = np.asarray(biome_map, dtype=np.uint8)
    if b.shape != expected:
        raise ValueError(f"biome_map shape {b.shape} != {expected}")
    owner = np.full(expected, -1, dtype=np.int32)
    pop = np.zeros(expected, dtype=np.float32)
    return WorldState(
        width=width,
        height=height,
        turn=0,
        seed=seed,
        height_map=h,
        biome_map=b,
        owner_map=owner,
        pop_map=pop,
        sea_level=float(sea_level),
        hex_radius=float(hex_radius),
    )


def save_npz(ws: WorldState, path: str) -> None:
    """Persist a :class:`WorldState` to ``path`` using ``np.savez_compressed``."""
    np.savez_compressed(
        path,
        width=np.array(ws.width, dtype=np.int32),
        height=np.array(ws.height, dtype=np.int32),
        turn=np.array(ws.turn, dtype=np.int32),
        seed=np.array(ws.seed, dtype=np.int32),
        sea_level=np.array(ws.sea_level, dtype=np.float32),
        hex_radius=np.array(ws.hex_radius, dtype=np.float32),
        height_map=ws.height_map,
        biome_map=ws.biome_map,
        owner_map=ws.owner_map,
        pop_map=ws.pop_map,
        date_m=np.array(ws.date_month, dtype=np.int32),
        date_d=np.array(ws.date_day, dtype=np.int32),
        date_y=np.array(ws.date_year, dtype=np.int32),
        time_scale=np.array(ws.time_scale),
        paused=np.array(ws.paused, dtype=np.bool_),
    )


def load_npz(path: str) -> WorldState:
    """Load a :class:`WorldState` from ``path`` and validate its contents."""
    with np.load(path) as data:
        required = {
            "width",
            "height",
            "turn",
            "seed",
            "sea_level",
            "hex_radius",
            "height_map",
            "biome_map",
            "owner_map",
            "pop_map",
        }
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"missing keys: {sorted(missing)}")

        width = int(data["width"])  # np.int64 -> int
        height = int(data["height"])
        turn = int(data["turn"])
        seed = int(data["seed"])
        sea_level = float(data["sea_level"])
        hex_radius = float(data["hex_radius"])
        expected = (height, width)

        date_m = 1
        if "date_m" in data.files:
            date_m = int(data["date_m"])
            if date_m < 1:
                raise ValueError("date components must be >=1")

        date_d = 1
        if "date_d" in data.files:
            date_d = int(data["date_d"])
            if date_d < 1:
                raise ValueError("date components must be >=1")

        date_y = 1
        if "date_y" in data.files:
            date_y = int(data["date_y"])
            if date_y < 1:
                raise ValueError("date components must be >=1")

        time_scale = "week"
        if "time_scale" in data.files:
            time_scale = str(data["time_scale"])
            if time_scale not in {"week", "month", "year"}:
                raise ValueError(f"invalid time_scale {time_scale!r}")

        paused = False
        if "paused" in data.files:
            p_val = data["paused"]
            if isinstance(p_val, np.ndarray):
                if p_val.shape != ():
                    raise ValueError("paused must be scalar")
                p_val = p_val.item()
            if not isinstance(p_val, (bool, np.bool_, int, np.integer)):
                raise ValueError("paused must be boolean")
            paused = bool(p_val)

        def fetch(name: str, dtype: np.dtype) -> np.ndarray:
            arr = data[name]
            if arr.shape != expected:
                raise ValueError(f"{name} shape {arr.shape} != {expected}")
            if arr.dtype != dtype:
                raise ValueError(f"{name} dtype {arr.dtype} != {dtype}")
            return arr

        height_map = fetch("height_map", np.float32)
        biome_map = fetch("biome_map", np.uint8)
        owner_map = fetch("owner_map", np.int32)
        pop_map = fetch("pop_map", np.float32)

    return WorldState(
        width=width,
        height=height,
        turn=turn,
        seed=seed,
        height_map=height_map,
        biome_map=biome_map,
        owner_map=owner_map,
        pop_map=pop_map,
        sea_level=sea_level,
        hex_radius=hex_radius,
        date_month=date_m,
        date_day=date_d,
        date_year=date_y,
        time_scale=time_scale,
        paused=paused,
    )
