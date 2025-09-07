"""
Population System Integration

Ensures the age-based population system with births, deaths, and aging
is properly enabled and working in your GodsimPy simulation.
"""

from typing import Any, Dict, Optional


def enable_realistic_population_system(engine: Any, enabled: bool = True) -> bool:
    """Enable or disable the realistic age-based population system."""
    if not enabled:
        print("Note: Disabling cohort system requires restart - not supported")
        return False
    
    try:
        # Apply the complete integration fixes (includes cohort system)
        from fixes.engine_integration_complete import apply_all_fixes
        apply_all_fixes(engine)
        
        print("✓ Realistic population system enabled")
        print("  - Age cohorts: Children, Adults, Elderly")
        print("  - Birth rates: Based on fertile female population")  
        print("  - Death rates: Age-appropriate mortality")
        print("  - Aging: Population moves through age groups")
        print("  - Workforce: Based on working-age population")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to enable realistic population system: {e}")
        return False


def check_population_system_status(engine: Any) -> Dict[str, Any]:
    """Check if the population system is working correctly."""
    try:
        from diagnostics.population_system_check import check_cohort_system_integration
        return check_cohort_system_integration(engine)
    except ImportError:
        # Fallback check
        status = {
            "cohort_system_available": hasattr(engine, 'cohort_state'),
            "integration_applied": False,
            "issues": []
        }
        
        if hasattr(engine, 'advance_turn'):
            method_name = getattr(engine.advance_turn, '__name__', 'unknown')
            status["integration_applied"] = 'integrated' in method_name
        
        return status


def diagnose_population_issues(engine: Any) -> None:
    """Diagnose and fix common population system issues."""
    try:
        from diagnostics.population_system_check import diagnose_population_system
        diagnose_population_system(engine)
    except ImportError:
        # Simplified diagnosis
        print("POPULATION SYSTEM DIAGNOSIS")
        print("=" * 40)
        
        status = check_population_system_status(engine)
        
        if not status.get('cohort_system_available', False):
            print("❌ ISSUE: Age-based population system not active")
            print("   Solution: Run enable_realistic_population_system(engine)")
        elif not status.get('integration_applied', False):
            print("❌ ISSUE: Population integration not applied")  
            print("   Solution: Run enable_realistic_population_system(engine)")
        else:
            print("✅ Population system appears to be integrated")
            
            # Quick population test
            initial_total = sum(t.pop for t in engine.world.tiles)
            engine.step()
            final_total = sum(t.pop for t in engine.world.tiles)
            change = final_total - initial_total
            
            print(f"Population change in 1 step: {change:+.1f}")
            
            if change == 0:
                print("⚠️  No population change detected")
                print("   Possible causes: equilibrium, small time step, food constraints")
            else:
                print("✅ Population changes are occurring")


def get_population_parameters() -> Dict[str, Any]:
    """Get current population system parameters."""
    try:
        from sim.cohorts import FERTILITY_PER_FEMALE_PER_YEAR, MORTALITY_PER_YEAR
        
        return {
            "fertility_per_female_per_year": float(FERTILITY_PER_FEMALE_PER_YEAR),
            "mortality_rates": {k: float(v) for k, v in MORTALITY_PER_YEAR.items()},
            "age_groups": {
                "c0_4": "Ages 0-4 (Children)",
                "c5_14": "Ages 5-14 (Youth)",
                "c15_39": "Ages 15-39 (Prime Adults)",
                "c40_64": "Ages 40-64 (Mature Adults)",
                "c65p": "Ages 65+ (Elderly)"
            }
        }
    except ImportError:
        return {"error": "Population system not available"}


def print_population_info() -> None:
    """Print information about the population system."""
    params = get_population_parameters()
    
    if "error" in params:
        print(f"Error: {params['error']}")
        return
    
    print("REALISTIC POPULATION SYSTEM PARAMETERS")
    print("=" * 45)
    print()
    print("Age Groups:")
    for key, description in params["age_groups"].items():
        print(f"  {key}: {description}")
    
    print()
    print(f"Fertility Rate: {params['fertility_per_female_per_year']:.3f} births per female per year")
    
    print()
    print("Mortality Rates (deaths per person per year):")
    for age_group, rate in params["mortality_rates"].items():
        percentage = rate * 100
        print(f"  {age_group}: {rate:.3f} ({percentage:.1f}%)")
    
    print()
    print("What this means:")
    print("- Populations grow through births (fertile females reproduce)")
    print("- Populations shrink through deaths (age-appropriate mortality)")  
    print("- People age over time, moving between groups")
    print("- Workforce comes from working-age population (15-64)")
    print("- Population growth is realistic and dynamic")


def setup_comprehensive_population_system(engine: Any) -> None:
    """Set up the complete realistic population system."""
    print("Setting up comprehensive population system...")
    print()
    
    # Enable realistic population
    success = enable_realistic_population_system(engine)
    
    if success:
        print()
        print("Population system parameters:")
        print_population_info()
        
        print()
        print("System is now active! You should see:")
        print("- Population changes over time due to births and deaths")
        print("- Age-appropriate population distribution") 
        print("- Dynamic workforce based on working-age population")
        print("- Realistic population growth patterns")
        
    else:
        print("❌ Failed to set up population system")
        print("Try running diagnose_population_issues(engine) for help")


if __name__ == "__main__":
    print("Population System Integration Module")
    print("=" * 40)
    print()
    print("Quick setup:")
    print("  from integrations.population_system_integration import setup_comprehensive_population_system")
    print("  setup_comprehensive_population_system(engine)")
    print()
    print("Diagnosis:")
    print("  from integrations.population_system_integration import diagnose_population_issues") 
    print("  diagnose_population_issues(engine)")