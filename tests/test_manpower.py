from engine import SimulationEngine, compute_manpower_limit


def test_manpower_penalty_reduces_growth_and_food():
    eng1 = SimulationEngine(width=4, height=4, seed=1)
    eng1.seed_population_everywhere(min_pop=50, max_pop=50)
    cid1 = eng1.add_civ("A", (1, 1))
    tile1 = eng1.world.get_tile(1, 1)
    tile1.biome = "grass"
    eng1.world.civs[cid1].stock_food = 0
    eng1.advance_turn(dt=1.0)
    no_army_food = eng1.world.civs[cid1].stock_food
    pop_no_army = tile1.pop

    eng2 = SimulationEngine(width=4, height=4, seed=1)
    eng2.seed_population_everywhere(min_pop=50, max_pop=50)
    cid2 = eng2.add_civ("A", (1, 1))
    tile2 = eng2.world.get_tile(1, 1)
    tile2.biome = "grass"
    eng2.world.civs[cid2].stock_food = 100
    eng2.add_army(cid2, (1, 1), strength=50)
    eng2.advance_turn(dt=1.0)
    pop_with_army = tile2.pop

    assert eng2.world.civs[cid2].stock_food == 0
    assert no_army_food > eng2.world.civs[cid2].stock_food
    assert pop_no_army > pop_with_army
    expected_limit = compute_manpower_limit(50)
    assert eng2.world.civs[cid2].manpower_limit == expected_limit
    assert eng2.world.civs[cid2].manpower_used == 50

