import os
from engine import SimulationEngine

def test_end_to_end(tmp_path):
    world_path = tmp_path / "world.json"
    eng = SimulationEngine(width=32, height=20, seed=7)
    eng.seed_population_everywhere(min_pop=5, max_pop=15)
    eng.add_civ("A", (5, 5))
    eng.add_civ("B", (20, 10))
    eng.save_json(str(world_path))

    eng2 = SimulationEngine()
    eng2.load_json(str(world_path))
    for _ in range(100):
        eng2.advance_turn()

    s = eng2.summary()
    assert s["turn"] == 100
    assert s["total_pop"] > 0
    for _, info in s["civs"].items():
        assert info["tiles"] >= 1

    out = tmp_path / "world_after.json"
    eng2.save_json(str(out))
    eng3 = SimulationEngine()
    eng3.load_json(str(out))
    assert eng3.summary()["total_pop"] == s["total_pop"]
