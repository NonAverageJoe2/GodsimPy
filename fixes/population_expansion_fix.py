"""
Fix for Population Expansion Bottleneck

This fix addresses the issue where civilizations get stuck at around 39 population
and stop expanding due to food capacity limitations creating a feedback loop.

The core problem:
1. Population growth is limited by food capacity (from workforce system)
2. Food capacity depends on having enough farmers (~60% of population)
3. At ~39 population, food capacity becomes limiting, creating a population ceiling
4. Without population growth, expansion thresholds are never met
5. Without expansion, civilizations can't acquire more agricultural land

The fix:
1. Adjusts expansion thresholds to be more dynamic based on food capacity
2. Allows food-motivated expansion (expanding to get more farmland)
3. Provides alternative expansion triggers when population is food-limited
4. Balances the food system to allow sustainable growth
"""

from __future__ import annotations
from typing import Any, Dict, Tuple, List, Optional


def apply_population_expansion_fix(engine: Any) -> None:
    """Apply the population expansion fix to the engine."""
    
    # Store original methods
    if not hasattr(engine, '_original_colonization_pass'):
        engine._original_colonization_pass = engine._colonization_pass_with_tech
    
    def enhanced_colonization_pass_with_tech():
        """Enhanced colonization that handles food-limited populations."""
        w = engine.world
        
        # Dynamic thresholds based on food situation
        actions: List[Tuple[int, Tuple[int, int], Tuple[int, int]]] = []
        claimed: set[Tuple[int, int]] = set()

        for cid in sorted(w.civs.keys()):
            civ = w.civs[cid]
            
            # Get current food situation for this civilization
            total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
            if total_pop == 0:
                continue
            
            # Calculate food capacity using workforce system
            try:
                from workforce import WORKFORCE_SYSTEM
                food_production, food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(
                    civ, w, None
                )
            except:
                food_production, food_capacity = total_pop * 1.2, total_pop * 1.5
            
            # Determine expansion motivation and thresholds
            food_pressure_ratio = total_pop / max(food_capacity, 1.0)
            is_food_limited = food_pressure_ratio > 0.8  # Close to food capacity limit
            
            # Dynamic thresholds based on situation
            if is_food_limited:
                # Food-motivated expansion: lower population threshold, higher food requirement
                POP_THRESHOLD = max(8, total_pop * 0.15)  # 15% of total population per tile
                FOOD_COST = max(10, int(food_production * 0.1))  # 10% of food production
                SETTLER_COST = max(3, min(8, int(total_pop * 0.1)))  # 10% of population
                expansion_motivation = "food_seeking"
            else:
                # Normal expansion: standard thresholds
                POP_THRESHOLD = 15
                FOOD_COST = 5
                SETTLER_COST = 5
                expansion_motivation = "normal"
            
            # Check if civ can afford expansion
            if civ.stock_food < FOOD_COST:
                continue
            
            # Technology bonuses
            expansion_bonus = 0.0
            if hasattr(engine, 'tech_system') and cid in engine.tech_system.civ_states:
                bonuses = engine.tech_system.get_civ_bonuses(cid)
                expansion_bonus = bonuses.territory_expansion_rate
                
            final_pop_threshold = POP_THRESHOLD * (1 - 0.3 * expansion_bonus)
            
            # Limit expansions per turn - increased for 5000+ year simulations
            max_expansions = 2 if is_food_limited else max(3, min(8, len(civ.tiles) // 5))
            expansions_this_turn = 0
            
            # Find expansion targets
            potential_targets = []
            
            for (q, r) in civ.tiles:
                source_tile = w.get_tile(q, r)
                
                # Check if this tile can support expansion
                can_expand = False
                if is_food_limited:
                    # Food-limited: any tile with reasonable population can expand
                    can_expand = source_tile.pop >= max(5, final_pop_threshold * 0.5)
                else:
                    # Normal: use standard threshold
                    can_expand = source_tile.pop >= final_pop_threshold
                
                if not can_expand:
                    continue
                
                # Look for adjacent expansion targets
                for nq, nr in w.neighbors6(q, r):
                    if (nq, nr) in claimed:
                        continue
                        
                    target_tile = w.get_tile(nq, nr)
                    if not target_tile or target_tile.owner is not None:
                        continue
                        
                    # Skip ocean tiles
                    if getattr(target_tile, 'biome', None) == 'ocean':
                        continue
                    
                    # Score the target based on expansion motivation
                    score = _score_expansion_target(
                        source_tile, target_tile, expansion_motivation
                    )

                    potential_targets.append(((q, r), (nq, nr), score))

            # Sort and select best targets
            potential_targets.sort(key=lambda x: x[2], reverse=True)

            best_score = potential_targets[0][2] if potential_targets else None
            if potential_targets and best_score is not None and best_score <= 0:
                (sq, sr), (dq, dr), _ = potential_targets[0]
                potential_targets[0] = ((sq, sr), (dq, dr), 0.1)

            for (sq, sr), (dq, dr), score in potential_targets[:max_expansions]:
                if (dq, dr) not in claimed and score > 0:
                    actions.append((cid, (sq, sr), (dq, dr)))
                    claimed.add((dq, dr))
                    expansions_this_turn += 1

                    # Debug output
                    if w.turn % 50 == 0:
                        print(f"[Expansion] Civ {cid} ({expansion_motivation}): {source_tile.pop} -> new colony (food ratio: {food_pressure_ratio:.2f})")
                        if best_score is not None:
                            print(f"  Best target: score {best_score:.2f}")
                            if best_score <= 0:
                                print("  Fallback applied to allow expansion")
        
        # Execute expansions
        for cid, (sq, sr), (dq, dr) in actions:
            source_tile = w.get_tile(sq, sr)
            target_tile = w.get_tile(dq, dr)
            civ = w.civs[cid]
            
            # Calculate costs based on motivation
            total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
            food_pressure_ratio = total_pop / max(1, total_pop * 1.0)  # Simplified check
            
            if food_pressure_ratio > 0.8:
                FOOD_COST = max(10, civ.stock_food // 10)
                SETTLER_COST = max(3, min(8, source_tile.pop // 5))
            else:
                FOOD_COST = 5
                SETTLER_COST = 5
            
            # Execute expansion
            civ.stock_food = max(0, civ.stock_food - FOOD_COST)
            source_tile.pop = max(1, source_tile.pop - SETTLER_COST)  # Never completely depopulate
            source_tile._pop_float = float(source_tile.pop)
            
            target_tile.owner = cid
            target_tile.pop = SETTLER_COST
            target_tile._pop_float = float(SETTLER_COST)
            
            civ.tiles.append((dq, dr))
    
    # Replace the method
    engine._colonization_pass_with_tech = enhanced_colonization_pass_with_tech


def _score_expansion_target(source_tile, target_tile, motivation: str) -> float:
    """Score an expansion target based on the motivation for expansion."""
    
    if motivation == "food_seeking":
        # Prioritize agricultural potential
        biome_scores = {
            'grassland': 1.0,
            'plains': 0.9, 
            'forest': 0.7,
            'hills': 0.6,
            'coast': 0.8,
            'desert': 0.2,
            'mountain': 0.1,
            'tundra': 0.3,
            'swamp': 0.4
        }
        
        biome_score = biome_scores.get(target_tile.biome, 0.5)
        
        # Bonus for river access (better farming)
        river_bonus = 0.3 if hasattr(target_tile, 'feature') and target_tile.feature and 'river' in target_tile.feature.lower() else 0.0
        
        return biome_score + river_bonus
    
    else:
        # Normal expansion - balanced scoring
        try:
            from resources import yields_for
            food_yield, prod_yield = yields_for(target_tile)
            return (food_yield * 2.0 + prod_yield) / 10.0
        except:
            # Fallback scoring
            biome_scores = {
                'grassland': 0.8,
                'plains': 0.7,
                'forest': 0.6,
                'hills': 0.5,
                'coast': 0.6,
                'desert': 0.2,
                'mountain': 0.1
            }
            return biome_scores.get(target_tile.biome, 0.4)


def apply_food_system_balance_fix(engine: Any) -> None:
    """Apply balancing fixes to the food system to prevent hard population caps."""
    
    # Store original method
    if not hasattr(engine, '_original_advance_pop'):
        engine._original_advance_pop = engine._advance_population_with_tech
    
    def balanced_advance_population_with_tech(dt: float = 1.0 / 52.0):
        """Enhanced population advancement that prevents hard food caps."""
        w = engine.world
        
        # Get civilization food data
        civ_food_data: Dict[int, Tuple[float, float]] = {}
        
        for cid, civ in w.civs.items():
            total_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
            
            # Calculate food capacity with some baseline bonus
            try:
                from workforce import WORKFORCE_SYSTEM
                food_production, raw_food_capacity = WORKFORCE_SYSTEM.calculate_civ_food_production(
                    civ, w, None
                )
                
                # Add baseline subsistence bonus to prevent hard caps
                # This represents foraging, hunting, and basic subsistence activities
                subsistence_bonus = total_pop * 0.3  # 30% subsistence bonus
                food_capacity = raw_food_capacity + subsistence_bonus
                
            except Exception:
                # Fallback calculation
                food_production = total_pop * 1.2
                food_capacity = total_pop * 1.4
            
            civ_food_data[cid] = (food_production, food_capacity)
            
            # Add food to stockpile
            max_food = max(1000, len(civ.tiles) * 200)
            civ.stock_food = max(0, min(civ.stock_food + int(food_production * dt), max_food))
        
        # Enhanced population growth with smoother food limitations
        for t in w.tiles:
            if t.owner is None:
                continue
                
            food_production, food_capacity = civ_food_data.get(t.owner, (0.0, 50.0))
            civ = w.civs[t.owner]
            total_civ_pop = sum(w.get_tile(q, r).pop for q, r in civ.tiles)
            
            # Technology bonuses
            growth_bonus = 0.0
            if hasattr(engine, 'tech_system') and t.owner in engine.tech_system.civ_states:
                bonuses = engine.tech_system.get_civ_bonuses(t.owner)
                growth_bonus = bonuses.population_growth_rate
            
            # Terrain-based carrying capacity
            try:
                from resources import yields_for
                food_yield, _ = yields_for(t)
                terrain_multiplier = max(0.5, food_yield / 2.0)
            except:
                terrain_multiplier = 1.0
            
            # Base growth rate
            from modifiers import MODIFIERS
            R = MODIFIERS.base_population_growth_rate
            
            # Calculate effective carrying capacity for this tile
            if food_capacity > 0 and total_civ_pop > 0:
                base_share = food_capacity / len(civ.tiles)
                K_eff = max(15.0, base_share * terrain_multiplier)  # Higher minimum
            else:
                K_eff = 50.0 * terrain_multiplier
            
            # Smooth starvation system (no hard death, just reduced growth)
            food_pressure = total_civ_pop / max(1, food_capacity)
            if food_pressure > 1.0:
                # Gradual slowdown instead of death
                starvation_factor = max(0.1, 1.0 / (1.0 + (food_pressure - 1.0) * 0.5))
            else:
                starvation_factor = 1.0
            
            # Apply logistic growth with smooth food pressure
            actual_growth_rate = (R + growth_bonus) * starvation_factor
            
            if t._pop_float > 0:
                ratio = (K_eff - t._pop_float) / t._pop_float
                t._pop_float = K_eff / (1.0 + ratio * math.exp(-actual_growth_rate * dt))
            
            # Update integer population
            import math
            pop_int = max(0, min(1000, math.floor(t._pop_float)))
            object.__setattr__(t, 'pop', pop_int)
    
    # Replace the method
    engine._advance_population_with_tech = balanced_advance_population_with_tech


def integrate_population_expansion_fixes(engine: Any) -> None:
    """Integrate all population expansion fixes with the engine."""
    try:
        apply_population_expansion_fix(engine)
        apply_food_system_balance_fix(engine)
        print("✓ Population expansion fixes applied successfully")
    except Exception as e:
        print(f"✗ Error applying population fixes: {e}")


def remove_population_expansion_fixes(engine: Any) -> None:
    """Remove population expansion fixes and restore original behavior."""
    if hasattr(engine, '_original_colonization_pass'):
        engine._colonization_pass_with_tech = engine._original_colonization_pass
        delattr(engine, '_original_colonization_pass')
    
    if hasattr(engine, '_original_advance_pop'):
        engine._advance_population_with_tech = engine._original_advance_pop
        delattr(engine, '_original_advance_pop')
    
    print("Population expansion fixes removed")