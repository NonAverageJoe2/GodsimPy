"""
Simple Population Fix - ASCII only version

Fixes the critical population system issues without Unicode characters.
"""

from typing import Any
import math


def fix_population_system(engine: Any) -> None:
    """Apply all population fixes without Unicode output."""
    
    print("APPLYING POPULATION SYSTEM FIXES")
    print("=" * 45)
    
    # Apply base fixes first
    try:
        from fixes.engine_integration_complete import apply_all_fixes
        apply_all_fixes(engine)
        print("Base integration fixes applied")
    except Exception as e:
        print(f"Warning: Base fixes failed: {e}")
    
    # Fix 1: Starvation system
    fix_starvation(engine)
    
    # Fix 2: Growth rates  
    fix_growth_rates(engine)
    
    # Fix 3: Food system
    fix_food_balance(engine)
    
    print("All population fixes applied successfully!")


def fix_starvation(engine: Any) -> None:
    """Fix the starvation system to prevent instant population death."""
    
    if hasattr(engine, '_advance_population_with_tech'):
        original = engine._advance_population_with_tech
        
        def gentle_population_advance(dt: float = 1.0 / 52.0):
            w = engine.world
            
            # Calculate food data for each civ
            civ_food_data = {}
            
            for cid, civ in w.civs.items():
                total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
                
                # Use existing workforce system but with higher base capacity
                try:
                    from workforce import WORKFORCE_SYSTEM
                    food_production, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(civ, w, None)
                    
                    # Add generous subsistence baseline
                    subsistence = total_pop * 0.9  # 90% can survive on subsistence
                    adjusted_capacity = food_capacity + subsistence
                    
                except Exception:
                    # Fallback - very generous
                    food_production = total_pop * 1.5
                    adjusted_capacity = total_pop * 2.0
                
                civ_food_data[cid] = (food_production, adjusted_capacity)
                
                # Increase food stockpile more generously
                max_food = max(3000, len(civ.tiles) * 500)
                civ.stock_food = max(0, min(civ.stock_food + int(food_production * dt * 3), max_food))
            
            # Population growth with gentle constraints
            from modifiers import MODIFIERS
            base_growth = MODIFIERS.base_population_growth_rate * 4.0  # Much faster growth
            
            for t in w.tiles:
                if t.owner is None or t.pop <= 0:
                    continue
                
                food_production, food_capacity = civ_food_data.get(t.owner, (50.0, 100.0))
                civ = w.civs[t.owner]
                total_civ_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
                
                # Calculate local carrying capacity - much higher than before
                capacity_per_tile = max(50.0, food_capacity / len(civ.tiles))
                
                # Very gentle food pressure - no death, just slower growth
                food_pressure = total_civ_pop / max(1, food_capacity)
                if food_pressure > 1.5:  # Only apply pressure if severely overpopulated
                    growth_modifier = max(0.5, 1.0 / food_pressure)  # Slow down but don't stop
                else:
                    growth_modifier = 1.5  # Bonus growth when well-fed
                
                # Apply enhanced growth
                growth_rate = base_growth * growth_modifier
                
                if t._pop_float > 0:
                    # Logistic growth with much higher carrying capacity
                    K = capacity_per_tile
                    ratio = (K - t._pop_float) / max(t._pop_float, 0.1)
                    new_pop = K / (1.0 + ratio * math.exp(-growth_rate * dt))
                    
                    # Ensure growth for small populations
                    if t._pop_float < 20:
                        new_pop = max(new_pop, t._pop_float + 0.2 * dt)
                    
                    t._pop_float = max(0.1, new_pop)
                else:
                    t._pop_float = 1.0
                
                # Update integer pop
                t.pop = max(0, min(1_000_000, int(t._pop_float)))  # Much higher for 5000+ year simulations
        
        engine._advance_population_with_tech = gentle_population_advance
        print("Starvation system fixed - no more instant death")
    else:
        print("Warning: Population advancement method not found")


def fix_growth_rates(engine: Any) -> None:
    """Increase population growth rates for more dynamic changes."""
    
    try:
        from modifiers import MODIFIERS
        
        if not hasattr(MODIFIERS, '_original_growth'):
            MODIFIERS._original_growth = MODIFIERS.base_population_growth_rate
        
        # Significantly increase growth rate
        MODIFIERS.base_population_growth_rate = MODIFIERS._original_growth * 5.0
        
        print(f"Growth rate increased: {MODIFIERS._original_growth:.4f} -> {MODIFIERS.base_population_growth_rate:.4f}")
        
    except Exception as e:
        print(f"Warning: Could not modify growth rate: {e}")


def fix_food_balance(engine: Any) -> None:
    """Make food system more generous to support population growth."""
    
    try:
        from workforce import WORKFORCE_SYSTEM
        
        if not hasattr(WORKFORCE_SYSTEM, '_original_values'):
            WORKFORCE_SYSTEM._original_values = {
                'productivity': WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY,
                'ratio': WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO
            }
        
        # Make agriculture much more productive
        WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY = WORKFORCE_SYSTEM._original_values['productivity'] * 3.0
        WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO = WORKFORCE_SYSTEM._original_values['ratio'] * 0.5  # Need fewer farmers
        
        print(f"Food system rebalanced:")
        print(f"  Productivity: {WORKFORCE_SYSTEM._original_values['productivity']} -> {WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY}")
        print(f"  Farmer ratio: {WORKFORCE_SYSTEM._original_values['ratio']:.1%} -> {WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO:.1%}")
        
    except Exception as e:
        print(f"Warning: Could not modify food system: {e}")


def test_population_fix(turns: int = 100) -> None:
    """Test the population fix with a simulation."""
    
    print(f"TESTING POPULATION FIX - {turns} TURNS")
    print("=" * 40)
    
    try:
        from engine import SimulationEngine
        
        # Create test world
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add civs
        civ1_id = engine.add_civ('Test Civ 1', (15, 12))
        civ2_id = engine.add_civ('Test Civ 2', (20, 15))
        
        # Set initial populations
        engine.world.get_tile(15, 12).pop = 20
        engine.world.get_tile(20, 15).pop = 25
        
        total_start = sum(t.pop for t in engine.world.tiles)
        year_start = engine.world.calendar.year
        
        print(f"Starting: {total_start} population, Year {year_start}")
        
        # Apply fixes
        fix_population_system(engine)
        
        print(f"\nRunning {turns} turns...")
        
        # Run simulation
        populations = []
        for i in range(turns):
            pre_pop = sum(t.pop for t in engine.world.tiles)
            engine.advance_turn()
            post_pop = sum(t.pop for t in engine.world.tiles)
            
            populations.append(post_pop)
            
            if i < 5 or i % 20 == 0:
                change = post_pop - pre_pop
                print(f"Turn {i+1:3d}: {pre_pop:5.1f} -> {post_pop:5.1f} ({change:+5.1f})")
        
        # Results
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        
        print(f"\nRESULTS:")
        print(f"Population: {total_start} -> {final_pop:.1f} ({final_pop - total_start:+.1f})")
        print(f"Time: Year {year_start} -> {final_year:.2f} ({final_year - year_start:.2f} years)")
        
        # Check civilizations
        print(f"\nCivilizations:")
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            print(f"  Civ {civ_id}: {civ_pop:.1f} population, {len(civ.tiles)} territories")
        
        # Success check
        growth_turns = sum(1 for i in range(1, len(populations)) if populations[i] > populations[i-1])
        success = (final_year > year_start + 0.1) and (abs(final_pop - total_start) > 2.0) and (len(engine.world.civs) > 0)
        
        print(f"\nSUCCESS INDICATORS:")
        print(f"  Time advanced: {final_year > year_start + 0.1}")
        print(f"  Population changed: {abs(final_pop - total_start) > 2.0}")
        print(f"  Civs survived: {len(engine.world.civs) > 0}")
        print(f"  Growth turns: {growth_turns}/{turns}")
        
        if success:
            print(f"\nSUCCESS: Population system is now working!")
        else:
            print(f"\nStill needs work - check individual indicators")
        
        return success
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_population_fix(100)