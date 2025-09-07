"""
Test Population Fixes

Quick test to verify the comprehensive population fixes work correctly.
"""

import sys
import os
sys.path.insert(0, '.')

from fixes.comprehensive_population_fix import apply_comprehensive_population_fix


def quick_test(turns: int = 200) -> None:
    """Test the fixes with a shorter simulation first."""
    
    print(f"TESTING POPULATION FIXES - {turns} TURNS")
    print("=" * 45)
    
    try:
        from engine import SimulationEngine
        
        # Create test world
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add civilizations
        civ1_id = engine.add_civ('Romans', (15, 12))
        civ2_id = engine.add_civ('Greeks', (20, 15))
        
        # Set initial populations
        engine.world.get_tile(15, 12).pop = 30
        engine.world.get_tile(20, 15).pop = 25
        
        initial_pop = sum(t.pop for t in engine.world.tiles)
        initial_year = engine.world.calendar.year
        
        print(f"Starting: {initial_pop} population, Year {initial_year}")
        
        # Apply comprehensive fixes
        apply_comprehensive_population_fix(engine)
        
        print(f"\nRunning {turns} turns...")
        
        # Run simulation with detailed tracking
        for turn in range(turns):
            pre_pop = sum(t.pop for t in engine.world.tiles)
            pre_year = engine.world.calendar.year
            
            engine.advance_turn()
            
            post_pop = sum(t.pop for t in engine.world.tiles)
            post_year = engine.world.calendar.year
            
            pop_change = post_pop - pre_pop
            year_change = post_year - pre_year
            
            # Show first 10 turns and every 50th turn
            if turn < 10 or turn % 50 == 0:
                print(f"Turn {turn+1:3d}: Pop {pre_pop:5.0f} -> {post_pop:5.0f} ({pop_change:+4.0f}) | Year {pre_year:.2f} -> {post_year:.2f} ({year_change:+.3f})")
        
        # Final results
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        years_elapsed = final_year - initial_year
        
        print(f"\nRESULTS AFTER {turns} TURNS:")
        print(f"Population: {initial_pop} -> {final_pop} ({final_pop - initial_pop:+} change)")
        print(f"Time: {initial_year:.2f} -> {final_year:.2f} ({years_elapsed:.2f} years)")
        
        # Check civilizations
        print(f"\nCivilizations:")
        total_territories = 0
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            total_territories += len(civ.tiles)
            print(f"  Civ {civ_id} ({civ.name}): {civ_pop} population, {len(civ.tiles)} territories")
        
        # Analyze success
        population_grew = final_pop > initial_pop
        time_progressed = years_elapsed > 1.0  # At least 1 year
        civs_alive = len(engine.world.civs) > 0
        
        print(f"\nANALYSIS:")
        print(f"  Population grew: {population_grew}")
        print(f"  Time progressed: {time_progressed}")
        print(f"  Civilizations survived: {civs_alive}")
        print(f"  Years per turn: {years_elapsed / turns:.4f}")
        
        if population_grew and time_progressed and civs_alive:
            print(f"\nSUCCESS: Fixes are working!")
            print(f"Ready for 1000+ year simulations.")
            return True
        else:
            print(f"\nStill has issues - need to investigate")
            return False
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def extended_test(years: int = 50) -> None:
    """Test with more years to see long-term behavior."""
    
    turns = years * 52  # 52 turns per year
    
    print(f"\nEXTENDED TEST - {years} YEARS ({turns} TURNS)")
    print("=" * 50)
    
    try:
        from engine import SimulationEngine
        
        engine = SimulationEngine(width=32, height=24, seed=42)
        civ1_id = engine.add_civ('Romans', (15, 12))
        civ2_id = engine.add_civ('Greeks', (20, 15))
        
        engine.world.get_tile(15, 12).pop = 30
        engine.world.get_tile(20, 15).pop = 25
        
        initial_pop = sum(t.pop for t in engine.world.tiles)
        initial_year = engine.world.calendar.year
        
        apply_comprehensive_population_fix(engine)
        
        print(f"Extended simulation starting...")
        
        checkpoint_interval = turns // 10  # 10 checkpoints
        
        for turn in range(turns):
            engine.advance_turn()
            
            if turn % checkpoint_interval == 0:
                current_pop = sum(t.pop for t in engine.world.tiles)
                current_year = engine.world.calendar.year
                years_passed = current_year - initial_year
                print(f"Turn {turn:5d}: {current_pop:5.0f} population, Year {years_passed:.1f}")
        
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        years_elapsed = final_year - initial_year
        
        print(f"\nEXTENDED RESULTS ({years} year target):")
        print(f"Population: {initial_pop} -> {final_pop} ({final_pop/initial_pop:.1f}x growth)")
        print(f"Time: {years_elapsed:.1f} years elapsed")
        print(f"Civs remaining: {len(engine.world.civs)}")
        
        # Calculate territories
        total_territories = sum(len(civ.tiles) for civ in engine.world.civs.values())
        print(f"Total territories: {total_territories}")
        
        success = (final_pop > initial_pop * 1.5 and 
                  years_elapsed > years * 0.8 and 
                  len(engine.world.civs) > 0)
        
        if success:
            print(f"\nEXTENDED TEST SUCCESS!")
            print(f"System is ready for your 1000+ year simulations!")
        else:
            print(f"\nExtended test shows room for improvement")
        
        return success
        
    except Exception as e:
        print(f"Extended test failed: {e}")
        return False


if __name__ == "__main__":
    # Run quick test first
    quick_success = quick_test(200)
    
    if quick_success:
        # If quick test passes, run extended test
        extended_test(50)
    else:
        print("Quick test failed - not proceeding to extended test")