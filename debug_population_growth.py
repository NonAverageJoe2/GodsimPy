"""
Debug Population Growth

Test what's happening in the population growth calculation.
"""

import sys
import os
sys.path.insert(0, '.')

from engine import SimulationEngine


def debug_population_growth() -> None:
    """Debug what's happening in population growth."""
    
    print("DEBUGGING POPULATION GROWTH")
    print("=" * 40)
    
    try:
        # Create simple test
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add one civilization
        civ_id = engine.add_civ('Romans', (15, 12))
        
        # Set population
        tile = engine.world.get_tile(15, 12)
        tile.pop = 20
        tile._pop_float = 20.0
        
        print(f"Initial state:")
        print(f"  Tile ({tile.q},{tile.r}): pop={tile.pop}, _pop_float={tile._pop_float:.2f}")
        print(f"  Owner: {tile.owner}")
        
        # Get civ
        civ = engine.world.civs[civ_id]
        print(f"  Civ: {civ.name}, tiles={len(civ.tiles)}")
        
        # Check workforce food calculation
        try:
            from workforce import WORKFORCE_SYSTEM
            food_production, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(civ, engine.world, None)
            print(f"  Food: production={food_production:.2f}, capacity={food_capacity:.2f}")
        except Exception as e:
            print(f"  Food calculation failed: {e}")
            food_production, food_capacity = 0.0, 5.0
        
        # Try one turn with debug
        print(f"\nAdvancing one turn...")
        
        # Manually step through population calculation to debug
        w = engine.world
        dt = 1.0 / 52.0
        
        # Get modifiers
        from modifiers import MODIFIERS
        R = MODIFIERS.base_population_growth_rate
        print(f"  Base growth rate R: {R:.4f}")
        
        # Get terrain multiplier
        try:
            from resources import yields_for
            food_yield, _ = yields_for(tile)
            terrain_multiplier = max(0.5, food_yield / 2.0)
            print(f"  Terrain multiplier: {terrain_multiplier:.2f}")
        except:
            terrain_multiplier = 1.0
            print(f"  Terrain multiplier: {terrain_multiplier:.2f} (fallback)")
        
        # Calculate K_eff
        total_civ_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
        print(f"  Total civ pop: {total_civ_pop}")
        
        if food_capacity > 0:
            base_share = max(food_capacity / len(civ.tiles), 100.0)
            K_eff = max(200.0, base_share * terrain_multiplier * 3.0)
        else:
            K_eff = 300.0 * terrain_multiplier
        
        print(f"  Carrying capacity K_eff: {K_eff:.2f}")
        print(f"  Current _pop_float: {tile._pop_float:.2f}")
        
        # Calculate growth
        if tile._pop_float > 0:
            ratio = (K_eff - tile._pop_float) / tile._pop_float
            print(f"  Growth ratio: {ratio:.4f}")
            
            import math
            growth_rate = R  # No penalties for test
            new_pop_float = K_eff / (1.0 + ratio * math.exp(-growth_rate * dt))
            print(f"  New _pop_float (calculated): {new_pop_float:.4f}")
            
            # Apply to tile
            tile._pop_float = new_pop_float
            tile.pop = max(0, int(tile._pop_float))
            
            print(f"  New _pop_float (actual): {tile._pop_float:.4f}")
            print(f"  New pop (integer): {tile.pop}")
        
        # Now try full engine turn
        print(f"\nTrying full engine turn...")
        pre_pop = tile.pop
        pre_float = tile._pop_float
        
        engine.advance_turn()
        
        post_pop = tile.pop
        post_float = tile._pop_float
        
        print(f"  Before: pop={pre_pop}, _pop_float={pre_float:.4f}")
        print(f"  After:  pop={post_pop}, _pop_float={post_float:.4f}")
        print(f"  Change: {post_pop - pre_pop} ({post_float - pre_float:+.4f})")
        
        if post_pop == pre_pop:
            print(f"\nPOPULATION IS NOT CHANGING!")
            print(f"Need to investigate why growth calculation isn't working.")
        else:
            print(f"\nPopulation changed! Growth is working.")
        
    except Exception as e:
        print(f"Debug failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_population_growth()