"""
Population System Diagnostic Tool

This tool checks if the age-based population system is working correctly
and diagnoses why populations might appear static.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import Dict, Any, Tuple


def check_cohort_system_integration(engine) -> Dict[str, Any]:
    """Check if the cohort system is properly integrated."""
    results = {
        "cohort_system_available": False,
        "cohort_state_initialized": False,
        "using_cohort_population": False,
        "population_method": "unknown",
        "cohort_data_present": False,
        "birth_death_rates": {},
        "issues": []
    }
    
    # Check if cohort system is available
    try:
        from sim.cohorts import step_cohorts, FERTILITY_PER_FEMALE_PER_YEAR, MORTALITY_PER_YEAR
        results["cohort_system_available"] = True
        results["birth_death_rates"] = {
            "fertility_per_female_per_year": float(FERTILITY_PER_FEMALE_PER_YEAR),
            "mortality_rates": {k: float(v) for k, v in MORTALITY_PER_YEAR.items()}
        }
    except ImportError as e:
        results["issues"].append(f"Cohort system import failed: {e}")
    
    # Check if engine has cohort state
    if hasattr(engine, 'cohort_state'):
        results["cohort_state_initialized"] = True
        
        # Check if cohort state has data
        try:
            cohort_state = engine.cohort_state
            if hasattr(cohort_state, 'cohort_maps') and cohort_state.cohort_maps:
                results["cohort_data_present"] = True
        except Exception as e:
            results["issues"].append(f"Cohort state access failed: {e}")
    else:
        results["issues"].append("Engine missing 'cohort_state' attribute")
    
    # Check which population advancement method is being used
    if hasattr(engine, 'advance_turn'):
        advance_method = engine.advance_turn
        if hasattr(advance_method, '__name__'):
            if 'integrated' in advance_method.__name__ or 'cohort' in advance_method.__name__:
                results["using_cohort_population"] = True
                results["population_method"] = "cohort-based"
            else:
                results["population_method"] = "logistic growth"
        else:
            results["population_method"] = "unknown (wrapped)"
    
    return results


def analyze_population_changes(engine, turns_to_check: int = 10) -> Dict[str, Any]:
    """Analyze population changes over multiple turns."""
    results = {
        "initial_populations": {},
        "final_populations": {},
        "changes": {},
        "total_births": 0,
        "total_deaths": 0,
        "net_change": 0,
        "turn_data": []
    }
    
    # Get initial state
    initial_pops = {}
    for civ_id, civ in engine.world.civs.items():
        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        initial_pops[civ_id] = civ_pop
    
    results["initial_populations"] = initial_pops
    
    # Run simulation and track changes
    for turn in range(turns_to_check):
        turn_start_pop = sum(engine.world.get_tile(t.q, t.r).pop for t in engine.world.tiles)
        
        # Step the simulation
        engine.step()
        
        turn_end_pop = sum(engine.world.get_tile(t.q, t.r).pop for t in engine.world.tiles)
        
        turn_data = {
            "turn": turn,
            "start_population": turn_start_pop,
            "end_population": turn_end_pop,
            "change": turn_end_pop - turn_start_pop
        }
        
        results["turn_data"].append(turn_data)
    
    # Get final state
    final_pops = {}
    for civ_id, civ in engine.world.civs.items():
        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        final_pops[civ_id] = civ_pop
    
    results["final_populations"] = final_pops
    
    # Calculate changes
    changes = {}
    for civ_id in initial_pops:
        if civ_id in final_pops:
            changes[civ_id] = final_pops[civ_id] - initial_pops[civ_id]
    
    results["changes"] = changes
    results["net_change"] = sum(changes.values())
    
    return results


def get_cohort_breakdown(engine) -> Dict[str, Any]:
    """Get detailed cohort breakdown for diagnosis."""
    results = {
        "has_cohort_data": False,
        "cohort_totals": {},
        "tile_cohorts": [],
        "reproduction_potential": 0,
        "death_risk": {}
    }
    
    if not hasattr(engine, 'cohort_state'):
        return results
    
    try:
        cohort_state = engine.cohort_state
        if not hasattr(cohort_state, 'cohort_maps') or not cohort_state.cohort_maps:
            return results
        
        results["has_cohort_data"] = True
        
        # Calculate totals for each age group
        from sim.cohorts import COHORT_KEYS
        cohort_totals = {}
        for key in COHORT_KEYS:
            if key in cohort_state.cohort_maps:
                total = float(cohort_state.cohort_maps[key].sum())
                cohort_totals[key] = total
        
        results["cohort_totals"] = cohort_totals
        
        # Calculate reproduction potential (fertile females)
        fertile_females = cohort_totals.get("c15_39", 0) * 0.5  # 50% female
        from sim.cohorts import FERTILITY_PER_FEMALE_PER_YEAR
        results["reproduction_potential"] = fertile_females * float(FERTILITY_PER_FEMALE_PER_YEAR)
        
        # Calculate death risk
        from sim.cohorts import MORTALITY_PER_YEAR
        death_risk = {}
        for key, mortality_rate in MORTALITY_PER_YEAR.items():
            if key in cohort_totals:
                expected_deaths = cohort_totals[key] * float(mortality_rate)
                death_risk[key] = expected_deaths
        
        results["death_risk"] = death_risk
        
    except Exception as e:
        results["error"] = str(e)
    
    return results


def diagnose_population_system(engine) -> None:
    """Run comprehensive population system diagnosis."""
    print("POPULATION SYSTEM DIAGNOSIS")
    print("=" * 50)
    
    # Check integration
    integration = check_cohort_system_integration(engine)
    
    print("1. SYSTEM INTEGRATION CHECK")
    print("-" * 30)
    print(f"Cohort system available: {'YES' if integration['cohort_system_available'] else 'NO'}")
    print(f"Cohort state initialized: {'YES' if integration['cohort_state_initialized'] else 'NO'}")
    print(f"Using cohort population: {'YES' if integration['using_cohort_population'] else 'NO'}")
    print(f"Population method: {integration['population_method']}")
    print(f"Cohort data present: {'YES' if integration['cohort_data_present'] else 'NO'}")
    
    if integration['issues']:
        print("\nISSUES FOUND:")
        for issue in integration['issues']:
            print(f"  - {issue}")
    
    print()
    
    # Check cohort breakdown
    cohorts = get_cohort_breakdown(engine)
    
    print("2. POPULATION BREAKDOWN")
    print("-" * 30)
    if cohorts['has_cohort_data']:
        print("Age Group Distribution:")
        total_pop = sum(cohorts['cohort_totals'].values())
        for age_group, count in cohorts['cohort_totals'].items():
            percentage = (count / total_pop * 100) if total_pop > 0 else 0
            print(f"  {age_group}: {count:6.1f} ({percentage:4.1f}%)")
        
        print(f"\nReproduction potential (births/year): {cohorts['reproduction_potential']:.2f}")
        print(f"Expected deaths per year:")
        for age_group, deaths in cohorts['death_risk'].items():
            print(f"  {age_group}: {deaths:.2f}")
    else:
        print("No cohort data available")
    
    print()
    
    # Check population changes
    print("3. POPULATION DYNAMICS TEST")
    print("-" * 30)
    print("Running 10-turn simulation to check population changes...")
    
    changes = analyze_population_changes(engine, 10)
    
    print(f"Net population change: {changes['net_change']}")
    
    if changes['turn_data']:
        print("\nTurn-by-turn changes:")
        for turn_data in changes['turn_data'][-5:]:  # Show last 5 turns
            print(f"  Turn {turn_data['turn']}: {turn_data['start_population']} -> {turn_data['end_population']} ({turn_data['change']:+.1f})")
    
    print()
    
    # Recommendations
    print("4. RECOMMENDATIONS")
    print("-" * 30)
    
    if not integration['cohort_system_available']:
        print("❌ CRITICAL: Cohort system not available")
        print("   Solution: Ensure sim/cohorts.py is present")
    elif not integration['cohort_state_initialized']:
        print("❌ CRITICAL: Cohort system not integrated")
        print("   Solution: Run apply_all_fixes(engine) to enable cohort system")
    elif not integration['using_cohort_population']:
        print("⚠️  WARNING: Using simple logistic growth instead of cohorts")
        print("   Solution: Check if apply_all_fixes(engine) was called")
    elif changes['net_change'] == 0:
        print("⚠️  WARNING: No population change detected")
        print("   Possible causes:")
        print("   - Time step too small (try larger dt)")
        print("   - Population at equilibrium")
        print("   - Food constraints preventing growth")
        print("   - Mortality exactly balancing births")
    else:
        print("✅ Population system appears to be working")
        print(f"   Detected {changes['net_change']:.1f} net population change over 10 turns")


if __name__ == "__main__":
    print("Population System Diagnostic Tool")
    print("=" * 40)
    print()
    print("Usage:")
    print("  from diagnostics.population_system_check import diagnose_population_system")
    print("  diagnose_population_system(engine)")
    print()
    print("This will check if the age-based population system is working")
    print("and identify why populations might appear static.")