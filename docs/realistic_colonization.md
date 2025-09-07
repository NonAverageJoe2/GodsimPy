# Realistic Colonization and Culture Spawning System

This system enhances GodsimPy with more realistic civilization expansion patterns and dynamic culture emergence over time.

## Features

### 🏞️ Realistic Colonization
- **Geographic Barriers**: Mountains, deserts, and oceans create natural expansion barriers
- **Distance Decay**: Colonization likelihood decreases with distance from population centers
- **Population Pressure**: Expansion driven by population growth and resource availability
- **Strategic Locations**: Bonus for rivers, coasts, fertile lands, and mountain passes
- **Resource Assessment**: Considers food and production yields of target territories

### 🌍 Dynamic Culture Spawning
- **Isolated Regions**: New cultures emerge in areas distant from existing civilizations
- **Population Threshold**: Requires sufficient local population to sustain new cultures
- **Cultural Diversity**: Generates unique names and linguistic styles based on geography
- **Timed Emergence**: Cultures spawn at realistic intervals throughout the simulation

### ⚙️ Configurable Parameters
- **JSON Configuration**: Easy tweaking of all system parameters via `balance/realistic_colonization.json`
- **Runtime Updates**: Modify behavior during simulation without restarts  
- **Terrain Modifiers**: Customize expansion difficulty for different biomes
- **Strategic Bonuses**: Define value multipliers for special geographic features

## Installation

1. Copy the system files to your GodsimPy directory:
   - `systems/realistic_colonization.py`
   - `integrations/realistic_colonization_integration.py`
   - `balance/realistic_colonization.json`

2. Enable in your simulation:

```python
from integrations.realistic_colonization_integration import enable_realistic_colonization

# In your main simulation loop
engine = SimulationEngine(world)
enable_realistic_colonization(engine, enabled=True)
```

## Usage

### Basic Integration

```python
import sys
sys.path.append('path/to/godofpy')

from engine import SimulationEngine
from worldgen import build_world
from integrations.realistic_colonization_integration import enable_realistic_colonization

# Create world and engine
world = build_world(width_hex=64, height_hex=48, seed=12345)
engine = SimulationEngine(world)

# Enable realistic colonization
enable_realistic_colonization(engine)

# Run simulation - colonization will happen automatically
for turn in range(1000):
    engine.step()
```

### Monitoring Progress

```python
from integrations.realistic_colonization_integration import get_colonization_stats

# Get detailed statistics
stats = get_colonization_stats(engine)
print(f"Active civilizations: {len(stats['civilization_stats'])}")
print(f"Culture spawn candidates: {stats['culture_spawn_candidates']}")

# Per-civilization details
for civ_id, civ_info in stats['civilization_stats'].items():
    print(f"{civ_info['name']}: {civ_info['tiles']} tiles, {civ_info['potential_targets']} targets")
```

### Runtime Configuration

```python
from integrations.realistic_colonization_integration import update_colonization_config

# Make expansion more aggressive
config_updates = {
    "colonization": {
        "base_colonization_range": 5,
        "expansion_attempt_probability": 0.3
    },
    "culture_spawning": {
        "spawn_interval_turns": 25,
        "base_spawn_probability": 0.4
    }
}

update_colonization_config(engine, config_updates)
```

### GUI Integration

```python
from integrations.realistic_colonization_integration import add_gui_integration

# Add to existing GUI
add_gui_integration(gui_instance)

# Press 'O' key to toggle colonization statistics panel
```

## Configuration Reference

### Colonization Parameters
- `base_colonization_range`: Base distance civilizations can expand (default: 3)
- `max_colonization_range`: Maximum expansion range (default: 8)  
- `distance_decay_factor`: How quickly expansion probability decreases with distance (default: 0.7)
- `population_pressure_threshold`: Population needed to drive expansion (default: 25)
- `settler_population_cost`: Population transferred to new colonies (default: 8)
- `expansion_attempt_probability`: Base probability of expansion per turn (default: 0.15)

### Terrain Modifiers
- `plains`: 1.0 (easiest expansion)
- `grassland`: 0.9  
- `forest`: 0.8
- `hills`: 0.7
- `tundra`: 0.5
- `swamp`: 0.4
- `desert`: 0.3
- `mountain`: 0.1 (very difficult)
- `ocean`: 0.0 (impossible)

### Strategic Bonuses
- `river_access`: +0.3 (rivers provide trade and water)
- `coastal_access`: +0.2 (ocean access for trade and fishing)
- `fertile_land`: +0.25 (high agricultural potential)
- `mountain_pass`: +0.15 (strategic control points)
- `resource_deposits`: +0.4 (valuable minerals, etc.)

### Culture Spawning
- `spawn_interval_turns`: Turns between spawn attempts (default: 100)
- `isolation_threshold_hexes`: Distance from existing civs needed (default: 5)
- `min_spawn_population`: Population threshold for spawning (default: 15)
- `base_spawn_probability`: Chance per candidate region (default: 0.15)

## Algorithm Details

### Colonization Process

1. **Source Selection**: For each civilization, identify tiles with sufficient population pressure
2. **Target Scoring**: Evaluate nearby unowned tiles based on:
   - Distance decay factor
   - Terrain expansion difficulty  
   - Resource value (food + production)
   - Strategic location bonuses
   - Population pressure from source
3. **Weighted Selection**: Choose target probabilistically based on scores
4. **Population Transfer**: Move settlers to establish new colony

### Culture Spawning Process

1. **Candidate Identification**: Find unowned, populated regions isolated from existing civilizations
2. **Isolation Check**: Ensure minimum distance from all existing civilizations
3. **Scoring**: Rate candidates by population size, resources, and isolation distance
4. **Probabilistic Spawn**: Roll for culture emergence based on configuration
5. **Culture Generation**: Create unique civilization with region-appropriate linguistic style

### Geographic Realism

- **Natural Barriers**: Mountains and deserts significantly impede expansion
- **Water Bodies**: Rivers provide bonuses, oceans block land expansion
- **Climate Zones**: Different biomes have realistic expansion difficulties
- **Strategic Locations**: Bonus for controlling trade routes and natural resources

## Examples

See `examples/realistic_colonization_demo.py` for a complete working demonstration.

## Testing

Run the test suite to verify functionality:

```bash
cd path/to/godofpy
python -m pytest tests/test_realistic_colonization.py -v
```

Or run individual tests:

```bash
python tests/test_realistic_colonization.py
```

## Troubleshooting

### Common Issues

1. **No expansion happening**: Check population thresholds and food availability
2. **Too much expansion**: Reduce `expansion_attempt_probability` or increase `settler_population_cost`  
3. **No culture spawning**: Verify isolated regions exist and population thresholds are met
4. **Configuration not loading**: Check JSON file format and file path

### Debug Output

Enable debug output by setting log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Notes

- System adds minimal overhead to simulation step
- Most expensive operation is target scoring for large civilizations
- Consider reducing `max_colonization_range` for performance on large maps

## Compatibility

- **Required**: GodsimPy core engine, worldgen module
- **Optional**: Resource system (yields_for function), GUI system
- **Python**: 3.7+ (uses dataclasses and typing annotations)

## Future Enhancements

Planned features for future versions:
- Naval expansion and colonization
- Cultural influence and conversion mechanics  
- Trade route establishment during expansion
- Diplomatic considerations in colonization
- Climate change effects on habitability
- Advanced migration patterns and refugee flows