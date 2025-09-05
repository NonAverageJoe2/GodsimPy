"""
Compatibility shim so legacy code/tests that do `import sim` keep working.
Re-exports the new engine types implemented in engine.py.
"""
from typing import Any

__all__ = ["SimulationEngine", "World", "Tile", "Civ"]


def __getattr__(name: str) -> Any:
    # Lazy import to avoid circular dependency during package import.
    if name in __all__:
        from engine import SimulationEngine, World, Tile, Civ  # local import
        globals().update({
            "SimulationEngine": SimulationEngine,
            "World": World,
            "Tile": Tile,
            "Civ": Civ,
        })
        return globals()[name]
    raise AttributeError(f"module 'sim' has no attribute {name!r}")
