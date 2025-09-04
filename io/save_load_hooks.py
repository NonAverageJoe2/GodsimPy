"""
Helpers to persist the enhanced colonization system state alongside your existing saves.

Integrate into your save/load code:
    # When saving
    state["colonization_enhanced"] = export_colonization_state(engine)

    # When loading (after engine/world constructed)
    import_colonization_state(engine, state.get("colonization_enhanced"))
"""

from typing import Any, Optional, Dict

def export_colonization_state(engine: Any) -> Dict:
    sys = getattr(engine, "colonization_system", None)
    if sys is None:
        return {}
    try:
        return sys.to_dict()
    except Exception:
        return {}

def import_colonization_state(engine: Any, data: Optional[Dict]) -> None:
    if not data:
        return
    sys = getattr(engine, "colonization_system", None)
    if sys is None:
        # allow lazy attachment
        try:
            from colonization_enhanced import integrate_enhanced_colonization
            integrate_enhanced_colonization(engine)
            sys = engine.colonization_system
        except Exception:
            return
    try:
        sys.from_dict(data)
    except Exception:
        pass
