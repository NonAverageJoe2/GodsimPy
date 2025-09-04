import unittest
import math

class TestEnhancedColonization(unittest.TestCase):
    def setUp(self):
        try:
            from engine import SimulationEngine
            self.Engine = SimulationEngine
        except Exception:
            self.Engine = None

    def test_population_conservation(self):
        if self.Engine is None:
            self.skipTest("engine.SimulationEngine not available")
        eng = self.Engine(width=24, height=24, seed=12345)
        # enable enhanced colonization
        from engine_integration import enable_enhanced_colonization
        enable_enhanced_colonization(eng, enabled=True)

        # Add a couple civs (engine must implement add_civ(name, (q,r)))
        eng.add_civ("A", (6, 6))
        eng.add_civ("B", (16, 16))

        # seed some population
        for civ in eng.world.civs.values():
            for (q, r) in list(civ.tiles):
                t = eng.world.get_tile(q, r)
                t.pop = 100

        # Run a bunch of turns
        def total_pop():
            tot = 0
            for r in range(eng.world.height_hex):
                for q in range(eng.world.width_hex):
                    t = eng.world.get_tile(q, r)
                    tot += int(getattr(t, "pop", 0))
            return tot

        start = total_pop()
        for _ in range(60):
            eng.advance_turn()
        end = total_pop()

        self.assertGreater(start, 0)
        # conservation: equal or small rounding drift
        self.assertTrue(abs(end - start) <= 2)

    def test_no_negative_pop(self):
        if self.Engine is None:
            self.skipTest("engine.SimulationEngine not available")
        eng = self.Engine(width=20, height=20, seed=7)
        from engine_integration import enable_enhanced_colonization
        enable_enhanced_colonization(eng, enabled=True)
        eng.add_civ("Solo", (10, 10))
        for _ in range(40):
            eng.advance_turn()
        for r in range(eng.world.height_hex):
            for q in range(eng.world.width_hex):
                t = eng.world.get_tile(q, r)
                self.assertGreaterEqual(int(getattr(t, "pop", 0)), 0)

if __name__ == "__main__":
    unittest.main()
