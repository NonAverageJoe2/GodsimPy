#!/usr/bin/env python3
"""
Demo script for the Realistic Colonization System

This script demonstrates how to enable and use the realistic colonization
and culture spawning features in GodsimPy.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import SimulationEngine
from worldgen import build_world  
from integrations.realistic_colonization_integration import (
    enable_realistic_colonization,
    get_colonization_stats,
    update_colonization_config
)


def create_demo_world():
    """Create a demo world with some initial civilizations."""
    print("Creating demo world...")
    
    # Generate world
    world_config = {
        'width': 64,
        'height': 48,  
        'seed': 12345,
        'n_civs': 3
    }
    
    world = build_world(
        width_hex=world_config['width'],
        height_hex=world_config['height'], 
        seed=world_config['seed']
    )
    
    # Initialize engine
    engine = SimulationEngine(world)
    
    # Add some initial civilizations if not already present
    if len(engine.world.civs) == 0:
        # Spawn a few civs manually for demo
        engine.spawn_civ((20, 15))  # Central location
        engine.spawn_civ((10, 30))  # Southwest
        engine.spawn_civ((45, 20))  # East
    
    return engine


def run_colonization_demo(turns: int = 200):
    """Run a colonization demo for the specified number of turns."""
    engine = create_demo_world()
    
    print(f"Initial world state:")
    print(f"- World size: {engine.world.width_hex} x {engine.world.height_hex}")
    print(f"- Civilizations: {len(engine.world.civs)}")
    
    # Enable realistic colonization
    enable_realistic_colonization(engine, enabled=True)
    
    # Adjust parameters for demo (faster expansion)
    config_updates = {
        "colonization": {
            "base_colonization_range": 4,
            "expansion_attempt_probability": 0.25,
            "population_pressure_threshold": 20
        },
        "culture_spawning": {
            "spawn_interval_turns": 50,  # Spawn cultures more frequently
            "base_spawn_probability": 0.3,
            "isolation_threshold_hexes": 4
        }
    }
    
    update_colonization_config(engine, config_updates)
    print("✓ Realistic colonization system configured for demo")
    
    # Run simulation
    print(f"\nRunning simulation for {turns} turns...")
    print("Turn | Civs | Total Tiles | New Cultures")
    print("-" * 45)
    
    initial_civs = len(engine.world.civs)
    
    for turn in range(turns):
        engine.step()
        
        # Print status every 25 turns
        if turn % 25 == 0:
            stats = get_colonization_stats(engine)
            total_tiles = sum(len(civ.tiles) for civ in engine.world.civs.values())
            new_cultures = len(engine.world.civs) - initial_civs
            
            print(f"{turn:4d} | {len(engine.world.civs):4d} | {total_tiles:11d} | {new_cultures:12d}")
    
    # Final statistics
    print("\n" + "=" * 50)
    print("SIMULATION COMPLETE")
    print("=" * 50)
    
    final_stats = get_colonization_stats(engine)
    
    print(f"\nFinal Statistics:")
    print(f"- Total turns: {turns}")  
    print(f"- Total civilizations: {len(engine.world.civs)}")
    print(f"- New cultures spawned: {len(engine.world.civs) - initial_civs}")
    print(f"- Culture spawn candidates remaining: {final_stats['culture_spawn_candidates']}")
    
    print(f"\nCivilization Details:")
    for civ_id, civ_info in final_stats['civilization_stats'].items():
        print(f"  {civ_info['name']}:")
        print(f"    - Tiles controlled: {civ_info['tiles']}")
        print(f"    - Food stockpile: {civ_info['stock_food']}")
        print(f"    - Expansion targets: {civ_info['potential_targets']}")
        if civ_info['best_target_score'] > 0:
            print(f"    - Best target score: {civ_info['best_target_score']:.3f}")
    
    return engine, final_stats


def interactive_demo():
    """Run an interactive demonstration."""
    print("=== Realistic Colonization System Demo ===")
    print()
    
    while True:
        print("Choose an option:")
        print("1. Quick demo (50 turns)")
        print("2. Medium demo (200 turns)")  
        print("3. Long demo (500 turns)")
        print("4. Custom demo")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            run_colonization_demo(50)
        elif choice == '2':
            run_colonization_demo(200)
        elif choice == '3':
            run_colonization_demo(500)
        elif choice == '4':
            try:
                turns = int(input("Enter number of turns: "))
                run_colonization_demo(turns)
            except ValueError:
                print("Invalid input. Please enter a number.")
        elif choice == '5':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please select 1-5.")
        
        print("\n" + "-" * 50 + "\n")


if __name__ == "__main__":
    try:
        interactive_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nError running demo: {e}")
        import traceback
        traceback.print_exc()