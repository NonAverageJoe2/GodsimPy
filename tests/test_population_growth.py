from engine import SimulationEngine


def test_population_growth_stable_across_dt():
    eng_week = SimulationEngine(width=8, height=8, seed=2)
    eng_year = SimulationEngine(width=8, height=8, seed=2)

    for t in eng_week.world.tiles:
        t.pop = 20
        t.biome = "grass"
    for t in eng_year.world.tiles:
        t.pop = 20
        t.biome = "grass"

    dt_week = 1.0 / 52.0
    for _ in range(52):
        eng_week.advance_turn(dt=dt_week)
    eng_year.advance_turn(dt=1.0)

    pops_week = [t.pop for t in eng_week.world.tiles]
    pops_year = [t.pop for t in eng_year.world.tiles]

    assert all(p >= 0 for p in pops_week)
    assert all(p >= 0 for p in pops_year)

    total_week = sum(pops_week)
    total_year = sum(pops_year)
    assert total_year > 0
    diff = abs(total_week - total_year) / total_year
    assert diff < 0.05
