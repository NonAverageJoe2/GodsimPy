"""
Integration module for the Realistic Colonization System

This module provides easy integration of the realistic colonization system
with the main GodsimPy engine, including GUI controls and save/load support.
"""

from typing import Any, Dict, Optional
import json
import os

def enable_realistic_colonization(engine: Any, enabled: bool = True) -> None:
    """Enable or disable the realistic colonization system."""
    if not enabled:
        # Restore original methods if disabling
        if hasattr(engine, '_original_step'):
            engine.step = engine._original_step
            delattr(engine, '_original_step')
        if hasattr(engine, 'realistic_colonization'):
            delattr(engine, 'realistic_colonization')
        return
    
    # Import and integrate the system
    try:
        from systems.realistic_colonization import integrate_realistic_colonization
        integrate_realistic_colonization(engine)
        print("✓ Realistic colonization system enabled")
    except Exception as e:
        print(f"✗ Failed to enable realistic colonization: {e}")


def get_colonization_stats(engine: Any) -> Dict[str, Any]:
    """Get statistics about colonization activity."""
    if not hasattr(engine, 'realistic_colonization'):
        return {"error": "Realistic colonization system not active"}
    
    system = engine.realistic_colonization
    
    # Calculate expansion potential for each civ
    civ_stats = {}
    for civ_id, civ in engine.world.civs.items():
        targets = system.find_colonization_targets(civ_id)
        viable_targets = [t for t in targets if t[2] > 0.1]  # Minimum viability threshold
        
        civ_stats[civ_id] = {
            "name": civ.name,
            "tiles": len(civ.tiles),
            "stock_food": civ.stock_food,
            "potential_targets": len(viable_targets),
            "best_target_score": viable_targets[0][2] if viable_targets else 0.0
        }
    
    # Culture spawn candidates
    spawn_candidates = system.identify_culture_spawn_candidates()
    
    return {
        "turn": engine.world.turn,
        "last_culture_spawn": system.last_culture_spawn_turn,
        "turns_until_next_spawn_attempt": max(0, system.culture_spawn_interval - (engine.world.turn - system.last_culture_spawn_turn)),
        "culture_spawn_candidates": len(spawn_candidates),
        "civilization_stats": civ_stats,
        "configuration": {
            "expansion_range": system.base_colonization_range,
            "culture_spawn_probability": system.culture_spawn_probability,
            "isolation_threshold": system.isolation_threshold
        }
    }


def update_colonization_config(engine: Any, config_updates: Dict[str, Any]) -> bool:
    """Update colonization configuration at runtime."""
    if not hasattr(engine, 'realistic_colonization'):
        return False
    
    system = engine.realistic_colonization
    
    try:
        # Update colonization parameters
        if 'colonization' in config_updates:
            col_config = config_updates['colonization']
            for key, value in col_config.items():
                if hasattr(system, key):
                    setattr(system, key, value)
        
        # Update terrain modifiers
        if 'terrain_modifiers' in config_updates:
            system.terrain_modifiers.update(config_updates['terrain_modifiers'])
        
        # Update strategic bonuses
        if 'strategic_bonuses' in config_updates:
            system.strategic_bonuses.update(config_updates['strategic_bonuses'])
        
        # Update culture spawning parameters
        if 'culture_spawning' in config_updates:
            spawn_config = config_updates['culture_spawning']
            for key, value in spawn_config.items():
                attr_name = key.replace('spawn_interval_turns', 'culture_spawn_interval')
                attr_name = attr_name.replace('isolation_threshold_hexes', 'isolation_threshold')
                attr_name = attr_name.replace('base_spawn_probability', 'culture_spawn_probability')
                if hasattr(system, attr_name):
                    setattr(system, attr_name, value)
        
        return True
    except Exception as e:
        print(f"Error updating colonization config: {e}")
        return False


def export_colonization_state(engine: Any) -> Dict:
    """Export colonization system state for saving."""
    if not hasattr(engine, 'realistic_colonization'):
        return {}
    
    system = engine.realistic_colonization
    return {
        "last_culture_spawn_turn": system.last_culture_spawn_turn,
        "culture_spawn_cooldown": system.culture_spawn_cooldown,
        "rng_state": system.rng.getstate()
    }


def import_colonization_state(engine: Any, data: Optional[Dict]) -> None:
    """Import colonization system state from save data."""
    if not data or not hasattr(engine, 'realistic_colonization'):
        return
    
    system = engine.realistic_colonization
    
    if 'last_culture_spawn_turn' in data:
        system.last_culture_spawn_turn = data['last_culture_spawn_turn']
    
    if 'culture_spawn_cooldown' in data:
        system.culture_spawn_cooldown = data['culture_spawn_cooldown']
    
    if 'rng_state' in data:
        try:
            system.rng.setstate(data['rng_state'])
        except Exception:
            pass  # Ignore RNG state restoration errors


# GUI Integration helpers
class ColonizationGUIPanel:
    """GUI panel for monitoring and controlling colonization."""
    
    def __init__(self, engine):
        self.engine = engine
        self.visible = False
        self.scroll_y = 0
        
    def toggle_visibility(self):
        """Toggle panel visibility."""
        self.visible = not self.visible
    
    def render_stats(self, surface, font, x: int, y: int) -> int:
        """Render colonization statistics to the GUI surface."""
        if not hasattr(self.engine, 'realistic_colonization'):
            text = font.render("Realistic colonization not active", True, (255, 255, 255))
            surface.blit(text, (x, y))
            return y + 25
        
        stats = get_colonization_stats(self.engine)
        current_y = y
        
        # Title
        title = font.render("Colonization Status", True, (255, 255, 0))
        surface.blit(title, (x, current_y))
        current_y += 30
        
        # Global stats
        global_info = [
            f"Turn: {stats['turn']}",
            f"Last culture spawn: {stats['last_culture_spawn']}",
            f"Next spawn attempt in: {stats['turns_until_next_spawn_attempt']} turns",
            f"Spawn candidates: {stats['culture_spawn_candidates']}"
        ]
        
        for info in global_info:
            text = font.render(info, True, (200, 200, 200))
            surface.blit(text, (x, current_y))
            current_y += 20
        
        current_y += 10
        
        # Civilization stats
        civ_title = font.render("Civilization Expansion:", True, (255, 255, 0))
        surface.blit(civ_title, (x, current_y))
        current_y += 25
        
        for civ_id, civ_info in stats['civilization_stats'].items():
            civ_text = f"{civ_info['name']}: {civ_info['tiles']} tiles, {civ_info['potential_targets']} targets"
            text = font.render(civ_text, True, (180, 180, 180))
            surface.blit(text, (x + 10, current_y))
            current_y += 18
        
        return current_y


def add_gui_integration(gui_instance):
    """Add colonization panel to the main GUI."""
    if not hasattr(gui_instance, 'colonization_panel'):
        gui_instance.colonization_panel = ColonizationGUIPanel(gui_instance.engine)
    
    # Store original key handler if not already done
    if not hasattr(gui_instance, '_original_handle_key'):
        gui_instance._original_handle_key = gui_instance.handle_key
        
        def enhanced_handle_key(event):
            result = gui_instance._original_handle_key(event)
            
            # Toggle colonization panel with 'O' key
            if event.key == ord('o'):
                gui_instance.colonization_panel.toggle_visibility()
                return True
            
            return result
        
        gui_instance.handle_key = enhanced_handle_key
    
    # Store original render method if not already done  
    if not hasattr(gui_instance, '_original_render_ui'):
        gui_instance._original_render_ui = gui_instance.render_ui
        
        def enhanced_render_ui(surface):
            result = gui_instance._original_render_ui(surface)
            
            # Render colonization panel if visible
            if gui_instance.colonization_panel.visible:
                import pygame
                font = pygame.font.Font(None, 18)
                panel_x = surface.get_width() - 400
                panel_y = 50
                
                # Background rectangle
                panel_rect = pygame.Rect(panel_x - 10, panel_y - 10, 380, 300)
                pygame.draw.rect(surface, (0, 0, 0, 180), panel_rect)
                pygame.draw.rect(surface, (100, 100, 100), panel_rect, 2)
                
                gui_instance.colonization_panel.render_stats(surface, font, panel_x, panel_y)
            
            return result
        
        gui_instance.render_ui = enhanced_render_ui