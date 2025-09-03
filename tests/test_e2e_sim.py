import os
import tempfile
import unittest
import numpy as np

from sim.state import from_worldgen, save_npz, load_npz
from sim.loop import advance_turn
from sim.resources import yields_with_features, carrying_capacity
from sim.terrain import generate_features
from sim.civilization import initialize_civs
from sim.cohorts import init_from_total, step_with_capacity, totals_from_cohorts


SEED_BIOME = 1
SEED_FEATURES = 2
SEED_CIV = 3
WS_SEED = 4

WIDTH = 16
HEIGHT = 16

BIOME_CHOICES = np.array([0, 1, 2, 3, 4], dtype=np.uint8)
BIOME_PROB = [0.65, 0.15, 0.07, 0.05, 0.08]


def step_n(ws, feature_map, n):
    dates = []
    for _ in range(n):
        ws = advance_turn(ws, feature_map=feature_map, steps=1)
        dates.append(ws.get_date_tuple())
    return ws, dates


def run_once():
    rng_b = np.random.default_rng(SEED_BIOME)
    biome = rng_b.choice(BIOME_CHOICES, p=BIOME_PROB, size=(HEIGHT, WIDTH)).astype(np.uint8)
    height_map = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    ws = from_worldgen(height_map, biome, sea_level=0.0, width=WIDTH, height=HEIGHT, hex_radius=1.0, seed=WS_SEED)

    features = generate_features(biome, np.random.default_rng(SEED_FEATURES))
    ws, _ = initialize_civs(ws, n_civs=3, base_pop=120.0, seed=SEED_CIV)

    initial_owned = int(np.count_nonzero(ws.owner_map >= 0))
    dates = [ws.get_date_tuple()]

    ws, d = step_n(ws, features, 8)
    dates.extend(d)
    ws.time_scale = "month"
    ws, d = step_n(ws, features, 6)
    dates.extend(d)
    ws.time_scale = "year"
    ws, d = step_n(ws, features, 2)
    dates.extend(d)

    y = yields_with_features(ws.biome_map, features)
    K = carrying_capacity(y["food"])
    coh = init_from_total(ws.pop_map)
    coh2 = step_with_capacity(coh, K, dt_years=30 / 365)
    ws.pop_map = np.ascontiguousarray(totals_from_cohorts(coh2), dtype=np.float32)

    return ws, features, dates, initial_owned, coh2


class TestEndToEnd(unittest.TestCase):
    def test_end_to_end(self):
        ws, features, dates, initial_owned, coh2 = run_once()

        # Save/load roundtrip
        with tempfile.TemporaryDirectory() as tmpd:
            path = os.path.join(tmpd, "world_e2e.npz")
            save_npz(ws, path)
            ws2 = load_npz(path)
        self.assertTrue(np.array_equal(ws.height_map, ws2.height_map))
        self.assertTrue(np.array_equal(ws.biome_map, ws2.biome_map))
        self.assertTrue(np.array_equal(ws.owner_map, ws2.owner_map))
        self.assertTrue(np.array_equal(ws.pop_map, ws2.pop_map))

        # Date checks
        start = dates[0]
        self.assertEqual(start, (1, 1, 1))
        self.assertNotEqual(dates[8], start)
        for prev, cur in zip(dates, dates[1:]):
            self.assertLess((prev[2], prev[0], prev[1]), (cur[2], cur[0], cur[1]))
        self.assertGreaterEqual(dates[-1][2], start[2] + 1)

        # Finite checks
        y = yields_with_features(ws.biome_map, features)
        self.assertTrue(np.isfinite(y["food"]).all())
        self.assertTrue(np.isfinite(y["prod"]).all())
        self.assertTrue(np.isfinite(ws.pop_map).all())
        self.assertTrue(np.isfinite(ws.owner_map.astype(float)).all())

        # Population and ownership checks
        self.assertTrue((ws.pop_map >= 0).all())
        self.assertGreater(ws.pop_map.sum(), 0.0)
        owned = int(np.count_nonzero(ws.owner_map >= 0))
        self.assertGreaterEqual(owned, initial_owned)
        self.assertGreaterEqual(ws.owner_map.min(), -1)
        self.assertLess(ws.owner_map.max(), 3)

        # Cohort consistency
        pop_from_coh = totals_from_cohorts(coh2)
        self.assertTrue(np.isfinite(pop_from_coh).all())
        self.assertTrue(np.allclose(pop_from_coh, ws.pop_map, atol=1e-3))

        # Determinism
        ws_b, _, _, _, _ = run_once()
        self.assertTrue(np.array_equal(ws.owner_map, ws_b.owner_map))
        self.assertTrue(np.array_equal(ws.pop_map, ws_b.pop_map))

        m, d, yv = ws.get_date_tuple()
        total_pop = float(ws.pop_map.sum())
        print(f"OK turn={ws.turn} date={m}/{d}/{yv} owned={owned} pop={round(total_pop, 2)}")


if __name__ == "__main__":
    unittest.main()
