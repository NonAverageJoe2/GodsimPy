"""
Tiny hook you can call from your engine to enable the enhanced system
without rewriting your existing engine.py right now.

Usage (inside SimulationEngine.__init__ after world is created):
    from engine_integration import enable_enhanced_colonization
    enable_enhanced_colonization(self)
"""

from typing import Any
from colonization_enhanced import integrate_enhanced_colonization

def enable_enhanced_colonization(engine: Any, enabled: bool = True) -> None:
    if not enabled:
        return
    if not hasattr(engine, "world"):
        raise RuntimeError("Engine must have .world before enabling colonization.")
    # ensure deterministic RNG exists
    if not hasattr(engine, "rng") or engine.rng is None:
        import random
        engine.rng = random.Random(int(getattr(engine, "seed", 0)))
    integrate_enhanced_colonization(engine)
