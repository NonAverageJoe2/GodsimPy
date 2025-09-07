"""
Tests for the Realistic Colonization System

Tests the core functionality of realistic colonization patterns,
culture spawning, and configuration management.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from systems.realistic_colonization import RealisticColonizationSystem, ColonizationContext
from integrations.realistic_colonization_integration import enable_realistic_colonization


class MockTile:
    """Mock tile for testing."""
    def __init__(self, q, r, biome='plains', pop=0, owner=None, feature=None):
        self.q = q
        self.r = r
        self.biome = biome
        self.pop = pop
        self.owner = owner
        self.feature = feature


class MockCiv:
    """Mock civilization for testing."""
    def __init__(self, civ_id, name="Test Civ", tiles=None, stock_food=100):
        self.civ_id = civ_id
        self.name = name
        self.tiles = tiles or []
        self.stock_food = stock_food
        self.capital = None
        self.main_culture = "Test Culture"
        self.linguistic_type = "latin"


class MockWorld:
    """Mock world for testing."""
    def __init__(self, width=32, height=24):
        self.width_hex = width
        self.height_hex = height
        self.seed = 42
        self.turn = 0
        self.civs = {}
        self.tiles = {}
        
        # Initialize empty tiles
        for q in range(width):
            for r in range(height):
                self.tiles[(q, r)] = MockTile(q, r)
    
    def get_tile(self, q, r):
        return self.tiles.get((q, r))
    
    def in_bounds(self, q, r):
        return 0 <= q < self.width_hex and 0 <= r < self.height_hex
    
    def distance(self, q1, r1, q2, r2):
        return max(abs(q1 - q2), abs(r1 - r2))  # Chebyshev distance


class TestRealisticColonizationSystem(unittest.TestCase):
    """Test the realistic colonization system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.world = MockWorld()
        self.system = RealisticColonizationSystem(self.world, rng_seed=42)
        
        # Add a test civilization
        civ = MockCiv(0, "Test Empire", tiles=[(15, 12)], stock_food=200)
        self.world.civs[0] = civ
        
        # Set up the tile with some population
        tile = self.world.get_tile(15, 12)
        tile.pop = 50
        tile.owner = 0
    
    def test_terrain_difficulty_calculation(self):
        """Test terrain difficulty modifier calculation."""
        # Test known terrain types
        self.assertEqual(self.system.get_terrain_difficulty('plains'), 1.0)
        self.assertEqual(self.system.get_terrain_difficulty('ocean'), 0.0)
        self.assertGreater(self.system.get_terrain_difficulty('forest'), 0.5)
        
        # Test unknown terrain (should use default)
        self.assertEqual(self.system.get_terrain_difficulty('unknown'), 0.5)
    
    def test_distance_decay_calculation(self):
        """Test distance decay factor calculation."""
        # Distance 0 should be full strength
        self.assertEqual(self.system.calculate_distance_decay(0), 1.0)
        
        # Distance should decrease with range
        decay1 = self.system.calculate_distance_decay(1)
        decay2 = self.system.calculate_distance_decay(2) 
        self.assertGreater(decay1, decay2)
        self.assertGreater(decay1, 0.0)
        self.assertGreater(decay2, 0.0)
    
    def test_colonization_viability_assessment(self):
        """Test colonization viability scoring."""
        context = ColonizationContext(
            source_tile=(15, 12),
            target_tile=(16, 12),  # Adjacent tile
            civ_id=0,
            distance=1,
            terrain_difficulty=0.0,
            resource_value=0.0,
            strategic_value=0.0,
            cultural_compatibility=1.0,
            population_pressure=2.0
        )
        
        # Viability should be positive for good targets
        viability = self.system.assess_colonization_viability(context)
        self.assertGreater(viability, 0.0)
        self.assertLessEqual(viability, 1.0)
    
    def test_colonization_target_finding(self):
        """Test finding colonization targets."""
        targets = self.system.find_colonization_targets(0)
        
        # Should find some targets around the populated tile
        self.assertGreater(len(targets), 0)
        
        # All targets should be valid format: ((source_q, source_r), (target_q, target_r), score)
        for target in targets:
            self.assertEqual(len(target), 3)
            source_pos, target_pos, score = target
            self.assertEqual(len(source_pos), 2)
            self.assertEqual(len(target_pos), 2)
            self.assertIsInstance(score, float)
            self.assertGreater(score, 0.0)
    
    def test_culture_spawn_candidate_identification(self):
        """Test identification of culture spawn candidates."""
        # Add some unowned populated tiles
        for i in range(3):
            tile = self.world.get_tile(5 + i, 5)
            tile.pop = 20 + i * 5
            tile.owner = None  # Unowned
        
        candidates = self.system.identify_culture_spawn_candidates()
        
        # Should find the isolated populated areas
        self.assertGreater(len(candidates), 0)
        
        # Check format: (q, r, score)
        for candidate in candidates:
            self.assertEqual(len(candidate), 3)
            q, r, score = candidate
            self.assertIsInstance(q, int)
            self.assertIsInstance(r, int) 
            self.assertIsInstance(score, float)
            self.assertGreater(score, 0.0)
    
    def test_configuration_loading(self):
        """Test configuration loading and fallback."""
        # System should load configuration successfully or use defaults
        self.assertIsInstance(self.system.terrain_modifiers, dict)
        self.assertIsInstance(self.system.base_colonization_range, int)
        self.assertIsInstance(self.system.culture_spawn_probability, float)
        
        # Key terrain modifiers should exist
        self.assertIn('plains', self.system.terrain_modifiers)
        self.assertIn('ocean', self.system.terrain_modifiers)
    
    @patch('systems.realistic_colonization.yields_for')
    def test_colonization_with_resource_system(self, mock_yields):
        """Test colonization when resource system is available."""
        # Mock the yields_for function
        mock_yields.return_value = (5.0, 3.0)  # food, production
        
        context = ColonizationContext(
            source_tile=(15, 12),
            target_tile=(16, 12),
            civ_id=0,
            distance=1,
            terrain_difficulty=0.0,
            resource_value=0.0,
            strategic_value=0.0,
            cultural_compatibility=1.0,
            population_pressure=2.0
        )
        
        viability = self.system.assess_colonization_viability(context)
        self.assertGreater(viability, 0.0)
        mock_yields.assert_called()
    
    def test_process_turn_integration(self):
        """Test the complete turn processing."""
        initial_civs = len(self.world.civs)
        initial_tiles = len(self.world.civs[0].tiles)
        
        # Run several turns
        for turn in range(10):
            self.world.turn = turn
            self.system.process_turn(turn, 1.0/52.0)
        
        # System should have attempted expansions (may or may not succeed)
        # This is a basic integration test - specific outcomes depend on RNG
        self.assertGreaterEqual(len(self.world.civs), initial_civs)


class TestIntegrationModule(unittest.TestCase):
    """Test the integration module functionality."""
    
    def setUp(self):
        """Set up test fixtures.""" 
        self.mock_engine = MagicMock()
        self.mock_engine.world = MockWorld()
        self.mock_engine.world.civs = {0: MockCiv(0)}
    
    def test_enable_realistic_colonization(self):
        """Test enabling the realistic colonization system.""" 
        # Test enabling
        enable_realistic_colonization(self.mock_engine, enabled=True)
        
        # Should have added the system
        self.assertTrue(hasattr(self.mock_engine, 'realistic_colonization'))
        
        # Test disabling
        enable_realistic_colonization(self.mock_engine, enabled=False) 
        
        # Should have removed the system
        self.assertFalse(hasattr(self.mock_engine, 'realistic_colonization'))


if __name__ == '__main__':
    # Create test directories if they don't exist
    os.makedirs('examples', exist_ok=True)
    
    # Run tests
    unittest.main(verbosity=2)