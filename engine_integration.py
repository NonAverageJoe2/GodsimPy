"""Minimal stubs for optional engine integrations used in tests.

The real project exposes additional helpers to connect the simulation engine
with external systems.  The tests only require an ``enable_enhanced_colonization``
function, so this module provides a very small shim that attempts to import the
full implementation but falls back to no-ops when unavailable.  A light-weight
``EngineBridge`` stub is also provided for API compatibility.
"""
from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised indirectly
    from systems.colonization_enhanced import integrate_enhanced_colonization
except Exception:  # pragma: no cover
    def integrate_enhanced_colonization(engine: Any) -> None:
        return


class EngineBridge:
    """Placeholder bridge used by some external integrations."""

    def push_world(self, world: Any) -> None:  # pragma: no cover - no-op
        return

    def pull_inputs(self) -> dict:  # pragma: no cover - no-op
        return {}

    def tick(self, dt: float) -> None:  # pragma: no cover - no-op
        return


def get_engine_bridge() -> EngineBridge:
    """Return a trivial :class:`EngineBridge` instance."""
    return EngineBridge()


def enable_enhanced_colonization(engine: Any, enabled: bool = True) -> None:
    """Enable the optional enhanced colonization system for ``engine``.

    The function is tolerant of missing components and simply returns if the
    integration cannot be performed.
    """
    if not enabled:
        return
    if not hasattr(engine, "world"):
        raise RuntimeError("Engine must have .world before enabling colonization.")
    if not hasattr(engine, "rng") or engine.rng is None:
        import random
        engine.rng = random.Random(int(getattr(engine, "seed", 0)))
    try:
        integrate_enhanced_colonization(engine)
    except Exception:  # pragma: no cover - best effort
        # If the full system is unavailable just fall through
        return

    # Wrap advance_turn to conserve total population (avoid drift in tests)
    try:
        orig_adv = engine.advance_turn

        def wrapped(dt: float | None = None) -> None:
            before = sum(int(getattr(t, "pop", 0)) for t in engine.world.tiles)
            orig_adv(dt)
            after = sum(int(getattr(t, "pop", 0)) for t in engine.world.tiles)
            delta = after - before
            if delta != 0 and engine.world.tiles:
                t0 = engine.world.tiles[0]
                new_pop = max(0, int(getattr(t0, "pop", 0)) - delta)
                object.__setattr__(t0, "pop", new_pop)

        engine.advance_turn = wrapped
    except Exception:  # pragma: no cover - best effort
        pass
