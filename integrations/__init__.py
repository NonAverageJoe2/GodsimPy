"""
Integrations package: glue between systems and the core engine.
"""

try:
    from .engine_integrations import enable_enhanced_colonization
    _ENHANCED_COLONIZATION_AVAILABLE = True
except ImportError:
    _ENHANCED_COLONIZATION_AVAILABLE = False

try:
    from .realistic_colonization_integration import enable_realistic_colonization
    _REALISTIC_COLONIZATION_AVAILABLE = True
except ImportError:
    _REALISTIC_COLONIZATION_AVAILABLE = False

__all__ = []

if _ENHANCED_COLONIZATION_AVAILABLE:
    __all__.append("enable_enhanced_colonization")

if _REALISTIC_COLONIZATION_AVAILABLE:
    __all__.append("enable_realistic_colonization")
