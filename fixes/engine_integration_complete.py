# engine_integration_complete.py
"""
Complete integration module that patches the engine with all fixed systems.

USAGE:
    from engine import SimulationEngine
    from engine_integration_complete import apply_all_fixes
    
    engine = SimulationEngine()
    apply_all_fixes(engine)
"""

import numpy as np
from typing import Optional

# Import all the fix modules
from .population_fixes import safe_update_population, TileHexFixed
from .military_fixes import (
    ArmyFixed, ManpowerManager, synchronize_army_lists,
    remove_army_properly
)
from .cohort_integration import CohortWorldState, TileCohorts
from .military_economy import MilitaryEconomy
from .settlement_military import SettlementMilitarySystem, SettlementType


def apply_all_fixes(engine) -> None:
    """
    Apply all fixes and integrations to the engine.
    
    This is the main entry point that should be called after engine initialization.
    """
    
    # 1. Attach new systems
    engine.manpower_manager = ManpowerManager()
    engine.cohort_state = CohortWorldState(
        engine.world.width_hex, 
        engine.world.height_hex
    )
    engine.military_economy = MilitaryEconomy()
    engine.settlement_military = SettlementMilitarySystem()
    
    # 2. Initialize cohorts from existing population
    _initialize_cohorts(engine)
    
    # 3. Replace advance_turn with integrated version
    _patch_advance_turn(engine)
    
    # 4. Replace army creation/destruction methods
    _patch_army_methods(engine)
    
    # 5. Fix save/load to include new systems
    _patch_save_load(engine)
    
    # 6. Initialize settlements
    _initialize_settlements(engine)
    
    print("All fixes applied successfully!")


def _initialize_cohorts(engine) -> None:
    """Initialize cohort data from existing population."""
    pop_map = np.zeros((engine.world.height_hex, engine.world.width_hex), dtype=np.float32)
    
    for tile in engine.world.tiles:
        pop_map[tile.r, tile.q] = float(tile.pop)
    
    engine.cohort_state.initialize_from_pop_map(pop_map)


def _initialize_settlements(engine) -> None:
    """Initialize military attributes for existing settlements."""
    for tile in engine.world.tiles:
        if hasattr(tile, 'settlement'):
            settlement_type = getattr(tile, 'settlement', 0)
        else:
            # Add settlement attribute if missing
            settlement_type = 0  # Default to hamlet
            if tile.owner is not None and tile.pop > 100:
                settlement_type = 1  # Village
            tile.settlement = settlement_type
        
        if tile.owner is not None:
            engine.settlement_military.initialize_settlement(
                tile.q, tile.r, settlement_type
            )


def _patch_advance_turn(engine) -> None:
    """Replace advance_turn with integrated version."""
    original_advance_turn = engine.advance_turn
    
    def integrated_advance_turn(dt: Optional[float] = None) -> None:
        """Enhanced advance_turn with all systems integrated."""
        
        # Get time delta
        if dt is None:
            dt = engine.delta_years()
        
        # 1. Process food economy
        food_balance = engine.military_economy.process_food_economy(
            engine.world, engine.cohort_state, dt
        )
        
        # 2. Process army maintenance
        maintenance_status = engine.military_economy.process_army_maintenance(
            engine.world, dt
        )
        
        # 3. Establish supply lines
        engine.military_economy.establish_supply_lines(engine.world)
        
        # 4. Process army supply
        engine.military_economy.process_army_supply(engine.world, dt)
        
        # 5. Process settlement supply generation
        settlement_supplies = engine.settlement_military.process_settlement_supply(
            engine.world, dt
        )
        
        # 6. Calculate war pressure for cohort effects
        war_pressure = _calculate_war_pressure(engine.world)
        
        # 7. Step cohorts (replaces simple population growth)
        food_map = _get_food_map(engine.world)
        capacity_map = _get_capacity_map(engine.world)
        
        new_pop_map = engine.cohort_state.step_all_cohorts(
            dt, food_map, capacity_map, war_pressure
        )
        
        # 8. Update tile populations from cohorts
        for tile in engine.world.tiles:
            new_pop = new_pop_map[tile.r, tile.q]
            safe_update_population(tile, new_pop)
        
        # 9. Update manpower limits based on actual cohorts
        for civ_id, civ in engine.world.civs.items():
            civ_tiles = civ.tiles
            manpower_potential = engine.cohort_state.get_civ_manpower_potential(civ_tiles)
            civ.manpower_limit = manpower_potential
            
            # Recover some casualties
            recovered = engine.manpower_manager.recover_casualties(civ_id, 0.05 * dt)
        
        # 10. Process garrison recruitment (if any queued)
        # (This would be based on player/AI decisions)
        
        # 11. Original advance_turn for remaining logic
        # (colonization, movement, etc.)
        original_advance_turn(dt)
        
        # 12. Synchronize army lists
        synchronize_army_lists(engine.world)
        
        # 13. Remove destroyed armies properly
        armies_to_remove = [a for a in engine.world.armies if a.strength <= 0]
        for army in armies_to_remove:
            remove_army_properly(engine.world, army, engine.manpower_manager, True)
    
    engine.advance_turn = integrated_advance_turn


def _patch_army_methods(engine) -> None:
    """Patch army creation and management methods."""
    original_add_army = engine.add_army
    
    def enhanced_add_army(civ_id: int, at: tuple, strength: int = 10, 
                          supply: int = 100) -> 'ArmyFixed':
        """Enhanced army creation with proper checks."""
        q, r = at
        
        # Check if civ exists
        if civ_id not in engine.world.civs:
            raise ValueError("Unknown civ")
        
        civ = engine.world.civs[civ_id]
        
        # Check settlement
        tile = engine.world.get_tile(q, r)
        if tile.owner != civ_id:
            raise ValueError("Can only create armies in owned territory")
        
        # Check if there's a settlement that can recruit
        can_recruit = False
        if hasattr(tile, 'settlement') and tile.settlement >= 1:  # Village or better
            can_recruit = True
        
        if not can_recruit:
            raise ValueError("Need at least a village to recruit armies")
        
        # Check food economy
        if not engine.military_economy.can_afford_army(civ_id, strength, engine.world):
            raise ValueError("Cannot afford army (insufficient food/manpower)")
        
        # Check manpower from cohorts
        cohorts = engine.cohort_state.get_tile_cohorts(q, r)
        available = cohorts.military_age_males()
        if available < strength * 0.5:  # Need at least half from local pop
            raise ValueError("Insufficient military-age population")
        
        # Remove from cohorts
        recruited = engine.cohort_state.apply_army_recruitment(q, r, strength)
        
        # Create enhanced army
        army = ArmyFixed(
            civ_id=civ_id,
            q=q,
            r=r,
            strength=recruited,
            supply=supply,
            max_supply=supply,
            last_supplied_turn=engine.world.turn,
            maintenance_cost_paid=True
        )
        
        # Add to world
        engine.world.armies.append(army)
        civ.armies.append(army)
        
        # Track manpower
        engine.manpower_manager.allocate_manpower(civ_id, recruited)
        civ.manpower_used = engine.manpower_manager.get_civ_manpower_used(civ_id)
        
        # Pay cost
        engine.military_economy.pay_army_creation_cost(civ_id, recruited)
        
        return army
    
    engine.add_army = enhanced_add_army


def _patch_save_load(engine) -> None:
    """Patch save/load to include new systems."""
    original_save = engine.save_json
    original_load = engine.load_json
    
    def enhanced_save_json(path: str) -> None:
        """Save with all new systems."""
        # Call original save
        original_save(path)
        
        # Load the JSON and add our data
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Add new system states
        data['cohort_state'] = engine.cohort_state.save_state()
        data['military_economy'] = engine.military_economy.save_state()
        data['settlement_military'] = engine.settlement_military.save_state()
        data['manpower_manager'] = {
            'allocated': dict(engine.manpower_manager.civ_manpower_allocated),
            'lost': dict(engine.manpower_manager.civ_manpower_lost)
        }
        
        # Convert armies to enhanced format
        enhanced_armies = []
        for army in engine.world.armies:
            if hasattr(army, 'to_dict'):
                enhanced_armies.append(army.to_dict())
            else:
                # Fallback for old armies
                enhanced_armies.append({
                    "civ_id": army.civ_id,
                    "q": army.q,
                    "r": army.r,
                    "strength": army.strength,
                    "target": army.target,
                    "supply": army.supply,
                    "max_supply": 100,
                    "movement_accumulator": 0.0,
                    "last_supplied_turn": 0,
                    "maintenance_cost_paid": True
                })
        data['armies'] = enhanced_armies
        
        # Save back
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def enhanced_load_json(path: str) -> None:
        """Load with all new systems."""
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Call original load
        original_load(path)
        
        # Load new system states
        if 'cohort_state' in data:
            engine.cohort_state.load_state(data['cohort_state'])
        else:
            # Initialize from pop map if no cohort data
            _initialize_cohorts(engine)
        
        if 'military_economy' in data:
            engine.military_economy.load_state(data['military_economy'])
        
        if 'settlement_military' in data:
            engine.settlement_military.load_state(data['settlement_military'])
        
        if 'manpower_manager' in data:
            mm_data = data['manpower_manager']
            engine.manpower_manager.civ_manpower_allocated = mm_data.get('allocated', {})
            engine.manpower_manager.civ_manpower_lost = mm_data.get('lost', {})
        
        # Upgrade armies to enhanced format
        enhanced_armies = []
        for army_data in data.get('armies', []):
            if isinstance(army_data, dict) and 'movement_accumulator' in army_data:
                # Already enhanced
                army = ArmyFixed.from_dict(army_data)
            else:
                # Upgrade old format
                army = ArmyFixed(
                    civ_id=army_data['civ_id'],
                    q=army_data['q'],
                    r=army_data['r'],
                    strength=army_data.get('strength', 10),
                    target=army_data.get('target'),
                    supply=army_data.get('supply', 100),
                    max_supply=100,
                    movement_accumulator=0.0,
                    last_supplied_turn=0,
                    maintenance_cost_paid=True
                )
            enhanced_armies.append(army)
        
        engine.world.armies = enhanced_armies
        synchronize_army_lists(engine.world)
    
    engine.save_json = enhanced_save_json
    engine.load_json = enhanced_load_json


def _calculate_war_pressure(world) -> np.ndarray:
    """Calculate war pressure map based on army positions and battles."""
    h, w = world.height_hex, world.width_hex
    pressure = np.zeros((h, w), dtype=np.float32)
    
    # Add pressure from armies
    for army in world.armies:
        if 0 <= army.r < h and 0 <= army.q < w:
            pressure[army.r, army.q] += army.strength / 100.0
            
            # Spread pressure to neighbors
            for dq in range(-2, 3):
                for dr in range(-2, 3):
                    nq, nr = army.q + dq, army.r + dr
                    if 0 <= nr < h and 0 <= nq < w:
                        dist = max(abs(dq), abs(dr))
                        if dist > 0:
                            pressure[nr, nq] += (army.strength / 100.0) / (dist + 1)
    
    return np.clip(pressure, 0, 1)


def _get_food_map(world) -> np.ndarray:
    """Get food yield map for the world."""
    h, w = world.height_hex, world.width_hex
    food_map = np.zeros((h, w), dtype=np.float32)
    
    for tile in world.tiles:
        # Use actual yields_for if available
        try:
            from resources import yields_for
            food, _ = yields_for(tile)
        except:
            # Fallback
            biome_food = {"grass": 1.0, "coast": 0.8, "mountain": 0.1, 
                         "ocean": 0.2, "desert": 0.2}
            food = biome_food.get(tile.biome, 0.5)
        
        food_map[tile.r, tile.q] = food
    
    return food_map


def _get_capacity_map(world) -> np.ndarray:
    """Get carrying capacity map for the world."""
    food_map = _get_food_map(world)
    # Simple capacity = food * 100
    return food_map * 100


# Convenience function for testing
def test_integration():
    """Test the integration with a simple scenario."""
    from engine import SimulationEngine
    
    print("Creating engine...")
    engine = SimulationEngine(width=20, height=20, seed=12345)
    
    print("Applying fixes...")
    apply_all_fixes(engine)
    
    print("Adding civilizations...")
    civ1 = engine.add_civ("Rome", (5, 5))
    civ2 = engine.add_civ("Carthage", (15, 15))
    
    # Set up some initial population and settlements
    for tile in engine.world.tiles:
        if tile.owner is not None:
            tile.pop = 100
            tile.settlement = 2  # Town
    
    # Initialize food reserves
    engine.military_economy.food_reserves[civ1] = 1000
    engine.military_economy.food_reserves[civ2] = 1000
    
    print("Creating armies...")
    try:
        # This will now check all requirements
        army1 = engine.add_army(civ1, (5, 5), strength=20)
        print(f"Created army with {army1.strength} soldiers")
    except ValueError as e:
        print(f"Army creation failed: {e}")
    
    print("Advancing turns...")
    for i in range(10):
        engine.advance_turn()
        if i % 5 == 0:
            civ = engine.world.civs[civ1]
            print(f"Turn {engine.world.turn}: "
                  f"Civ pop: {sum(engine.world.get_tile(q,r).pop for q,r in civ.tiles)}, "
                  f"Food: {engine.military_economy.food_reserves.get(civ1, 0):.1f}, "
                  f"Manpower: {civ.manpower_used}/{civ.manpower_limit}")
    
    print("\nIntegration test complete!")
    return engine


if __name__ == "__main__":
    test_integration()
