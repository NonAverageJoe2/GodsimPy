import numpy as np
from sim.settlements import initiate_expansion, CITY


def test_initiate_expansion_balances_population():
    pop = np.array([[100, 10, 30]], dtype=np.float32)
    settlement = np.array([[CITY, CITY, CITY]], dtype=np.uint8)
    owner = np.array([[0, 0, 0]], dtype=np.int32)
    rng = np.random.default_rng(0)

    result = initiate_expansion(
        pop.copy(), settlement, owner, civ_id=0, rng=rng, expansion_chance=1.0
    )
    mask = (owner == 0) & (settlement >= CITY)
    pops = result[mask]

    assert pops.sum() == 140
    assert pops.max() - pops.min() <= 1


def test_initiate_expansion_can_skip():
    pop = np.array([[100, 10, 30]], dtype=np.float32)
    settlement = np.array([[CITY, CITY, CITY]], dtype=np.uint8)
    owner = np.array([[0, 0, 0]], dtype=np.int32)
    rng = np.random.default_rng(1)

    result = initiate_expansion(
        pop.copy(), settlement, owner, civ_id=0, rng=rng, expansion_chance=0.0
    )
    np.testing.assert_array_equal(result, pop)
