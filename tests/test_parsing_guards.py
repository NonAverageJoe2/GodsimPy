import json
from pathlib import Path

from engine import SimulationEngine
from sim.safe_parse import to_int, to_float


def test_safe_parse_helpers():
    assert to_int("7") == 7
    assert to_int("bad", default=3) == 3
    assert to_float("1.5") == 1.5
    assert to_float("nan", default=2.5) == 2.5


def test_tile_loader_guard(tmp_path: Path):
    class DummyTech:
        def save_state(self):
            return {}
        def load_state(self, state):
            return

    # Create engine instance without running heavy worldgen
    eng = object.__new__(SimulationEngine)
    eng.tech_system = DummyTech()
    # Craft minimal world save with problematic strings
    data = {
        "width_hex": 1,
        "height_hex": 1,
        "hex_size": 1,
        "sea_level": 0.0,
        "turn": 0,
        "seed": 1,
        "time_scale": "week",
        "calendar": {"year": 1, "month": 1, "day": 1},
        "colonize_period_years": 0.25,
        "colonize_elapsed": 0.0,
        "tiles": [
            {"q": 0, "r": 0, "height": "2.5", "biome": "mountain", "pop": "12", "owner": "NA"}
        ],
        "civs": {},
        "armies": [],
        "technology": eng.tech_system.save_state(),
    }
    path = tmp_path / "world.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    eng.load_json(str(path))
    tile = eng.world.get_tile(0, 0)
    assert tile.biome == "mountain"
    assert tile.pop == 12
    assert tile.owner == 0  # default from to_int
