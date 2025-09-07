#!/usr/bin/env python3
"""
Population System Demonstration

This script demonstrates the age-based population system with births, deaths, and aging
to show that populations do change over time in realistic ways.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def create_test_simulation():
    """Create a test simulation with the population system enabled."""
    print("Creating test simulation...")
    
    try:
        # Create a basic engine setup
        from engine import SimulationEngine
        from worldgen import build_world
        
        # Generate small world for testing
        world = build_world(width_hex=32, height_hex=24, seed=42)
        engine = SimulationEngine(world)
        
        # Ensure we have some initial civilizations
        if len(engine.world.civs) == 0:
            # Add test civilizations
            engine.spawn_civ((15, 12))
            engine.spawn_civ((20, 15))
        
        return engine
        
    except Exception as e:
        print(f"Error creating simulation: {e}")
        return None

def demonstrate_population_system():
    """Demonstrate that the population system works with births, deaths, and aging."""
    engine = create_test_simulation()
    if not engine:
        return
    
    print("\n" + "="*60)
    print("POPULATION SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Enable the comprehensive population system
    try:
        from integrations.population_system_integration import setup_comprehensive_population_system
        setup_comprehensive_population_system(engine)
    except Exception as e:
        print(f"Warning: Could not enable population system integration: {e}")
        print("Continuing with existing system...")
    
    print("\nInitial State:")
    print("-" * 20)
    
    # Record initial populations
    initial_data = {}
    total_initial = 0
    
    for civ_id, civ in engine.world.civs.items():
        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        initial_data[civ_id] = civ_pop
        total_initial += civ_pop
        print(f"Civ {civ_id} ({civ.name}): {civ_pop} population")
    
    print(f"Total Population: {total_initial}")
    
    # Show population parameters
    try:
        from sim.cohorts import FERTILITY_PER_FEMALE_PER_YEAR, MORTALITY_PER_YEAR
        print(f"\nPopulation Parameters:")
        print(f"  Birth rate: {FERTILITY_PER_FEMALE_PER_YEAR:.3f} per female per year")
        print(f"  Death rates by age:")
        for age, rate in MORTALITY_PER_YEAR.items():
            print(f"    {age}: {rate*100:.1f}% per year")
    except:
        print("Population parameters not available")
    
    # Run simulation and track changes
    print(f"\nRunning simulation for 100 turns...")
    print("Turn | Total Pop | Net Change | Births | Deaths | Notes")
    print("-" * 65)
    
    turn_data = []
    
    for turn in range(100):
        turn_start = sum(t.pop for t in engine.world.tiles)
        
        # Step simulation
        engine.step()
        
        turn_end = sum(t.pop for t in engine.world.tiles)
        net_change = turn_end - turn_start
        
        # Record data
        turn_data.append({
            'turn': turn,
            'start_pop': turn_start,
            'end_pop': turn_end,
            'change': net_change
        })
        
        # Print every 10 turns
        if turn % 10 == 0 or turn < 5:
            # Estimate births and deaths (simplified)
            if hasattr(engine, 'cohort_state'):
                notes = "Cohort system active"
            else:
                notes = "Simple growth"
                
            print(f"{turn:4d} | {turn_end:9.0f} | {net_change:10.1f} | {'':6} | {'':6} | {notes}")
    
    # Final analysis
    print("\n" + "="*60)
    print("RESULTS ANALYSIS")
    print("="*60)
    
    final_total = sum(t.pop for t in engine.world.tiles)
    net_change = final_total - total_initial
    
    print(f"Initial Population: {total_initial}")
    print(f"Final Population:   {final_total}")
    print(f"Net Change:         {net_change:+.1f}")
    print(f"Growth Rate:        {(net_change/total_initial)*100:.2f}% over 100 turns")
    
    # Analyze population changes
    positive_changes = [d['change'] for d in turn_data if d['change'] > 0]
    negative_changes = [d['change'] for d in turn_data if d['change'] < 0]
    zero_changes = [d['change'] for d in turn_data if d['change'] == 0]
    
    print(f"\nTurn Analysis:")
    print(f"  Population increased: {len(positive_changes)} turns")
    print(f"  Population decreased: {len(negative_changes)} turns") 
    print(f"  Population unchanged: {len(zero_changes)} turns")
    
    if positive_changes:
        print(f"  Average growth: +{sum(positive_changes)/len(positive_changes):.2f}")
    if negative_changes:
        print(f"  Average decline: {sum(negative_changes)/len(negative_changes):.2f}")
    
    # Check for age-based population
    print(f"\nPopulation System Status:")
    if hasattr(engine, 'cohort_state'):
        print("  ✅ Age-based population system is ACTIVE")
        print("     - Births occur based on fertile female population")
        print("     - Deaths occur based on age-specific mortality rates")
        print("     - Population ages over time through cohorts")
        print("     - Workforce calculation uses working-age population")
    else:
        print("  ⚠️  Simple logistic growth system")
        print("     - Population grows towards carrying capacity")
        print("     - No births/deaths, no aging, no demographic structure")
    
    # Recommendations
    print(f"\nWhat This Means:")
    if net_change > 0:
        print("  ✅ Populations are growing over time")
    elif net_change < 0:
        print("  📉 Populations are declining (deaths > births)")
    else:
        print("  ⚖️  Populations are at equilibrium (births ≈ deaths)")
    
    print(f"\nIf you want more dramatic population changes:")
    print(f"  - Increase fertility rate in balance/population_system.json")
    print(f"  - Decrease mortality rates for faster growth")
    print(f"  - Run simulation for more turns (population changes are gradual)")
    print(f"  - Add more civilizations for larger overall changes")
    
    return turn_data

def quick_population_check():
    """Quick check to see if population system is working."""
    print("QUICK POPULATION SYSTEM CHECK")
    print("=" * 40)
    
    # Check system availability
    try:
        from sim.cohorts import step_cohorts, FERTILITY_PER_FEMALE_PER_YEAR
        print("✅ Age-based population system is available")
        print(f"   Birth rate: {FERTILITY_PER_FEMALE_PER_YEAR:.3f} per female per year")
    except ImportError:
        print("❌ Age-based population system not found")
        return
    
    # Check integration
    try:
        from fixes.engine_integration_complete import apply_all_fixes
        print("✅ Population integration is available")
    except ImportError:
        print("❌ Population integration not found")
        return
    
    # Check if it's enabled by default
    with open('main.py', 'r') as f:
        content = f.read()
        if 'apply_all_fixes' in content:
            print("✅ Population system should be active in GUI")
        else:
            print("⚠️  Population system may not be active by default")
    
    print("\nTo manually enable the population system:")
    print("  from integrations.population_system_integration import setup_comprehensive_population_system")
    print("  setup_comprehensive_population_system(engine)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_population_check()
    else:
        print("Population System Demo")
        print("=" * 30)
        print("Choose an option:")
        print("1. Quick system check")
        print("2. Full demonstration (100 turns)")
        print("3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            quick_population_check()
        elif choice == "2":
            demonstrate_population_system()
        else:
            print("Goodbye!")