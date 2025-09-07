"""
Population Debug System

Adds comprehensive debug output to track population changes, births, deaths,
aging, time progression, and colonization to identify why populations aren't changing.
"""

import sys
import os
from typing import Any, Dict, List

def add_population_debug_prints(engine: Any) -> None:
    """Add debug prints to population system to track all changes."""
    
    print("🔧 ADDING POPULATION DEBUG SYSTEM")
    print("=" * 50)
    
    # First, let's check what population system is actually being used
    if hasattr(engine, 'cohort_state'):
        print("✅ Cohort state found - using age-based population")
        add_cohort_debug_prints(engine)
    else:
        print("⚠️  No cohort state - checking for simple population system")
        add_simple_population_debug_prints(engine)
    
    # Add time tracking
    add_time_debug_prints(engine)
    
    # Add colonization debug
    add_colonization_debug_prints(engine)
    
    print("🔧 Debug system installed - watch console for detailed output")


def add_cohort_debug_prints(engine: Any) -> None:
    """Add debug prints to the cohort-based population system."""
    
    # Store original step method
    if not hasattr(engine, '_original_step_method'):
        engine._original_step_method = engine.step
        engine._debug_turn_counter = 0
        engine._debug_population_history = []
    
    def debug_step(dt: float = 1.0 / 52.0):
        """Step with comprehensive population debugging."""
        engine._debug_turn_counter += 1
        turn = engine._debug_turn_counter
        
        # Record pre-step state
        pre_step_data = {}
        total_pre_pop = 0
        
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            pre_step_data[civ_id] = {
                'population': civ_pop,
                'tiles': len(civ.tiles),
                'food': getattr(civ, 'stock_food', 0)
            }
            total_pre_pop += civ_pop
        
        # Print detailed info every 10 turns, summary every turn
        if turn % 10 == 0 or turn <= 5:
            print(f"\n📊 TURN {turn} - POPULATION DEBUG")
            print("-" * 40)
            print(f"Time step (dt): {dt:.6f} years ({dt*365.25:.1f} days)")
            print(f"Game time: Year {engine.world.calendar.year}, Turn {engine.world.turn}")
            
            for civ_id, data in pre_step_data.items():
                civ = engine.world.civs[civ_id]
                print(f"Civ {civ_id} ({civ.name}):")
                print(f"  Population: {data['population']}")
                print(f"  Territories: {data['tiles']}")
                print(f"  Food Stock: {data['food']}")
                
                # Check cohort breakdown if available
                if hasattr(engine, 'cohort_state'):
                    try:
                        cohort_totals = {}
                        for key in ['c0_4', 'c5_14', 'c15_39', 'c40_64', 'c65p']:
                            if hasattr(engine.cohort_state, 'cohort_maps') and key in engine.cohort_state.cohort_maps:
                                # Sum cohorts for this civ's tiles
                                civ_total = 0
                                for q, r in civ.tiles:
                                    if engine.world.in_bounds(q, r):
                                        civ_total += float(engine.cohort_state.cohort_maps[key][r, q])
                                cohort_totals[key] = civ_total
                        
                        if cohort_totals:
                            print(f"  Age breakdown: {cohort_totals}")
                            
                            # Calculate reproduction potential
                            fertile_females = cohort_totals.get('c15_39', 0) * 0.5
                            from sim.cohorts import FERTILITY_PER_FEMALE_PER_YEAR
                            birth_potential = fertile_females * float(FERTILITY_PER_FEMALE_PER_YEAR) * dt
                            print(f"  Birth potential this turn: {birth_potential:.3f}")
                            
                            # Calculate death risk
                            from sim.cohorts import MORTALITY_PER_YEAR
                            death_risk = 0
                            for age_key, mortality in MORTALITY_PER_YEAR.items():
                                if age_key in cohort_totals:
                                    death_risk += cohort_totals[age_key] * float(mortality) * dt
                            print(f"  Death risk this turn: {death_risk:.3f}")
                            
                    except Exception as e:
                        print(f"  Cohort analysis failed: {e}")
        
        # Call original step
        result = engine._original_step_method(dt)
        
        # Record post-step state
        post_step_data = {}
        total_post_pop = 0
        
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            post_step_data[civ_id] = civ_pop
            total_post_pop += civ_pop
        
        # Calculate and report changes
        total_change = total_post_pop - total_pre_pop
        
        if turn % 10 == 0 or turn <= 5 or abs(total_change) > 0.1:
            print(f"\n📈 TURN {turn} CHANGES:")
            for civ_id in pre_step_data:
                if civ_id in post_step_data:
                    change = post_step_data[civ_id] - pre_step_data[civ_id]['population']
                    if abs(change) > 0.01:
                        print(f"  Civ {civ_id}: {pre_step_data[civ_id]['population']:.1f} -> {post_step_data[civ_id]:.1f} ({change:+.2f})")
            
            print(f"TOTAL POPULATION: {total_pre_pop:.1f} -> {total_post_pop:.1f} ({total_change:+.2f})")
        
        # Store history
        engine._debug_population_history.append({
            'turn': turn,
            'total_population': total_post_pop,
            'change': total_change,
            'year': engine.world.calendar.year
        })
        
        # Periodic summary
        if turn % 52 == 0:  # Every year
            print(f"\n🗓️  YEARLY SUMMARY - Year {engine.world.calendar.year}")
            print("-" * 50)
            year_start = max(0, len(engine._debug_population_history) - 52)
            year_data = engine._debug_population_history[year_start:]
            
            total_change_year = sum(d['change'] for d in year_data)
            print(f"Population change this year: {total_change_year:+.1f}")
            print(f"Current total population: {total_post_pop:.1f}")
            
            # Report civilization expansions
            expansions_this_year = 0
            for civ_id, civ in engine.world.civs.items():
                tiles_now = len(civ.tiles)
                # This is approximate - we'd need to track tile history for exact count
                if tiles_now > 1:
                    print(f"  Civ {civ_id} ({civ.name}): {tiles_now} territories")
                    if tiles_now > 1:
                        expansions_this_year += 1
            
            print(f"Civilizations with multiple territories: {expansions_this_year}")
        
        return result
    
    # Replace the step method
    engine.step = debug_step
    print("✅ Cohort population debug system installed")


def add_simple_population_debug_prints(engine: Any) -> None:
    """Add debug prints to simple logistic growth population system."""
    
    # Check if engine has population advancement method
    if hasattr(engine, '_advance_population_with_tech'):
        original_advance = engine._advance_population_with_tech
        
        def debug_advance_population(dt: float = 1.0 / 52.0):
            print(f"\n🧮 POPULATION ADVANCEMENT (Simple Growth)")
            print(f"Time step: {dt:.6f} years")
            
            # Track population before/after
            pre_pops = {}
            for t in engine.world.tiles:
                if t.owner is not None:
                    if t.owner not in pre_pops:
                        pre_pops[t.owner] = 0
                    pre_pops[t.owner] += t.pop
            
            result = original_advance(dt)
            
            # Track population after
            post_pops = {}
            for t in engine.world.tiles:
                if t.owner is not None:
                    if t.owner not in post_pops:
                        post_pops[t.owner] = 0
                    post_pops[t.owner] += t.pop
            
            # Report changes
            print("Population changes:")
            for civ_id in set(list(pre_pops.keys()) + list(post_pops.keys())):
                pre = pre_pops.get(civ_id, 0)
                post = post_pops.get(civ_id, 0)
                change = post - pre
                if abs(change) > 0.01:
                    print(f"  Civ {civ_id}: {pre:.1f} -> {post:.1f} ({change:+.2f})")
            
            return result
        
        engine._advance_population_with_tech = debug_advance_population
        print("✅ Simple population debug system installed")
    else:
        print("⚠️  No population advancement method found")


def add_time_debug_prints(engine: Any) -> None:
    """Add debug prints to time progression system."""
    
    # Store original advance_turn if not already stored
    if not hasattr(engine, '_original_advance_turn'):
        engine._original_advance_turn = engine.advance_turn
        engine._debug_time_history = []
    
    def debug_advance_turn(dt: float = 1.0 / 52.0):
        """Advance turn with time debugging."""
        
        pre_turn = engine.world.turn
        pre_year = engine.world.calendar.year
        pre_month = engine.world.calendar.month
        pre_day = engine.world.calendar.day
        
        result = engine._original_advance_turn(dt)
        
        post_turn = engine.world.turn
        post_year = engine.world.calendar.year
        post_month = engine.world.calendar.month
        post_day = engine.world.calendar.day
        
        # Log time progression
        engine._debug_time_history.append({
            'turn': post_turn,
            'year': post_year,
            'month': post_month,
            'day': post_day,
            'dt': dt
        })
        
        # Print time info periodically
        if post_turn % 52 == 0 or post_turn <= 10:
            print(f"\n⏰ TIME PROGRESSION - Turn {post_turn}")
            print(f"Date: Year {post_year}, Month {post_month}, Day {post_day}")
            print(f"Time step: {dt:.6f} years ({dt*365.25:.1f} days)")
            print(f"Years per turn: {dt:.6f}")
            print(f"Turns per year: {1/dt:.1f}")
        
        return result
    
    engine.advance_turn = debug_advance_turn
    print("✅ Time progression debug system installed")


def add_colonization_debug_prints(engine: Any) -> None:
    """Add debug prints to colonization system."""
    
    # Check for colonization method
    if hasattr(engine, '_colonization_pass_with_tech'):
        original_colonization = engine._colonization_pass_with_tech
        
        def debug_colonization():
            print(f"\n🏘️  COLONIZATION PASS - Turn {engine.world.turn}")
            
            # Track territories before
            pre_territories = {}
            for civ_id, civ in engine.world.civs.items():
                pre_territories[civ_id] = len(civ.tiles)
            
            result = original_colonization()
            
            # Track territories after
            post_territories = {}
            for civ_id, civ in engine.world.civs.items():
                post_territories[civ_id] = len(civ.tiles)
            
            # Report expansions
            expansions = 0
            for civ_id in pre_territories:
                if civ_id in post_territories:
                    change = post_territories[civ_id] - pre_territories[civ_id]
                    if change > 0:
                        civ = engine.world.civs[civ_id]
                        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
                        print(f"  🏛️  Civ {civ_id} ({civ.name}) expanded: {pre_territories[civ_id]} -> {post_territories[civ_id]} territories (pop: {civ_pop:.1f}, food: {getattr(civ, 'stock_food', 0)})")
                        expansions += 1
            
            if expansions == 0:
                print("  No expansions this turn")
                # Show why no expansions
                for civ_id, civ in engine.world.civs.items():
                    civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
                    max_tile_pop = max((engine.world.get_tile(q, r).pop for q, r in civ.tiles), default=0)
                    print(f"    Civ {civ_id}: Pop {civ_pop:.1f} (max tile {max_tile_pop:.1f}), Food {getattr(civ, 'stock_food', 0)}, Tiles {len(civ.tiles)}")
            
            return result
        
        engine._colonization_pass_with_tech = debug_colonization
        print("✅ Colonization debug system installed")
    else:
        print("⚠️  No colonization method found")


def print_debug_summary(engine: Any, turns_run: int = 0) -> None:
    """Print a summary of debug information collected."""
    
    print(f"\n🔍 DEBUG SUMMARY AFTER {turns_run} TURNS")
    print("=" * 60)
    
    # Population history
    if hasattr(engine, '_debug_population_history') and engine._debug_population_history:
        history = engine._debug_population_history
        
        print("📈 POPULATION TRENDS:")
        print(f"  Total turns recorded: {len(history)}")
        
        if len(history) >= 2:
            start_pop = history[0]['total_population']
            end_pop = history[-1]['total_population']
            total_change = end_pop - start_pop
            
            print(f"  Starting population: {start_pop:.1f}")
            print(f"  Current population: {end_pop:.1f}")
            print(f"  Total change: {total_change:+.1f}")
            
            if len(history) > 52:  # More than a year
                years_elapsed = (history[-1]['turn'] - history[0]['turn']) / 52.0
                growth_rate = (total_change / start_pop) * 100 / years_elapsed if start_pop > 0 else 0
                print(f"  Growth rate: {growth_rate:.2f}% per year")
            
            # Find periods of change
            significant_changes = [h for h in history if abs(h['change']) > 0.5]
            print(f"  Turns with significant change (>0.5): {len(significant_changes)}")
        
        print()
    
    # Current state
    print("🏛️  CURRENT CIVILIZATION STATE:")
    total_pop = 0
    total_tiles = 0
    
    for civ_id, civ in engine.world.civs.items():
        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        total_pop += civ_pop
        total_tiles += len(civ.tiles)
        
        print(f"  Civ {civ_id} ({getattr(civ, 'name', 'Unknown')}):")
        print(f"    Population: {civ_pop:.1f}")
        print(f"    Territories: {len(civ.tiles)}")
        print(f"    Food Stock: {getattr(civ, 'stock_food', 0)}")
        
        if len(civ.tiles) > 0:
            max_tile_pop = max(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            avg_tile_pop = civ_pop / len(civ.tiles)
            print(f"    Largest settlement: {max_tile_pop:.1f}")
            print(f"    Average settlement: {avg_tile_pop:.1f}")
    
    print(f"\nTOTAL WORLD: {total_pop:.1f} population across {total_tiles} territories")
    print(f"Game time: Year {engine.world.calendar.year}")


def run_debug_simulation(turns: int = 100) -> None:
    """Run a simulation with full debug output."""
    
    print("🚀 STARTING DEBUG SIMULATION")
    print("=" * 50)
    
    try:
        # Create engine
        from engine import SimulationEngine
        from worldgen import build_world
        
        world = build_world(width_hex=48, height_hex=36, seed=12345)
        engine = SimulationEngine(world)
        
        # Add some civs if none exist
        if len(engine.world.civs) == 0:
            engine.spawn_civ((20, 15))
            engine.spawn_civ((30, 20))
            engine.spawn_civ((25, 10))
        
        # Enable all fixes
        try:
            from fixes.engine_integration_complete import apply_all_fixes
            apply_all_fixes(engine)
            print("✅ Applied all fixes (including cohort system)")
        except Exception as e:
            print(f"⚠️  Could not apply fixes: {e}")
        
        # Install debug system
        add_population_debug_prints(engine)
        
        print(f"\n🎮 RUNNING {turns} TURNS...")
        print("Watch for population changes, births, deaths, and expansions")
        print("-" * 60)
        
        # Run simulation
        for i in range(turns):
            engine.step()
        
        # Final summary
        print_debug_summary(engine, turns)
        
    except Exception as e:
        print(f"❌ Debug simulation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Population Debug System")
    print("=" * 30)
    print()
    print("This will run a simulation with extensive debug output")
    print("to identify why populations aren't changing as expected.")
    print()
    
    try:
        turns = int(input("How many turns to run? (default 100): ") or "100")
    except ValueError:
        turns = 100
    
    run_debug_simulation(turns)