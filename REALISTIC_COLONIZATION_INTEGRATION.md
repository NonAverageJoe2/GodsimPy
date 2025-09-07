# Quick Integration Guide - Realistic Colonization System

## To enable the new realistic colonization system in your existing GodsimPy simulation:

### Option 1: Simple Integration (Recommended)

Add these lines to your main simulation code after creating the engine:

```python
# Enable realistic colonization system
try:
    from integrations.realistic_colonization_integration import enable_realistic_colonization
    enable_realistic_colonization(engine, enabled=True)
    print("✓ Realistic colonization system enabled")
except ImportError:
    print("⚠ Realistic colonization system not found, using default behavior")
```

### Option 2: GUI Integration

If you're using the GUI, also add:

```python
# Add GUI monitoring panel (press 'O' to toggle)
try:
    from integrations.realistic_colonization_integration import add_gui_integration
    add_gui_integration(gui)  # your GUI instance
    print("✓ Colonization GUI panel added (press 'O' key)")
except ImportError:
    pass
```

### Option 3: Full Configuration

For advanced users who want to customize parameters:

```python
from integrations.realistic_colonization_integration import (
    enable_realistic_colonization, 
    update_colonization_config,
    get_colonization_stats
)

# Enable system
enable_realistic_colonization(engine)

# Customize for faster/more dynamic expansion
config = {
    "colonization": {
        "base_colonization_range": 4,          # Expand further
        "expansion_attempt_probability": 0.25,  # More frequent attempts
        "population_pressure_threshold": 20     # Lower threshold
    },
    "culture_spawning": {
        "spawn_interval_turns": 50,    # New cultures every 50 turns
        "base_spawn_probability": 0.3  # Higher spawn chance
    }
}

update_colonization_config(engine, config)

# Monitor progress (optional)
def print_expansion_stats():
    stats = get_colonization_stats(engine)
    print(f"Turn {stats['turn']}: {len(stats['civilization_stats'])} civilizations")
    for civ_info in stats['civilization_stats'].values():
        print(f"  {civ_info['name']}: {civ_info['tiles']} tiles")

# Call print_expansion_stats() periodically to see progress
```

## What You'll See

After enabling the system:

1. **More Realistic Expansion**: Civilizations will expand based on geography, population pressure, and resource availability rather than simple proximity
2. **Geographic Barriers**: Mountains, deserts, and oceans will naturally limit expansion
3. **Strategic Expansion**: Rivers, coasts, and fertile lands will be prioritized
4. **Dynamic Culture Spawning**: New civilizations will emerge in isolated, populated regions over time
5. **Natural Growth Patterns**: Expansion will follow realistic settlement patterns

## Files Added

The integration adds these files to your project:
- `systems/realistic_colonization.py` - Core system implementation
- `integrations/realistic_colonization_integration.py` - Integration helpers
- `balance/realistic_colonization.json` - Configuration file
- `docs/realistic_colonization.md` - Full documentation
- `examples/realistic_colonization_demo.py` - Demonstration script
- `tests/test_realistic_colonization.py` - Test suite

## Configuration File

Edit `balance/realistic_colonization.json` to customize behavior without changing code.

## No Changes to Existing Code

The system is designed to be completely non-intrusive - it enhances existing behavior without modifying your current simulation logic.