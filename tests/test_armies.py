from engine import SimulationEngine


def setup_world(width=6, height=6, seed=1):
    e = SimulationEngine(width=width, height=height, seed=seed)
    for t in e.world.tiles:
        t.biome = "grass"
    return e


def test_army_pathfinding_and_movement():
    e = setup_world()
    e.world.get_tile(1, 0).biome = "mountain"
    cid = e.add_civ("A", (0, 0))
    army = e.add_army(cid, (0, 0), strength=5)
    e.set_army_target(army, (2, 0))
    e.advance_turn()  # week
    assert (army.q, army.r) == (0, 1)
    e.advance_turn()
    assert (army.q, army.r) == (1, 1)
    e.advance_turn()
    assert (army.q, army.r) == (2, 0)


def test_supply_attrition_and_no_negative_strength():
    e = SimulationEngine(width=4, height=4, seed=1)
    tile = e.world.get_tile(0, 0)
    tile.biome = "mountain"
    cid = e.add_civ("A", (0, 0))
    army = e.add_army(cid, (0, 0), strength=2, supply=1)
    e.advance_turn()
    assert army.supply == 0
    assert army.strength == 1
    e.advance_turn()
    assert len(e.world.armies) == 0


def test_combat_resolution():
    e = SimulationEngine(width=4, height=4, seed=1)
    e.world.get_tile(0, 0).biome = "grass"
    cid1 = e.add_civ("A", (0, 0))
    cid2 = e.add_civ("B", (0, 0))
    a1 = e.add_army(cid1, (0, 0), strength=10)
    a2 = e.add_army(cid2, (0, 0), strength=6)
    e.advance_turn()
    assert len(e.world.armies) == 1
    assert e.world.armies[0].civ_id == cid1
    assert e.world.armies[0].strength == 7
