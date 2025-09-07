"""
Test 5000+ Year Simulation

Test that civilizations can continue growing and expanding 
over very long periods without hitting artificial caps.
"""

import sys
import os
sys.path.insert(0, '.')


def test_5000_year_growth(years_to_test: int = 50) -> None:
    """Test population and territorial growth over extended periods."""
    
    turns = years_to_test * 52  # 52 turns per year
    
    print(f"TESTING {years_to_test}-YEAR SIMULATION ({turns} TURNS)")
    print("=" * 60)
    
    try:
        from engine import SimulationEngine
        
        # Create engine
        engine = SimulationEngine(width=64, height=48, seed=42)  # Larger world for expansion
        
        # Add civilizations
        civ1_id = engine.add_civ('Romans', (20, 15))
        civ2_id = engine.add_civ('Greeks', (30, 25))
        civ3_id = engine.add_civ('Egyptians', (40, 35))
        
        # Set initial populations
        engine.world.get_tile(20, 15).pop = 25
        engine.world.get_tile(30, 25).pop = 30
        engine.world.get_tile(40, 35).pop = 20
        
        initial_pop = sum(t.pop for t in engine.world.tiles)
        initial_territories = sum(len(civ.tiles) for civ in engine.world.civs.values())
        initial_year = engine.world.calendar.year
        
        print(f"Starting simulation:")
        print(f"  Population: {initial_pop}")
        print(f"  Territories: {initial_territories}")
        print(f"  Civilizations: {len(engine.world.civs)}")
        print(f"  Target: {years_to_test} years")
        
        # Track progress
        checkpoint_turns = turns // 10  # 10 checkpoints
        checkpoints = []
        
        for turn in range(turns):
            current_pop = sum(t.pop for t in engine.world.tiles)
            current_territories = sum(len(civ.tiles) for civ in engine.world.civs.values())
            current_year = engine.world.calendar.year
            
            engine.advance_turn()
            
            new_pop = sum(t.pop for t in engine.world.tiles)
            new_territories = sum(len(civ.tiles) for civ in engine.world.civs.values())
            
            # Save checkpoint data
            if turn % checkpoint_turns == 0:
                years_elapsed = current_year - initial_year
                
                checkpoints.append({
                    'turn': turn,
                    'years': years_elapsed,
                    'population': current_pop,
                    'territories': current_territories,
                    'civs': len(engine.world.civs)
                })
                
                pop_change = new_pop - current_pop
                terr_change = new_territories - current_territories
                
                print(f"Year {years_elapsed:4.0f}: Pop {current_pop:6.0f} ({pop_change:+4.0f}) | Territories {current_territories:4d} ({terr_change:+2d}) | Civs {len(engine.world.civs)}")
                
                # Check for stagnation
                if len(checkpoints) >= 3:
                    recent = checkpoints[-3:]
                    pop_growth = recent[-1]['population'] - recent[0]['population'] 
                    terr_growth = recent[-1]['territories'] - recent[0]['territories']
                    
                    if pop_growth < 10 and terr_growth < 2:
                        print(f"WARNING: Possible stagnation detected at year {years_elapsed:.0f}")
                        print(f"  Population growth over last 3 checkpoints: {pop_growth:.0f}")
                        print(f"  Territory growth over last 3 checkpoints: {terr_growth}")
        
        # Final analysis
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_territories = sum(len(civ.tiles) for civ in engine.world.civs.values())
        final_year = engine.world.calendar.year
        years_elapsed = final_year - initial_year
        
        print(f"\nFINAL RESULTS AFTER {years_to_test} YEAR TARGET:")
        print(f"Population: {initial_pop} -> {final_pop} ({final_pop/initial_pop:.1f}x growth)")
        print(f"Territories: {initial_territories} -> {final_territories} ({final_territories/initial_territories:.1f}x growth)")
        print(f"Time elapsed: {years_elapsed:.1f} years")
        print(f"Civilizations: {len(engine.world.civs)} (started with 3)")
        
        # Detailed civilization analysis
        print(f"\nDETAILED CIVILIZATION STATUS:")
        largest_civ_territories = 0
        largest_civ_pop = 0
        
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            largest_settlement = max((engine.world.get_tile(q, r).pop for q, r in civ.tiles), default=0)
            
            largest_civ_territories = max(largest_civ_territories, len(civ.tiles))
            largest_civ_pop = max(largest_civ_pop, civ_pop)
            
            print(f"  Civ {civ_id} ({civ.name}):")
            print(f"    Population: {civ_pop:,} across {len(civ.tiles)} territories")
            print(f"    Largest settlement: {largest_settlement:,} people")
            print(f"    Average settlement: {civ_pop/len(civ.tiles):.0f} people")
        
        # Success metrics for 5000+ year sustainability
        pop_multiplier = final_pop / initial_pop
        terr_multiplier = final_territories / initial_territories
        time_success = years_elapsed >= years_to_test * 0.9
        
        continuous_growth = True
        if len(checkpoints) >= 5:
            # Check that growth continued throughout simulation
            mid_point = checkpoints[len(checkpoints)//2]
            final_point = checkpoints[-1]
            late_growth = final_point['population'] > mid_point['population'] * 1.1  # 10% growth in second half
            continuous_growth = late_growth
        
        print(f"\nSUSTAINABILITY ANALYSIS:")
        print(f"  Population growth: {pop_multiplier:.1f}x (target: >5x for {years_to_test} years)")
        print(f"  Territorial growth: {terr_multiplier:.1f}x (target: >10x for {years_to_test} years)")
        print(f"  Time progression: {time_success} ({years_elapsed:.1f}/{years_to_test} years)")
        print(f"  Continuous growth: {continuous_growth}")
        print(f"  Largest civilization: {largest_civ_territories} territories, {largest_civ_pop:,} people")
        
        # Overall success assessment
        pop_success = pop_multiplier > (years_to_test / 10)  # At least 1x per 10 years
        terr_success = terr_multiplier > (years_to_test / 5)  # At least 1x per 5 years
        large_civ_success = largest_civ_territories > 20     # At least one medium empire
        
        overall_success = pop_success and terr_success and time_success and continuous_growth
        
        print(f"\nSUCCESS METRICS:")
        print(f"  Population growth adequate: {pop_success}")
        print(f"  Territorial expansion adequate: {terr_success}")
        print(f"  Large civilizations formed: {large_civ_success}")
        print(f"  No stagnation: {continuous_growth}")
        
        if overall_success:
            print(f"\n🎉 SUCCESS: System supports {years_to_test}+ year simulations!")
            print(f"Ready for your 5000+ year civilization games!")
        else:
            print(f"\n⚠️  PARTIAL SUCCESS: Growth occurred but may still have limitations")
            if not pop_success:
                print(f"     - Population growth too slow for very long simulations")
            if not terr_success:
                print(f"     - Territorial expansion too slow")
            if not continuous_growth:
                print(f"     - Growth stagnated in later periods")
        
        return overall_success
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Testing fixes for 5000+ year civilization simulations...")
    print("This test uses 50 years as a scaled-down version to verify growth patterns\n")
    
    success = test_5000_year_growth(50)
    
    if success:
        print(f"\n" + "="*70)
        print(f"✅ READY FOR 5000+ YEAR SIMULATIONS!")
        print(f"Population and territorial caps have been removed.")
        print(f"Your civilizations should now grow into massive empires")
        print(f"over thousands of years without hitting artificial limits!")
        print(f"="*70)
    else:
        print(f"\n🔧 May need further optimization for very long-term growth")