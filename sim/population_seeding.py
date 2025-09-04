"""Population seeding for empty provinces in civilization simulation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def generate_population_weights() -> NDArray[np.float32]:
    """Generate probability weights for population values 0-10.
    
    50% chance for 0 population, remaining 50% distributed among 1-10
    with 10 being the least likely.
    
    Returns:
        Array of 11 weights corresponding to population values 0-10
    """
    # Start with 50% weight for 0 population
    weights = np.zeros(11, dtype=np.float32)
    weights[0] = 0.5  # 50% chance for 0 population
    
    # Remaining 50% distributed exponentially among 1-10 (10 being least likely)
    remaining_weight = 0.5
    decay_weights = np.array([0.9 ** i for i in range(10)], dtype=np.float32)  # Exponential decay
    decay_weights = decay_weights / np.sum(decay_weights)  # Normalize to sum to 1
    weights[1:] = decay_weights * remaining_weight  # Scale to use remaining 50%
    
    return weights


def seed_empty_provinces(owner_map: NDArray[np.int32], 
                        pop_map: NDArray[np.float32],
                        biome_map: NDArray[np.uint8],
                        seed: int = 0) -> NDArray[np.float32]:
    """Seed empty provinces with small amounts of population.
    
    Args:
        owner_map: Territory ownership (-1 = unowned)
        pop_map: Current population map
        biome_map: Biome types (used to exclude ocean/mountains)
        seed: Random seed for reproducible generation
        
    Returns:
        Updated population map with seeded values
    """
    rng = np.random.default_rng(seed)
    h, w = owner_map.shape
    result_pop = pop_map.copy()
    
    # Generate population weights (0 most likely, 10 least likely)
    weights = generate_population_weights()
    population_values = np.arange(11, dtype=np.float32)  # [0, 1, 2, ..., 10]
    
    # Find all empty, habitable tiles
    empty_mask = (owner_map < 0) & (pop_map <= 0.1)  # Unowned and essentially unpopulated
    habitable_mask = ~np.isin(biome_map, [2, 3])  # Not mountains (2) or ocean (3)
    seedable_mask = empty_mask & habitable_mask
    
    # Get coordinates of all seedable tiles
    seedable_coords = np.argwhere(seedable_mask)
    
    if len(seedable_coords) == 0:
        return result_pop  # No tiles to seed
    
    # Generate random population values for all seedable tiles at once
    # Use weighted random choice based on our probability distribution
    num_tiles = len(seedable_coords)
    seeded_populations = rng.choice(
        population_values, 
        size=num_tiles, 
        p=weights
    )
    
    # Apply the seeded population to each tile
    for i, (r, c) in enumerate(seedable_coords):
        result_pop[r, c] = seeded_populations[i]
    
    return result_pop


def get_population_distribution_info(weights: NDArray[np.float32]) -> str:
    """Get human-readable info about population distribution probabilities.
    
    Useful for debugging and configuration verification.
    """
    info_lines = ["Population seeding distribution:"]
    for pop_val in range(11):
        percentage = weights[pop_val] * 100
        info_lines.append(f"  Pop {pop_val}: {percentage:.1f}%")
    return "\n".join(info_lines)


def apply_natural_variation(pop_map: NDArray[np.float32],
                           owner_map: NDArray[np.int32],
                           variation_factor: float = 0.1,
                           seed: int = 0) -> NDArray[np.float32]:
    """Apply small random variations to empty province populations.
    
    This can be called periodically to make empty areas feel more dynamic.
    
    Args:
        pop_map: Current population map
        owner_map: Territory ownership
        variation_factor: How much variation to apply (0.0 to 1.0)
        seed: Random seed
        
    Returns:
        Population map with small random variations applied
    """
    rng = np.random.default_rng(seed)
    result_pop = pop_map.copy()
    
    # Only apply variation to empty territories with some population
    variation_mask = (owner_map < 0) & (pop_map > 0.1) & (pop_map <= 10)
    
    if not np.any(variation_mask):
        return result_pop
    
    # Generate small random variations (-variation_factor to +variation_factor)
    variation_coords = np.argwhere(variation_mask)
    for r, c in variation_coords:
        current_pop = result_pop[r, c]
        
        # Apply random variation (can increase or decrease)
        variation = rng.uniform(-variation_factor, variation_factor) * current_pop
        new_pop = current_pop + variation
        
        # Keep within bounds [0, 10]
        new_pop = np.clip(new_pop, 0.0, 10.0)
        result_pop[r, c] = new_pop
    
    return result_pop