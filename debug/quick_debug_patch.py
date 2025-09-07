"""
Quick Debug Patch

Adds debug output to your existing running simulation to see what's happening
with population, time, and colonization systems.
"""

def enable_debug_mode(engine):
    """Enable comprehensive debug output for an existing engine."""
    
    print("🔧 ENABLING DEBUG MODE")
    print("=" * 40)
    
    # Add turn counter
    if not hasattr(engine, '_debug_turn'):
        engine._debug_turn = engine.world.turn
        engine._debug_start_year = engine.world.calendar.year
    
    # Store original methods
    if not hasattr(engine, '_original_step'):
        engine._original_step = engine.step
        
    if not hasattr(engine, '_original_advance_turn'):
        engine._original_advance_turn = engine.advance_turn
    
    # Debug step method
    def debug_step(dt=1.0/52.0):
        engine._debug_turn += 1
        turn = engine._debug_turn
        
        # Get population data before step
        pre_pop_data = {}
        total_pre_pop = 0
        
        print(f"\n🔄 TURN {turn} (Year {engine.world.calendar.year})")
        print("-" * 30)
        
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            pre_pop_data[civ_id] = {
                'pop': civ_pop,
                'tiles': len(civ.tiles),
                'food': getattr(civ, 'stock_food', 0)
            }
            total_pre_pop += civ_pop
            
            print(f"Civ {civ_id} ({getattr(civ, 'name', 'Unknown')}):")
            print(f"  Pop: {civ_pop:.1f}, Tiles: {len(civ.tiles)}, Food: {pre_pop_data[civ_id]['food']}")
            
            # Check individual tile populations
            if len(civ.tiles) <= 5:  # Only show for small civs
                for q, r in civ.tiles:
                    tile = engine.world.get_tile(q, r)
                    print(f"    Tile ({q},{r}): {tile.pop:.1f} pop")
        
        print(f"TOTAL PRE-STEP POPULATION: {total_pre_pop:.1f}")
        
        # Check what systems are active
        print(f"Time step: {dt:.6f} years ({dt*365:.1f} days)")
        
        # Check cohort system
        if hasattr(engine, 'cohort_state'):
            print("📊 Cohort system: ACTIVE")
            if hasattr(engine.cohort_state, 'cohort_maps'):
                total_cohort_pop = 0
                for key, cohort_map in engine.cohort_state.cohort_maps.items():
                    cohort_total = float(cohort_map.sum())
                    total_cohort_pop += cohort_total
                    if turn % 10 == 0:  # Detailed cohort info every 10 turns
                        print(f"  {key}: {cohort_total:.1f}")
                print(f"  Total cohort population: {total_cohort_pop:.1f}")
            else:
                print("  No cohort maps found")
        else:
            print("📊 Cohort system: NOT FOUND")
        
        # Execute the step
        result = engine._original_step(dt)
        
        # Get population data after step
        post_pop_data = {}
        total_post_pop = 0
        
        for civ_id, civ in engine.world.civs.items():
            civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
            post_pop_data[civ_id] = civ_pop
            total_post_pop += civ_pop
        
        # Calculate changes
        total_change = total_post_pop - total_pre_pop
        
        print(f"\n📈 POST-STEP RESULTS:")
        print(f"TOTAL POPULATION: {total_pre_pop:.1f} -> {total_post_pop:.1f} ({total_change:+.3f})")
        
        # Show per-civ changes
        any_changes = False
        for civ_id in pre_pop_data:
            if civ_id in post_pop_data:
                change = post_pop_data[civ_id] - pre_pop_data[civ_id]['pop']
                if abs(change) > 0.001:
                    print(f"  Civ {civ_id}: {pre_pop_data[civ_id]['pop']:.1f} -> {post_pop_data[civ_id]:.1f} ({change:+.3f})")
                    any_changes = True
        
        if not any_changes:
            print("  No population changes detected")
        
        # Check for new territories
        territory_changes = False
        for civ_id in pre_pop_data:
            if civ_id in engine.world.civs:
                new_tiles = len(engine.world.civs[civ_id].tiles)
                old_tiles = pre_pop_data[civ_id]['tiles']
                if new_tiles != old_tiles:
                    print(f"  🏛️ Civ {civ_id} territories: {old_tiles} -> {new_tiles}")
                    territory_changes = True
        
        if not territory_changes and turn % 20 == 0:
            print("  No territorial changes (expansion)")
        
        # Yearly summary
        if turn % 52 == 0:
            years_elapsed = engine.world.calendar.year - engine._debug_start_year
            print(f"\n🗓️  YEAR {engine.world.calendar.year} COMPLETE ({years_elapsed} years elapsed)")
            print("=" * 50)
        
        return result
    
    # Replace step method
    engine.step = debug_step
    
    print("✅ Debug mode enabled!")
    print("Now run your simulation - you'll see detailed output every turn")
    print("Population changes, births, deaths, and expansions will be tracked")


def quick_population_analysis(engine):
    """Quick analysis of current population state."""
    
    print("\n🔍 QUICK POPULATION ANALYSIS")
    print("=" * 40)
    
    total_pop = 0
    total_tiles = 0
    
    for civ_id, civ in engine.world.civs.items():
        civ_pop = sum(engine.world.get_tile(q, r).pop for q, r in civ.tiles)
        total_pop += civ_pop
        total_tiles += len(civ.tiles)
        
        print(f"Civ {civ_id} ({getattr(civ, 'name', 'Unknown')}):")
        print(f"  Population: {civ_pop:.1f}")
        print(f"  Territories: {len(civ.tiles)}")
        print(f"  Food: {getattr(civ, 'stock_food', 'N/A')}")
        
        # Show tile breakdown
        if len(civ.tiles) > 0:
            tile_pops = [engine.world.get_tile(q, r).pop for q, r in civ.tiles]
            print(f"  Largest settlement: {max(tile_pops):.1f}")
            print(f"  Average settlement: {sum(tile_pops)/len(tile_pops):.1f}")
    
    print(f"\nWORLD TOTALS:")
    print(f"  Population: {total_pop:.1f}")
    print(f"  Territories: {total_tiles}")
    print(f"  Current Year: {engine.world.calendar.year}")
    print(f"  Turn: {engine.world.turn}")
    
    # Check what systems are active
    print(f"\nSYSTEM STATUS:")
    
    if hasattr(engine, 'cohort_state'):
        print("  ✅ Cohort system: Found")
        if hasattr(engine.cohort_state, 'cohort_maps') and engine.cohort_state.cohort_maps:
            total_cohort = sum(float(cm.sum()) for cm in engine.cohort_state.cohort_maps.values())
            print(f"     Total cohort population: {total_cohort:.1f}")
        else:
            print("     ❌ No cohort data")
    else:
        print("  ❌ Cohort system: Not found")
    
    # Check if fixes are applied
    if hasattr(engine.advance_turn, '__name__'):
        if 'integrated' in engine.advance_turn.__name__:
            print("  ✅ Integration fixes: Applied")
        else:
            print("  ❌ Integration fixes: Not applied")
    else:
        print("  ❓ Integration status: Unknown")
    
    return {
        'total_population': total_pop,
        'total_territories': total_tiles,
        'year': engine.world.calendar.year,
        'turn': engine.world.turn
    }


if __name__ == "__main__":
    print("Quick Debug Patch")
    print("=" * 20)
    print()
    print("Usage:")
    print("  from debug.quick_debug_patch import enable_debug_mode")
    print("  enable_debug_mode(engine)")
    print("  # Then run your simulation normally")
    print()
    print("For analysis:")
    print("  from debug.quick_debug_patch import quick_population_analysis") 
    print("  quick_population_analysis(engine)")