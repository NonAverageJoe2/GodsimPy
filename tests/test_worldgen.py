import numpy as np
from engine import SimulationEngine


def test_worldgen_deterministic_and_biomes():
    eng1 = SimulationEngine(width=24, height=16, seed=123)
    eng2 = SimulationEngine(width=24, height=16, seed=123)
    # Heights and biomes should match exactly for same seed
    h1 = [ (t.height, t.biome) for t in eng1.world.tiles ]
    h2 = [ (t.height, t.biome) for t in eng2.world.tiles ]
    assert h1 == h2

    # And different seeds should produce differences
    eng3 = SimulationEngine(width=24, height=16, seed=456)
    h3 = [ (t.height, t.biome) for t in eng3.world.tiles ]
    assert h1 != h3

    biomes = {t.biome for t in eng1.world.tiles}
    assert len(biomes) > 1  # non-trivial biome variety
