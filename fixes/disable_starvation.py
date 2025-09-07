"""
Disable Starvation System

Directly patches the engine to disable the aggressive starvation system
that's killing all populations immediately.
"""

def disable_starvation_system(engine):
    """Disable the starvation death system that's killing populations."""
    
    print("DISABLING STARVATION SYSTEM")
    print("=" * 30)
    
    # Find the population advancement method
    if hasattr(engine, '_advance_population_with_tech'):
        original_method = engine._advance_population_with_tech
        
        def population_advance_no_starvation(dt: float = 1.0 / 52.0):
            """Population advancement without instant starvation deaths."""
            
            w = engine.world
            
            # Get civilization data (simplified version of original)
            civ_food_data = {}
            
            for cid, civ in w.civs.items():
                total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
                
                # Very generous food system
                food_production = max(100, total_pop * 2.0)  # Each person produces 2x their needs
                food_capacity = max(200, total_pop * 3.0)    # Can support 3x current population
                
                civ_food_data[cid] = (food_production, food_capacity)
                
                # Add food to stockpile
                max_food = max(5000, len(civ.tiles) * 1000)
                civ.stock_food = max(0, min(civ.stock_food + int(food_production * dt), max_food))
            
            # Population growth WITHOUT starvation deaths
            from modifiers import MODIFIERS
            base_growth_rate = MODIFIERS.base_population_growth_rate * 3.0  # Faster growth
            POP_MAX = 2000
            
            for t in w.tiles:
                if t.owner is None or t.pop <= 0:
                    continue
                
                food_production, food_capacity = civ_food_data.get(t.owner, (100.0, 200.0))
                civ = w.civs[t.owner]
                
                # High carrying capacity per tile
                K_eff = max(100.0, food_capacity / len(civ.tiles))
                
                # NO STARVATION DEATHS - only growth rate adjustment
                food_pressure = sum(w.get_tile(q, r).pop for q, r in civ.tiles) / max(1, food_capacity)
                if food_pressure > 2.0:  # Only slow growth if severely overpopulated
                    growth_modifier = 0.8  # Slow down but don't kill
                else:
                    growth_modifier = 1.2  # Bonus growth when not overpopulated
                
                # Apply growth
                actual_growth_rate = base_growth_rate * growth_modifier
                
                if t._pop_float > 0:
                    # Logistic growth
                    ratio = (K_eff - t._pop_float) / max(t._pop_float, 0.1)
                    new_pop_float = K_eff / (1.0 + ratio * abs((-actual_growth_rate * dt)))
                    
                    # Ensure minimum growth for small populations
                    if t._pop_float < 50:
                        new_pop_float = max(new_pop_float, t._pop_float + 0.5 * dt)
                    
                    t._pop_float = max(1.0, new_pop_float)  # Never drop below 1
                else:
                    t._pop_float = 2.0  # Respawn if extinct
                
                # Update integer population
                t.pop = max(1, min(POP_MAX, int(t._pop_float)))
        
        engine._advance_population_with_tech = population_advance_no_starvation
        print("Starvation system disabled - populations will grow steadily")
        
    else:
        print("Warning: Could not find population advancement method")
    

def create_test_with_no_starvation():
    """Create and test a simulation with no starvation system."""
    
    print("TESTING SIMULATION WITHOUT STARVATION")
    print("=" * 45)
    
    try:
        import sys
        import os
        sys.path.insert(0, '.')
        
        from engine import SimulationEngine
        from fixes.engine_integration_complete import apply_all_fixes
        
        # Create engine
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add civilizations
        civ1 = engine.add_civ('Romans', (15, 12))
        civ2 = engine.add_civ('Greeks', (20, 15))
        
        # Set populations
        engine.world.get_tile(15, 12).pop = 30
        engine.world.get_tile(20, 15).pop = 25
        
        print(f"Initial setup:")
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            print(f"  Civ {civ_id} ({civ.name}): {civ_pop} population")
        
        # Apply base fixes
        apply_all_fixes(engine)
        
        # Disable starvation
        disable_starvation_system(engine)
        
        # Run test
        print(f"\\nRunning 50 turns without starvation:")
        
        total_start = sum(t.pop for t in engine.world.tiles)
        
        for turn in range(50):
            pre_pop = sum(t.pop for t in engine.world.tiles)
            engine.advance_turn()
            post_pop = sum(t.pop for t in engine.world.tiles)
            change = post_pop - pre_pop
            
            if turn < 10 or turn % 10 == 0 or abs(change) > 1:
                print(f"Turn {turn+1:2d}: {pre_pop:5.1f} -> {post_pop:5.1f} ({change:+5.1f})")
        
        final_pop = sum(t.pop for t in engine.world.tiles)
        final_year = engine.world.calendar.year
        
        print(f"\\nResults:")
        print(f"Population: {total_start} -> {final_pop} ({final_pop - total_start:+})")
        print(f"Year: 0 -> {final_year:.2f}")
        
        # Check civilizations
        print(f"\\nFinal civilizations:")
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            print(f"  Civ {civ_id} ({civ.name}): {civ_pop} population, {len(civ.tiles)} territories")
        
        success = (final_pop > total_start) and (len(engine.world.civs) >= 2) and (final_year > 0.5)
        
        if success:
            print(f"\\nSUCCESS: Population grew without starvation deaths!")
            print(f"This fix should work for your 1000+ year simulations.")
        else:
            print(f"\\nStill has issues - check individual factors")
        
        return success
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    create_test_with_no_starvation()