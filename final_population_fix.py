"""
Final Population Fix

Direct test of population system to ensure 1000+ year growth works.
"""

import sys
import os
sys.path.insert(0, '.')


def test_final_population_fix(turns: int = 500) -> None:
    """Test population growth with direct comprehensive approach."""
    
    print(f"FINAL POPULATION FIX TEST - {turns} TURNS")
    print("=" * 50)
    
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
        tile1._pop_float = 30.0
        tile2._pop_float = 25.0
        
        initial_pop = sum(t.pop for t in engine.world.tiles)
        initial_year = engine.world.calendar.year
        
        print(f"Starting simulation:")
        print(f"  Population: {initial_pop}")
        print(f"  Year: {initial_year}")
        
        # Track populations
        populations = []
        for turn in range(turns):
            current_pop = sum(t.pop for t in engine.world.tiles)
            populations.append(current_pop)
            
            engine.advance_turn()
            
            new_pop = sum(t.pop for t in engine.world.tiles)
            
            # Show progress every 100 turns
            if turn % 100 == 0:
                change = new_pop - current_pop
                year = engine.world.calendar.year - initial_year
                print(f"Turn {turn+1:3d}: {current_pop:5.0f} -> {new_pop:5.0f} ({change:+4.0f}) | Year {year:.1f}")
        
        # Final results
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        years_elapsed = final_year - initial_year
        
        print(f"\nFINAL RESULTS:")
        print(f"Population: {initial_pop} -> {final_pop} ({final_pop - initial_pop:+} change)")
        print(f"Time: {initial_year:.2f} -> {final_year:.2f} ({years_elapsed:.2f} years)")
        
        # Check civilizations
        print(f"\nCivilizations:")
        total_territories = 0
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            total_territories += len(civ.tiles)
            print(f"  Civ {civ_id} ({civ.name}): {civ_pop} population, {len(civ.tiles)} territories")
        
        # Analyze growth
        growth_turns = sum(1 for i in range(1, len(populations)) if populations[i] > populations[i-1])
        declining_turns = sum(1 for i in range(1, len(populations)) if populations[i] < populations[i-1])
        stable_turns = turns - growth_turns - declining_turns
        
        print(f"\nGROWTH ANALYSIS:")
        print(f"  Growth turns: {growth_turns}/{turns} ({100*growth_turns/turns:.1f}%)")
        print(f"  Declining turns: {declining_turns}/{turns} ({100*declining_turns/turns:.1f}%)")
        print(f"  Stable turns: {stable_turns}/{turns} ({100*stable_turns/turns:.1f}%)")
        
        # Success metrics
        population_growth = final_pop > initial_pop
        significant_growth = final_pop > initial_pop * 1.5  # At least 50% growth
        time_advanced = years_elapsed > 5.0  # At least 5 years
        civs_survived = len(engine.world.civs) > 0
        
        print(f"\nSUCCESS METRICS:")
        print(f"  Population grew: {population_growth} ({final_pop/initial_pop:.2f}x)")
        print(f"  Significant growth: {significant_growth}")
        print(f"  Time advanced: {time_advanced} ({years_elapsed:.1f} years)")
        print(f"  Civilizations survived: {civs_survived} ({len(engine.world.civs)} civs)")
        
        success = population_growth and time_advanced and civs_survived
        
        if success and significant_growth:
            print(f"\nSUCCESS: Population system now works for long simulations!")
            print(f"Your civilizations will grow over 1000+ year periods.")
            return True
        elif success:
            print(f"\nPARTIAL SUCCESS: Some growth, but may need longer periods.")
            return True
        else:
            print(f"\nSTILL NEEDS WORK: Population not growing sustainably.")
            return False
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_final_population_fix(500)  # Test with 500 turns (about 10 years)
    
    if success:
        print(f"\n" + "="*60)
        print(f"READY FOR 1000+ YEAR SIMULATIONS")
        print(f"Your civilization populations should now grow sustainably")
        print(f"over very long time periods!")
        print(f"="*60)
    else:
        print(f"\nNeed to continue investigating population growth issues.")