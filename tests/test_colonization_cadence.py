from engine import SimulationEngine


def test_colonization_triggers_on_cadence() -> None:
    eng = SimulationEngine(width=8, height=8, seed=1)
    w = eng.world

    # Clear any pre-existing state and set up a single civ
    for t in w.tiles:
        t.pop = 0
        t.owner = None
        if hasattr(t, "_pop_float"):
            del t._pop_float

    cid = eng.add_civ("A", (3, 3))
    src = w.get_tile(3, 3)
    src.pop = 100
    src.biome = "grass"
    src._pop_float = float(src.pop)

    assert len(w.civs[cid].tiles) == 1

    # Advance turns below the colonization period: no colonization yet
    eng.advance_turn(dt=0.1)
    assert len(w.civs[cid].tiles) == 1
    eng.advance_turn(dt=0.1)
    assert len(w.civs[cid].tiles) == 1

    # Next advancement crosses the period threshold and triggers colonization
    eng.advance_turn(dt=0.1)
    assert len(w.civs[cid].tiles) == 2
    assert src.pop == 90
    owned = set(w.civs[cid].tiles)
    owned.remove((3, 3))
    new_coord = owned.pop()
    new_tile = w.get_tile(*new_coord)
    assert new_tile.pop == 10

    # Further advancement without reaching the next period should not colonize again
    eng.advance_turn(dt=0.1)
    assert len(w.civs[cid].tiles) == 2
