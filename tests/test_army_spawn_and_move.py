from engine import SimulationEngine


def build_world():
    e = SimulationEngine(width=8, height=8, seed=1)
    for t in e.world.tiles:
        t.biome = "grass"
    cid = e.add_civ("A", (0, 0))
    return e, cid


def test_army_spawn_move_and_persist(tmp_path):
    e, cid = build_world()
    army = e.add_army(cid, (0, 0), strength=5)
    e.set_army_target(army, (2, 0))
    e.advance_turn()
    e.advance_turn()
    assert (army.q, army.r) == (2, 0)

    save_path = tmp_path / "world.json"
    e.save_json(save_path)

    e2 = SimulationEngine()
    e2.load_json(save_path)
    assert len(e2.world.armies) == 1
    a2 = e2.world.armies[0]
    assert (a2.q, a2.r) == (2, 0)
