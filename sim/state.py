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
    )
