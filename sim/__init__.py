"""
Compatibility shim so legacy code/tests that do `import sim` keep working.
Re-exports the new engine types implemented in engine.py.
"""
from typing import Any
from engine import SimulationEngine, World, Tile, Civ

__all__ = ["SimulationEngine", "World", "Tile", "Civ"]

def __getattr__(name: str) -> Any:
    # Only expose known symbols; fail clearly for anything else.
    if name in __all__:
        return globals()[name]
    raise AttributeError(f"module 'sim' has no attribute {name!r}")
