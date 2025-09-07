"""
Investigate Population Stagnation

Test what happens to population growth over longer periods to find
what's causing stagnation after a certain year.
"""

import sys
import os
sys.path.insert(0, '.')


def investigate_population_stagnation(max_turns: int = 2000) -> None:
    """Test population over a very long period to find stagnation point."""
    
    print(f"INVESTIGATING POPULATION STAGNATION - {max_turns} TURNS")
    print("=" * 60)
    
    try:
        from engine import SimulationEngine
        
        # Create engine
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add civilizations
        civ1_id = engine.add_civ('Romans', (15, 12))
        civ2_id = engine.add_civ('Greeks', (20, 15))
        
        # Set initial populations
        tile1 = engine.world.get_tile(15, 12)
        tile2 = engine.world.get_tile(20, 15)
        tile1.pop = 30
        tile2.pop = 25
        
        initial_pop = sum(t.pop for t in engine.world.tiles)
        initial_year = engine.world.calendar.year
        
        print(f"Starting long-term investigation:")
        print(f"  Population: {initial_pop}")
        print(f"  Year: {initial_year}")
        
        # Track detailed population history
        population_history = []
        stagnation_detected = False
        stagnation_start = None
        last_significant_change = 0
        
        for turn in range(max_turns):
            current_pop = sum(t.pop for t in engine.world.tiles)
            current_year = engine.world.calendar.year
            
            population_history.append({
                'turn': turn,
                'population': current_pop,
                'year': current_year
            })
            
            # Check for stagnation (no significant change for 200 turns)
            if turn > 200:
                recent_pops = [h['population'] for h in population_history[-200:]]
                pop_variance = max(recent_pops) - min(recent_pops)
                
                if pop_variance <= 5 and not stagnation_detected:  # Less than 5 pop change in 200 turns
                    stagnation_detected = True
                    stagnation_start = turn
                    stagnation_year = current_year - initial_year
                    print(f"\nSTAGNATION DETECTED at turn {turn} (Year {stagnation_year:.1f})")
                    print(f"  Population: {current_pop}")
                    print(f"  Recent variance: {pop_variance} people over 200 turns")
                    
                    # Print detailed state at stagnation
                    print(f"\nCivilization states at stagnation:")
                    total_territories = 0
                    for civ_id, civ in engine.world.civs.items():
                        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
                        total_territories += len(civ.tiles)
                        print(f"  Civ {civ_id} ({civ.name}): {civ_pop} population, {len(civ.tiles)} territories")
                    
                    print(f"  Total territories: {total_territories}")
                    
                    # Check a few tiles for detailed state
                    print(f"\nSample tile states:")
                    sample_tiles = [t for t in engine.world.tiles if t.owner is not None][:5]
                    for tile in sample_tiles:
                        civ = engine.world.civs[tile.owner]
                        print(f"    Tile ({tile.q},{tile.r}): pop={tile.pop}, _pop_float={tile._pop_float:.2f}, owner={civ.name}")
                    
                    break
            
            # Advance simulation
            engine.advance_turn()
            
            new_pop = sum(t.pop for t in engine.world.tiles)
            change = new_pop - current_pop
            
            if abs(change) > 0:
                last_significant_change = turn
            
            # Report progress every 200 turns or on significant changes
            if turn % 200 == 0 or abs(change) > 10:
                years_elapsed = current_year - initial_year
                print(f"Turn {turn:4d}: {current_pop:5.0f} -> {new_pop:5.0f} ({change:+4.0f}) | Year {years_elapsed:.1f}")
        
        # Final analysis
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        years_elapsed = final_year - initial_year
        
        print(f"\nFINAL ANALYSIS:")
        print(f"Population: {initial_pop} -> {final_pop} ({final_pop - initial_pop:+} change)")
        print(f"Time: {years_elapsed:.2f} years elapsed")
        print(f"Last significant change: Turn {last_significant_change}")
        
        if stagnation_detected:
            stagnation_year = population_history[stagnation_start]['year'] - initial_year
            stagnation_pop = population_history[stagnation_start]['population']
            
            print(f"\nSTAGNATION ANALYSIS:")
            print(f"  Stagnation started: Turn {stagnation_start}, Year {stagnation_year:.1f}")
            print(f"  Population at stagnation: {stagnation_pop}")
            print(f"  Growth period: {stagnation_year:.1f} years")
            print(f"  Growth multiplier: {stagnation_pop/initial_pop:.2f}x")
            
            # Look for patterns
            if stagnation_pop > 500:
                print(f"  Pattern: High population stagnation (may have hit carrying capacity)")
            elif years_elapsed > 10:
                print(f"  Pattern: Time-based stagnation (may be age/tech related)")
            else:
                print(f"  Pattern: Early stagnation (may be resource/food constraint)")
            
            return stagnation_year, stagnation_pop
        else:
            print(f"\nNo stagnation detected in {max_turns} turns")
            return None, final_pop
        
    except Exception as e:
        print(f"Investigation failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def diagnose_stagnation_cause(stagnation_year, stagnation_pop):
    """Try to diagnose what's causing the stagnation."""
    
    print(f"\nDIAGNOSING STAGNATION CAUSE")
    print("=" * 40)
    
    # Look for likely causes based on patterns
    likely_causes = []
    
    if stagnation_pop > 1000:
        likely_causes.append("Carrying capacity limit reached")
        likely_causes.append("Food production insufficient for large populations")
    
    if stagnation_year > 20:
        likely_causes.append("Technology advancement affecting growth")
        likely_causes.append("Complex civilization interactions")
    
    if stagnation_year < 5:
        likely_causes.append("Early resource constraints")
        likely_causes.append("Workforce balance issues")
    
    print(f"Likely causes:")
    for i, cause in enumerate(likely_causes, 1):
        print(f"  {i}. {cause}")
    
    print(f"\nRecommended investigations:")
    print(f"  - Check if POP_MAX constant is being hit")
    print(f"  - Verify carrying capacity calculations at high populations") 
    print(f"  - Test if technology system affects late-game growth")
    print(f"  - Check for hidden population caps in workforce system")


if __name__ == "__main__":
    stagnation_year, stagnation_pop = investigate_population_stagnation(2000)
    
    if stagnation_year is not None:
        diagnose_stagnation_cause(stagnation_year, stagnation_pop)
        print(f"\nFound stagnation issue - need to investigate specific cause")
    else:
        print(f"\nNo stagnation found - population continues growing")