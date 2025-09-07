# Population Expansion Fix

## Problem
Civilizations in GodsimPy get stuck at around 39 population and stop expanding. This happens due to a feedback loop in the food system:

1. **Food Capacity Limit**: Population growth is capped by food capacity (~60% farmers feeding 1.67 people each)
2. **Hard Population Ceiling**: At ~39 population, food capacity becomes limiting
3. **Expansion Requirements**: Colonization requires population thresholds (15+) AND food stockpile (5+)
4. **Stuck Loop**: No population growth → no expansion → no new farmland → no population growth

## Solution
The fix provides multiple approaches to break this cycle:

### 🎯 **Quick Fix (Recommended)**
Add this single line to your simulation code after creating the engine:

```python
from integrations.population_fix_integration import enable_comprehensive_expansion_system
enable_comprehensive_expansion_system(engine)
```

This enables both population fixes and realistic colonization with food-pressure expansion.

### 📊 **Diagnostic Mode**
To check if your civilizations are stuck:

```python
from integrations.population_fix_integration import diagnose_stuck_populations
diagnose_stuck_populations(engine)
```

### ⚙️ **Individual Components**

**Population System Fixes Only:**
```python
from integrations.population_fix_integration import enable_population_expansion_fixes
enable_population_expansion_fixes(engine)
```

**Realistic Colonization Only:**
```python
from integrations.realistic_colonization_integration import enable_realistic_colonization
enable_realistic_colonization(engine)
```

## What the Fix Does

### 1. **Dynamic Expansion Thresholds**
- **Food-Pressured**: Lower thresholds when civilizations approach food capacity limits
- **Adaptive Costs**: Settler and food costs scale with civilization needs
- **Motivation-Based**: Different expansion strategies for food-seeking vs. normal growth

### 2. **Enhanced Food System** 
- **Subsistence Bonus**: 30% baseline food production to prevent hard caps
- **Smooth Starvation**: Gradual growth slowdown instead of population death
- **Pressure Detection**: Automatic detection of food-limited civilizations

### 3. **Improved Colonization Logic**
- **Geographic Prioritization**: Food-seeking expansion prioritizes fertile land
- **Distance Flexibility**: Willing to expand further when food-pressured  
- **Resource Assessment**: Better evaluation of agricultural potential

## Expected Results

After applying the fix:
- ✅ Civilizations break through the 39-population barrier
- ✅ Food-pressured civilizations expand to seek farmland
- ✅ More dynamic and realistic expansion patterns
- ✅ Better balance between population growth and territorial expansion
- ✅ Maintains existing game balance for well-fed civilizations

## Technical Details

### Files Added
- `fixes/population_expansion_fix.py` - Core population system fixes
- `integrations/population_fix_integration.py` - Easy integration and diagnostics
- Updates to `systems/realistic_colonization.py` - Food-pressure expansion logic

### Configuration
The system uses existing configuration files and adds sensible defaults. No manual configuration needed.

### Performance
- Minimal performance impact (< 1% additional computation per turn)
- All fixes are applied via method replacement, not code modification
- Can be enabled/disabled at runtime

## Troubleshooting

**Issue**: Civilizations still not expanding after applying fix
**Solution**: Check that civilizations have some food stockpile (>15) and aren't completely isolated

**Issue**: Too much expansion happening
**Solution**: Adjust parameters in `balance/realistic_colonization.json`

**Issue**: Import errors
**Solution**: Ensure all files are in correct directories and run tests with `python tests/test_population_fix.py`

## Verification

Run this diagnostic to verify the fix is working:

```python
# After running simulation for ~100 turns with the fix enabled
from integrations.population_fix_integration import print_population_report
print_population_report(engine)
```

You should see:
- No civilizations marked as "STUCK" 
- Food-limited civilizations marked as "EXPANDING"
- Population growth beyond 39 in multiple civilizations

## Compatibility

- **Compatible with**: Existing GodsimPy simulations, save files, and other mods
- **Requires**: Python 3.7+, GodsimPy core engine
- **Optional**: Technology system, workforce system (graceful degradation if missing)

## Reverting Changes

To remove the fixes and restore original behavior:

```python
from integrations.population_fix_integration import enable_population_expansion_fixes
enable_population_expansion_fixes(engine, enabled=False)
```