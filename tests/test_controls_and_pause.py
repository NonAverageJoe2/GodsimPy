import unittest
import copy
import numpy as np

from sim.state import WorldState
from sim.terrain import generate_features
from sim.resources import yields_with_features
from sim.loop import advance_turn

# Try to import seeding helper from civilization; fallback to settlement
from sim import civilization
initialize_civs = civilization.initialize_civs
seed_neutral_population = getattr(civilization, "seed_neutral_population", None)
if seed_neutral_population is None:  # pragma: no cover - fallback for older versions
    from sim.settlement import seed_background_population as seed_neutral_population


class ControlsPauseTest(unittest.TestCase):
    def test_controls_and_pause(self) -> None:
        rng = np.random.default_rng(1337)
        w = h = 16
        height_map = rng.random((h, w), dtype=np.float32)
        biome_map = rng.choice(
            np.array([0, 1, 2, 3, 4], dtype=np.uint8),
            size=(h, w),
            p=[0.4, 0.1, 0.05, 0.1, 0.35],
        )
        ws = WorldState(
            width=w,
            height=h,
            turn=0,
            seed=9876,
            height_map=height_map,
            biome_map=biome_map,
            owner_map=np.full((h, w), -1, dtype=np.int32),
            pop_map=np.zeros((h, w), dtype=np.float32),
            sea_level=0.5,
            hex_radius=1.0,
        )

        features = generate_features(ws.biome_map, rng)
        yields_with_features(ws.biome_map, features)

        seed_neutral_population(
            ws,
            feature_map=features,
            seed=2024,
            max_fraction_of_capacity=0.05,
            min_people_per_tile=5.0,
        )
        land = (ws.biome_map != 3) & (ws.biome_map != 2)
        self.assertTrue(np.all(ws.pop_map[land] > 0))

        base_pop = 15.0
        initialize_civs(ws, n_civs=2, base_pop=base_pop, seed=7)
        owned = ws.owner_map >= 0
        self.assertTrue(np.all(ws.pop_map[owned] >= base_pop))
        self.assertTrue(np.all(ws.pop_map[land & ~owned] > 0))

        turn0 = ws.turn
        date0 = ws.get_date_tuple()
        owner0 = ws.owner_map.copy()
        pop0 = ws.pop_map.copy()
        ws.paused = True
        advance_turn(ws, feature_map=features, steps=3)
        self.assertEqual(turn0, ws.turn)
        self.assertEqual(date0, ws.get_date_tuple())
        self.assertTrue(np.array_equal(owner0, ws.owner_map))
        self.assertTrue(np.array_equal(pop0, ws.pop_map))
        ws.paused = False

        base_sum = ws.pop_map.sum()
        ws_week = copy.deepcopy(ws)
        ws_week.time_scale = "week"
        advance_turn(ws_week, feature_map=features, steps=1)
        delta_w = ws_week.pop_map.sum() - base_sum

        ws_year = copy.deepcopy(ws)
        ws_year.time_scale = "year"
        advance_turn(ws_year, feature_map=features, steps=1)
        delta_y = ws_year.pop_map.sum() - base_sum
        self.assertGreaterEqual(delta_w, 0.0)
        self.assertGreater(delta_y, delta_w)

        def ymd(t: tuple[int, int, int]) -> tuple[int, int, int]:
            m, d, y = t
            return y, m, d

        A = ws.get_date_tuple()
        ws.time_scale = "week"
        advance_turn(ws, feature_map=features, steps=1)
        B = ws.get_date_tuple()
        ws.time_scale = "month"
        advance_turn(ws, feature_map=features, steps=1)
        C = ws.get_date_tuple()
        ws.time_scale = "week"
        advance_turn(ws, feature_map=features, steps=1)
        D = ws.get_date_tuple()
        self.assertTrue(ymd(A) < ymd(B) < ymd(C) < ymd(D))

        if (ws.turn + 1) % 4 == 0:
            advance_turn(ws, feature_map=features, steps=1)
        if ws.turn % 4 == 0:
            advance_turn(ws, feature_map=features, steps=1)
        owned_before = int(np.sum(ws.owner_map >= 0))
        advance_turn(ws, feature_map=features, steps=1)
        owned_after = int(np.sum(ws.owner_map >= 0))
        self.assertEqual(owned_before, owned_after)

        total_pop = float(ws.pop_map.sum())
        print(
            f"summary: turn={ws.turn} date={ws.get_date_tuple()} pop={total_pop:.1f} owned={owned_after}"
        )


if __name__ == "__main__":
    unittest.main()
