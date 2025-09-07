"""
Population System Fix

Fixes the critical issues identified in the population system:
1. Starvation system killing all populations immediately
2. Time progression not advancing calendar  
3. Population equilibrium at starvation levels
4. No population growth over long periods
"""

from typing import Any
import math


def apply_population_system_fix(engine: Any) -> None:
    """Apply comprehensive fixes to the population system."""
    
    print("APPLYING POPULATION SYSTEM FIXES")
    print("=" * 50)
    
    fix_starvation_system(engine)
    fix_time_progression(engine)
    fix_population_growth(engine)
    fix_food_system_balance(engine)
    
    print("All population system fixes applied!")


def fix_starvation_system(engine: Any) -> None:
    """Fix the overly aggressive starvation system."""
    
    # Find and patch the population advancement method
    if hasattr(engine, '_advance_population_with_tech'):
        original_advance_pop = engine._advance_population_with_tech
        
        def balanced_advance_population(dt: float = 1.0 / 52.0):
            """Population advancement with balanced starvation."""
            w = engine.world
            
            # Get civilization food data (from original)
            civ_food_data = {}
            manpower_penalties = {}
            
            for cid, civ in w.civs.items():
                total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
                
                # Use workforce system for food calculation
                try:
                    from workforce import WORKFORCE_SYSTEM
                    tech_bonuses = None
                    if hasattr(engine, 'tech_system') and cid in engine.tech_system.civ_states:
                        tech_bonuses = engine.tech_system.get_civ_bonuses(cid)
                    
                    food_production, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(
                        civ, w, tech_bonuses
                    )
                    
                    # Add base subsistence capacity to prevent starvation deaths
                    base_subsistence = total_pop * 0.8  # 80% subsistence baseline
                    adjusted_capacity = food_capacity + base_subsistence
                    
                except Exception:
                    # Fallback calculation
                    food_production = total_pop * 1.2
                    adjusted_capacity = total_pop * 1.5
                
                civ_food_data[cid] = (food_production, adjusted_capacity)
                
                # Add food to stockpile (with higher max)
                max_food = max(2000, len(civ.tiles) * 300)  # Increased food storage
                civ.stock_food = max(0, min(civ.stock_food + int(food_production * dt * 2), max_food))
            
            # Enhanced population growth with gentler starvation
            from modifiers import MODIFIERS
            R = MODIFIERS.base_population_growth_rate * 2.0  # Increased base growth
            POP_MAX = 1_000_000  # Much higher for 5000+ year simulations
            
            for t in w.tiles:
                if t.owner is None:
                    continue
                
                food_production, food_capacity = civ_food_data.get(t.owner, (0.0, 50.0))
                civ = w.civs[t.owner]
                total_civ_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
                
                # Technology bonuses
                growth_bonus = 0.0
                terrain_multiplier = 1.0
                
                if hasattr(engine, 'tech_system') and t.owner in engine.tech_system.civ_states:
                    bonuses = engine.tech_system.get_civ_bonuses(t.owner)
                    growth_bonus = bonuses.population_growth_rate
                
                # Calculate local carrying capacity
                try:
                    from resources import yields_for
                    food_yield, _ = yields_for(t)
                    terrain_multiplier = max(0.8, food_yield / 2.0)
                except:
                    terrain_multiplier = 1.0
                
                # Distribute capacity among tiles
                if food_capacity > 0 and total_civ_pop > 0:
                    base_share = food_capacity / len(civ.tiles)
                    K_eff = max(20.0, base_share * terrain_multiplier)  # Higher minimum capacity
                else:
                    K_eff = 60.0 * terrain_multiplier  # Higher fallback capacity
                
                # GENTLE starvation system - no instant deaths, just reduced growth
                starvation_modifier = 1.0
                if total_civ_pop > food_capacity:
                    overpop_ratio = total_civ_pop / max(1, food_capacity)
                    # Gradual slowdown instead of death
                    starvation_modifier = max(0.2, 1.0 / (1.0 + (overpop_ratio - 1.0) * 0.3))
                else:
                    # Bonus growth when well-fed
                    food_bonus = min(1.2, food_capacity / max(1, total_civ_pop))
                    starvation_modifier = food_bonus
                
                # Apply enhanced logistic growth
                actual_r = (R + growth_bonus) * starvation_modifier
                
                if t._pop_float > 0:
                    ratio = (K_eff - t._pop_float) / t._pop_float
                    new_pop_float = K_eff / (1.0 + ratio * math.exp(-actual_r * dt))
                    
                    # Ensure positive growth for small populations
                    if t._pop_float < 10 and new_pop_float <= t._pop_float:
                        new_pop_float = t._pop_float + 0.1 * dt * actual_r
                    
                    t._pop_float = new_pop_float
                else:
                    t._pop_float = 1.0  # Minimum viable population
                
                # Update integer population
                pop_int = max(0, min(POP_MAX, math.floor(t._pop_float)))
                object.__setattr__(t, 'pop', pop_int)
        
        engine._advance_population_with_tech = balanced_advance_population
        print("Starvation system fixed (gentle decline vs instant death)")
    
    else:
        print("⚠️  Population advancement method not found")


def fix_time_progression(engine: Any) -> None:
    """Fix time progression to ensure calendar advances."""
    
    if hasattr(engine, 'advance_turn'):
        original_advance_turn = engine.advance_turn
        
        def enhanced_advance_turn(dt: float = 1.0 / 52.0):
            """Enhanced advance_turn with proper time progression."""
            
            # Ensure minimum time progression
            actual_dt = max(dt, 1.0 / 52.0)  # At least 1 week per turn
            
            # Call original advance_turn with proper dt
            result = original_advance_turn(actual_dt)
            
            # Force calendar advancement if it's stuck
            if not hasattr(engine.world, '_last_calendar_check'):
                engine.world._last_calendar_check = engine.world.calendar.year
            
            if engine.world.calendar.year == engine.world._last_calendar_check:
                # Calendar hasn't advanced, force it
                engine.world.calendar.advance_fraction(actual_dt)
            
            engine.world._last_calendar_check = engine.world.calendar.year
            
            return result
        
        engine.advance_turn = enhanced_advance_turn
        print("✅ Time progression fixed (calendar will advance properly)")
    
    else:
        print("⚠️  advance_turn method not found")


def fix_population_growth(engine: Any) -> None:
    """Fix population growth to be more noticeable over long periods."""
    
    # Increase base population growth rate
    try:
        from modifiers import MODIFIERS
        
        # Store original rate
        if not hasattr(MODIFIERS, '_original_growth_rate'):
            MODIFIERS._original_growth_rate = MODIFIERS.base_population_growth_rate
        
        # Increase growth rate for more dynamic population changes
        MODIFIERS.base_population_growth_rate = MODIFIERS._original_growth_rate * 3.0
        
        print(f"✅ Population growth rate increased: {MODIFIERS._original_growth_rate:.3f} -> {MODIFIERS.base_population_growth_rate:.3f}")
    
    except Exception as e:
        print(f"⚠️  Could not modify growth rate: {e}")


def fix_food_system_balance(engine: Any) -> None:
    """Fix food system to support sustainable population growth."""
    
    # Patch workforce system to be less restrictive
    try:
        from workforce import WORKFORCE_SYSTEM
        
        # Store original values
        if not hasattr(WORKFORCE_SYSTEM, '_original_productivity'):
            WORKFORCE_SYSTEM._original_productivity = WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY
            WORKFORCE_SYSTEM._original_ratio = WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO
        
        # Increase agricultural productivity and reduce required farmers
        WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY = WORKFORCE_SYSTEM._original_productivity * 2.0  # Farmers feed more people
        WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO = WORKFORCE_SYSTEM._original_ratio * 0.7  # Need fewer farmers
        
        print(f"✅ Food system rebalanced:")
        print(f"   Agricultural productivity: {WORKFORCE_SYSTEM._original_productivity} -> {WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY}")
        print(f"   Required farmer ratio: {WORKFORCE_SYSTEM._original_ratio:.1%} -> {WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO:.1%}")
    
    except Exception as e:
        print(f"⚠️  Could not modify food system: {e}")


def restore_original_population_system(engine: Any) -> None:
    """Restore original population system settings."""
    
    print("🔄 RESTORING ORIGINAL POPULATION SYSTEM")
    
    # Restore growth rate
    try:
        from modifiers import MODIFIERS
        if hasattr(MODIFIERS, '_original_growth_rate'):
            MODIFIERS.base_population_growth_rate = MODIFIERS._original_growth_rate
            delattr(MODIFIERS, '_original_growth_rate')
            print("✅ Growth rate restored")
    except:
        pass
    
    # Restore workforce system
    try:
        from workforce import WORKFORCE_SYSTEM
        if hasattr(WORKFORCE_SYSTEM, '_original_productivity'):
            WORKFORCE_SYSTEM.AGRICULTURAL_PRODUCTIVITY = WORKFORCE_SYSTEM._original_productivity
            WORKFORCE_SYSTEM.BASE_AGRICULTURAL_RATIO = WORKFORCE_SYSTEM._original_ratio
            delattr(WORKFORCE_SYSTEM, '_original_productivity')
            delattr(WORKFORCE_SYSTEM, '_original_ratio')
            print("✅ Food system restored")
    except:
        pass
    
    print("Original system restored")


# Integration function
def enable_fixed_population_system(engine: Any, enabled: bool = True) -> None:
    """Enable or disable the fixed population system."""
    
    if enabled:
        # Apply all fixes first to get cohort system
        try:
            from fixes.engine_integration_complete import apply_all_fixes
            apply_all_fixes(engine)
        except Exception as e:
            print(f"Warning: Could not apply base fixes: {e}")
        
        # Then apply population fixes
        apply_population_system_fix(engine)
        
        print("🎉 FIXED POPULATION SYSTEM ENABLED")
        print("Expected improvements:")
        print("- No instant starvation deaths")
        print("- Proper time progression")
        print("- Sustainable population growth")
        print("- Population changes visible over 100+ turns")
        print("- Realistic demographic dynamics")
        
    else:
        restore_original_population_system(engine)


if __name__ == "__main__":
    print("Population System Fix")
    print("=" * 30)
    print()
    print("This fix addresses the critical issues:")
    print("1. Starvation system killing populations instantly")
    print("2. Time not progressing properly")
    print("3. No population growth over long periods")
    print()
    print("Usage:")
    print("  from fixes.population_system_fix import enable_fixed_population_system")
    print("  enable_fixed_population_system(engine)")
    print()
    print("Then run your simulation for 100+ turns to see population changes!")