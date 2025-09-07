"""
Debug Colonization System

Check why civilizations aren't expanding territories.
"""

import sys
import os
sys.path.insert(0, '.')


def debug_colonization() -> None:
    """Debug why colonization isn't working."""
    
    print("DEBUGGING COLONIZATION SYSTEM")
    print("=" * 40)
    
    try:
        from engine import SimulationEngine
        
        # Create simple test
        engine = SimulationEngine(width=32, height=24, seed=42)
        
        # Add one civilization
        civ_id = engine.add_civ('Romans', (15, 12))
        
        # Set high population to trigger expansion
        tile = engine.world.get_tile(15, 12)
        tile.pop = 50  # Well above threshold
        tile._pop_float = 50.0
        
        # Give plenty of food
        civ = engine.world.civs[civ_id]
        civ.stock_food = 1000
        
        print(f"Initial state:")
        print(f"  Tile ({tile.q},{tile.r}): pop={tile.pop}")
        print(f"  Civ food: {civ.stock_food}")
        print(f"  Civ territories: {len(civ.tiles)}")
        
        # Check neighbors
        neighbors = engine.world.neighbors6(tile.q, tile.r)
        print(f"  Available neighbors: {len(neighbors)}")
        for nq, nr in neighbors[:3]:  # Show first 3
            ntile = engine.world.get_tile(nq, nr) 
            print(f"    ({nq},{nr}): owner={ntile.owner}, biome={ntile.biome}")
        
        # Set faster colonization for testing
        engine.world.colonize_period_years = 0.05  # Every 2-3 turns instead of 15-16
        
        # Try advancing several turns and check for expansion
        print(f"\nAdvancing turns to test expansion...")
        
        for turn in range(20):  # Run more turns
            initial_territories = len(civ.tiles)
            initial_food = civ.stock_food
            
            print(f"\nTurn {turn+1}:")
            print(f"  Before: {initial_territories} territories, {initial_food} food")
            
            engine.advance_turn()
            
            final_territories = len(civ.tiles)
            final_food = civ.stock_food
            
            print(f"  After:  {final_territories} territories, {final_food} food")
            
            if final_territories > initial_territories:
                print(f"  SUCCESS: Expanded! New territories:")
                for q, r in civ.tiles:
                    tile_pop = engine.world.get_tile(q, r).pop
                    print(f"    ({q},{r}): {tile_pop} pop")
                break
            else:
                print(f"  No expansion occurred")
                
                # Check expansion conditions
                pop_threshold = 15  # From engine code
                tile_pop = engine.world.get_tile(15, 12).pop
                print(f"    Population check: {tile_pop} >= {pop_threshold}? {tile_pop >= pop_threshold}")
                print(f"    Food check: {civ.stock_food} >= 5? {civ.stock_food >= 5}")
        
        if len(civ.tiles) == 1:
            print(f"\nEXPANSION FAILED - No territorial growth after 10 turns")
            print(f"This explains why civilizations stagnate in long games!")
        else:
            print(f"\nExpansion working - found {len(civ.tiles)} territories")
        
    except Exception as e:
        print(f"Debug failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_colonization()