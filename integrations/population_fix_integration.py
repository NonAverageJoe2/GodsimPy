"""
Population Expansion Fix Integration

This module provides easy integration of fixes for the population expansion
bottleneck where civilizations get stuck at around 39 population.
"""

from typing import Any, Dict


def enable_population_expansion_fixes(engine: Any, enabled: bool = True) -> None:
    """Enable or disable population expansion fixes."""
    if not enabled:
        # Remove fixes
        try:
            from fixes.population_expansion_fix import remove_population_expansion_fixes
            remove_population_expansion_fixes(engine)
        except Exception:
            pass
        return
    
    # Apply fixes
    try:
        from fixes.population_expansion_fix import integrate_population_expansion_fixes
        integrate_population_expansion_fixes(engine)
        print("✓ Population expansion fixes enabled")
    except Exception as e:
        print(f"✗ Failed to enable population expansion fixes: {e}")


def get_population_diagnostics(engine: Any) -> Dict[str, Any]:
    """Get diagnostic information about population and food systems."""
    diagnostics = {
        "civilizations": {},
        "total_population": 0,
        "food_limited_civs": 0,
        "expanding_civs": 0
    }
    
    try:
        from workforce import WORKFORCE_SYSTEM
    except ImportError:
        return {"error": "Workforce system not available"}
    
    total_pop = 0
    food_limited_count = 0
    expanding_count = 0
    
    for civ_id, civ in engine.world.civs.items():
        civ_total_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        total_pop += civ_total_pop
        
        if civ_total_pop == 0:
            continue
        
        # Calculate food situation
        try:
            food_production, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(
                civ, engine.world, None
            )
            food_pressure_ratio = civ_total_pop / max(food_capacity, 1.0)
            is_food_limited = food_pressure_ratio > 0.8
            
            if is_food_limited:
                food_limited_count += 1
            
            # Check if expanding (has gained tiles recently)
            is_expanding = len(civ.tiles) > 1 and civ.stock_food > 20
            if is_expanding:
                expanding_count += 1
            
        except Exception:
            food_production = food_capacity = 0.0
            food_pressure_ratio = 0.0
            is_food_limited = False
        
        # Find largest tile population
        max_tile_pop = 0
        if civ.tiles:
            max_tile_pop = max(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        
        diagnostics["civilizations"][civ_id] = {
            "name": getattr(civ, 'name', f'Civ {civ_id}'),
            "total_population": civ_total_pop,
            "tiles": len(civ.tiles),
            "stock_food": getattr(civ, 'stock_food', 0),
            "food_production": food_production,
            "food_capacity": food_capacity,
            "food_pressure_ratio": food_pressure_ratio,
            "is_food_limited": is_food_limited,
            "max_tile_population": max_tile_pop,
            "stuck_at_39": max_tile_pop >= 35 and max_tile_pop <= 45 and len(civ.tiles) == 1
        }
    
    diagnostics["total_population"] = total_pop
    diagnostics["food_limited_civs"] = food_limited_count
    diagnostics["expanding_civs"] = expanding_count
    diagnostics["turn"] = engine.world.turn
    
    return diagnostics


def print_population_report(engine: Any) -> None:
    """Print a detailed population diagnostic report."""
    diagnostics = get_population_diagnostics(engine)
    
    if "error" in diagnostics:
        print(f"Error: {diagnostics['error']}")
        return
    
    print("\n" + "="*60)
    print(f"POPULATION DIAGNOSTIC REPORT - Turn {diagnostics['turn']}")
    print("="*60)
    
    print(f"Total Population: {diagnostics['total_population']}")
    print(f"Food-Limited Civilizations: {diagnostics['food_limited_civs']}")
    print(f"Currently Expanding: {diagnostics['expanding_civs']}")
    
    stuck_civs = [civ for civ in diagnostics["civilizations"].values() if civ["stuck_at_39"]]
    if stuck_civs:
        print(f"🚫 Stuck at ~39 Population: {len(stuck_civs)} civilizations")
    
    print("\nDetailed Breakdown:")
    print("-" * 60)
    
    for civ_id, civ_info in diagnostics["civilizations"].items():
        status_icons = []
        if civ_info["stuck_at_39"]:
            status_icons.append("🚫 STUCK")
        if civ_info["is_food_limited"]:
            status_icons.append("🍞 FOOD-LIMITED")
        if civ_info["tiles"] > 2:
            status_icons.append("🌍 EXPANDING")
        
        status = " ".join(status_icons) if status_icons else "✅ HEALTHY"
        
        print(f"{civ_info['name']:20} | Pop: {civ_info['total_population']:3d} | "
              f"Tiles: {civ_info['tiles']:2d} | Food: {civ_info['stock_food']:3d} | "
              f"Max Tile: {civ_info['max_tile_population']:2d} | {status}")
        
        if civ_info["food_capacity"] > 0:
            print(f"{'':22} | Food Capacity: {civ_info['food_capacity']:.1f} | "
                  f"Pressure: {civ_info['food_pressure_ratio']:.2f}")
    
    print("\n" + "="*60)
    
    # Recommendations
    if stuck_civs:
        print("RECOMMENDATIONS:")
        print("- Enable population expansion fixes: enable_population_expansion_fixes(engine)")
        print("- Or use realistic colonization system with food-pressure expansion")
        print("- Check food production balance in workforce.py")


def enable_comprehensive_expansion_system(engine: Any) -> None:
    """Enable both population fixes and realistic colonization for best results."""
    print("Enabling comprehensive expansion system...")
    
    # Enable population fixes
    enable_population_expansion_fixes(engine, enabled=True)
    
    # Enable realistic colonization
    try:
        from integrations.realistic_colonization_integration import enable_realistic_colonization
        enable_realistic_colonization(engine, enabled=True)
        print("✓ Realistic colonization system enabled")
    except Exception as e:
        print(f"⚠ Realistic colonization not available: {e}")
    
    print("✓ Comprehensive expansion system enabled")
    print("  - Food-pressure driven expansion")  
    print("  - Dynamic population thresholds")
    print("  - Geographic expansion patterns")
    print("  - Balanced food system")


# Quick diagnostic command
def diagnose_stuck_populations(engine: Any) -> None:
    """Quick diagnostic for stuck population issues."""
    print("Diagnosing population expansion issues...")
    print_population_report(engine)
    
    diagnostics = get_population_diagnostics(engine)
    stuck_count = sum(1 for civ in diagnostics["civilizations"].values() if civ["stuck_at_39"])
    
    if stuck_count > 0:
        print(f"\n🚨 Found {stuck_count} civilizations stuck at ~39 population")
        print("\nTo fix this issue, run:")
        print("  enable_comprehensive_expansion_system(engine)")
    else:
        print("\n✅ No stuck populations detected!")


if __name__ == "__main__":
    print("Population Expansion Fix Integration Module")
    print("==========================================")
    print()
    print("Usage:")
    print("  from integrations.population_fix_integration import enable_comprehensive_expansion_system")
    print("  enable_comprehensive_expansion_system(engine)")
    print()
    print("Or for diagnostics only:")
    print("  from integrations.population_fix_integration import diagnose_stuck_populations")  
    print("  diagnose_stuck_populations(engine)")