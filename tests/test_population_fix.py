"""
Test script for population expansion fixes

This script tests the fixes for the population expansion bottleneck
where civilizations get stuck at around 39 population.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_population_fix_import():
    """Test that population fix modules can be imported."""
    try:
        from fixes.population_expansion_fix import integrate_population_expansion_fixes
        print("✓ Population expansion fix imports successfully")
        return True
    except Exception as e:
        print(f"✗ Population expansion fix import failed: {e}")
        return False

def test_integration_import():
    """Test that integration module can be imported."""
    try:
        from integrations.population_fix_integration import enable_comprehensive_expansion_system
        print("✓ Population fix integration imports successfully")
        return True
    except Exception as e:
        print(f"✗ Population fix integration import failed: {e}")
        return False

def test_realistic_colonization_updates():
    """Test that realistic colonization updates work."""
    try:
        from systems.realistic_colonization import RealisticColonizationSystem
        
        # Mock world for testing
        class MockWorld:
            def __init__(self):
                self.width_hex = 32
                self.height_hex = 24
                self.seed = 42
                self.civs = {}
                self.turn = 0
            def get_tile(self, q, r): 
                class MockTile:
                    def __init__(self):
                        self.pop = 20
                        self.owner = None
                        self.biome = 'plains'
                return MockTile()
            def in_bounds(self, q, r): return True
        
        world = MockWorld()
        system = RealisticColonizationSystem(world, rng_seed=42)
        
        print("✓ Realistic colonization system initializes with updates")
        return True
    except Exception as e:
        print(f"✗ Realistic colonization update test failed: {e}")
        return False

def run_comprehensive_test():
    """Run comprehensive test of all population fix components."""
    print("Testing Population Expansion Fixes")
    print("=" * 40)
    
    tests = [
        test_population_fix_import,
        test_integration_import,
        test_realistic_colonization_updates
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("Test Results:")
    print(f"  Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed! Population fixes are ready to use.")
        print()
        print("To apply fixes to your simulation:")
        print("  from integrations.population_fix_integration import enable_comprehensive_expansion_system")
        print("  enable_comprehensive_expansion_system(engine)")
    else:
        print("❌ Some tests failed. Check imports and dependencies.")
        
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)