#!/usr/bin/env python3
"""GodsimPy GUI - Main application for interactive civilization simulation."""

import os
import sys
import math
import pygame
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List, Set
from enum import Enum

# ---- Optional technology integration -----------------------------------------
# These imports are guarded. The UI will gracefully no-op if technology.py
# (and its types) are unavailable or if no tech_system is connected to GUI/world.
try:
    from technology import TechnologySystem, Age, TechCategory  # type: ignore
    _TECH_AVAILABLE = True
except Exception:
    TechnologySystem = object  # type: ignore
    class Age:  # minimal compat stubs so hints/dicts work
        DISSEMINATION = "DISSEMINATION"
    class TechCategory:
        pass
    _TECH_AVAILABLE = False

# --- top-down deskew helpers (used by HexRenderer) ---
SQRT3 = math.sqrt(3.0)
DESKEW_Y = 1.0 / SQRT3

def _evenq_center(q: int, r: int, radius: float) -> Tuple[float, float]:
    """
    Center of a flat-top hex in an even-q offset layout.
    Produces a rectangular map boundary with regular hex shapes.
    """
    hex_w = 2.0 * radius
    hex_h = SQRT3 * radius
    horiz = 0.75 * hex_w           # 1.5 * radius
    vert  = hex_h                  # sqrt(3) * radius
    cx = q * horiz + radius
    cy = r * vert + (hex_h * 0.5 if (q & 1) else 0.0) + hex_h * 0.5
    return cx, cy

def _deskew(x: float, y: float) -> Tuple[float, float]:
    # Cancel axial's built-in √3 vertical stretch so top-down looks rectangular
    return x, y * DESKEW_Y

def _to_rect_space(x: float, y: float, q: int, r_hex: float) -> Tuple[float, float]:
    """
    Convert raw axial pixel coords (flat-top) into rectangular top-down space:
      y' = y / √3  -  0.5 * r_hex * q
    """
    return x, y * DESKEW_Y - 0.5 * r_hex * q

from sim.state import WorldState, load_npz, save_npz
from sim.resources import biome_yields
from sim.terrain import generate_features, describe_feature
from sim.civilization import initialize_civs, make_palette
from worldgen import build_world
from sim.state import from_worldgen
from render import render_topdown, render_iso
from render.render_topdown import render_topdown_height, render_topdown_political
from engine import SimulationEngine, Army, Civ
from fixes.engine_integration_complete import apply_all_fixes
from worldgen.biomes import Biome

try:
    from gui.country_labels import CountryLabelRenderer
except ImportError:
    CountryLabelRenderer = None


# ========================= Tech GUI Components ================================

class TechTreeWindow:
    """Window for displaying the technology tree."""
    def __init__(self):
        self.visible = False
        self.selected_civ_id: Optional[int] = None
        self.scroll_y = 0
        self.width = 600
        self.height = 500
        self.padding = 20
        self.dropdown_open = False
        self.dropdown_rect = pygame.Rect(0, 0, 0, 0)
        self.dropdown_screen_rect = pygame.Rect(0, 0, 0, 0)  # For rendering on screen
        self.dropdown_items = []
        self.hovered_item = -1  # Index of currently hovered dropdown item

        # Fonts (init after pygame.init in GUI ctor)
        self.font_title = pygame.font.Font(None, 24)
        self.font_header = pygame.font.Font(None, 20)
        self.font_normal = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 14)

        # Colors by category
        self.category_colors = {
            getattr(TechCategory, "AGRICULTURE", "AGRICULTURE"): (100, 200, 100),
            getattr(TechCategory, "MILITARY", "MILITARY"): (200, 100, 100),
            getattr(TechCategory, "ECONOMY", "ECONOMY"): (200, 200, 100),
            getattr(TechCategory, "SCIENCE", "SCIENCE"): (100, 150, 200),
            getattr(TechCategory, "CULTURE", "CULTURE"): (200, 100, 200),
            getattr(TechCategory, "EXPLORATION", "EXPLORATION"): (150, 200, 200),
            getattr(TechCategory, "INFRASTRUCTURE", "INFRASTRUCTURE"): (150, 150, 150),
            getattr(TechCategory, "METALLURGY", "METALLURGY"): (200, 150, 100),
        }

    def show(self, civ_id: int):
        self.visible = True
        self.selected_civ_id = civ_id
        self.scroll_y = 0

    def hide(self):
        self.visible = False

    def draw(self, surface: pygame.Surface, tech_system: Optional["TechnologySystem"], civs_name_map: Dict[int, str]):
        """Draw the tech tree window (safe if tech_system is None)."""
        if not self.visible or self.selected_civ_id is None or tech_system is None:
            return

        # Calculate window position (centered)
        screen_w, screen_h = surface.get_size()
        x = (screen_w - self.width) // 2
        y = (screen_h - self.height) // 2

        # Create window surface
        window = pygame.Surface((self.width, self.height))
        window.fill((30, 30, 40))

        # Draw border
        pygame.draw.rect(window, (100, 100, 120), (0, 0, self.width, self.height), 3)

        # Title bar
        title_rect = pygame.Rect(0, 0, self.width, 35)
        pygame.draw.rect(window, (50, 50, 70), title_rect)
        pygame.draw.line(window, (100, 100, 120), (0, 35), (self.width, 35), 2)

        # Close button
        close_rect = pygame.Rect(self.width - 30, 5, 25, 25)
        pygame.draw.rect(window, (200, 50, 50), close_rect)
        close_text = self.font_normal.render("X", True, (255, 255, 255))
        close_text_rect = close_text.get_rect(center=close_rect.center)
        window.blit(close_text, close_text_rect)

        civ_id = self.selected_civ_id
        if civ_id not in tech_system.civ_states:
            # Initialize the civilization in the tech system if it doesn't exist
            tech_system.initialize_civ(civ_id)
            if civ_id not in tech_system.civ_states:
                # Show message that tech system is not available for this civ
                error_text = "Technology system not initialized for this civilization"
                error_surface = self.font_normal.render(error_text, True, (200, 100, 100))
                error_rect = error_surface.get_rect(center=(self.width // 2, self.height // 2))
                window.blit(error_surface, error_rect)
                surface.blit(window, (x, y))
                return

        civ_name = civs_name_map.get(civ_id, f"Civ {civ_id}")
        civ_state = tech_system.civ_states.get(civ_id)

        # Title
        title = "Technology Tree"
        title_text = self.font_title.render(title, True, (255, 255, 255))
        title_text_rect = title_text.get_rect(center=(self.width // 2, 17))
        window.blit(title_text, title_text_rect)

        # Civ selector dropdown
        y_offset = 40
        self._draw_civ_dropdown(window, civs_name_map, y_offset)
        y_offset += 35

        # Age / progress
        age_val = getattr(civ_state.current_age, "value", str(civ_state.current_age))
        age_text = f"Current Age: {age_val}"
        self._draw_text(window, age_text, self.padding, y_offset, self.font_header, (200, 200, 100))
        y_offset += 25

        tech_count_text = f"Technologies: {len(civ_state.researched_techs)}"
        self._draw_text(window, tech_count_text, self.padding, y_offset, self.font_normal, (180, 180, 180))
        y_offset += 20

        # Current research
        if civ_state.current_research:
            current_tech = tech_system.tech_tree.technologies.get(civ_state.current_research)
            if current_tech:
                research_text = f"Researching: {current_tech.name}"
                self._draw_text(window, research_text, self.padding, y_offset, self.font_normal, (150, 200, 150))
                y_offset += 18

                # Progress bar
                bar_width = self.width - 2 * self.padding
                bar_height = 15
                bar_x = self.padding
                bar_y = y_offset

                pygame.draw.rect(window, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height))
                # civ_state.research_progress is points; cost is points
                cost = max(1, int(getattr(current_tech, "research_cost", 1)))
                progress_pct = float(getattr(civ_state, "research_progress", 0.0)) / float(cost)
                fill_width = int(bar_width * min(1.0, progress_pct))
                if fill_width > 0:
                    pygame.draw.rect(window, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))
                pygame.draw.rect(window, (80, 80, 80), (bar_x, bar_y, bar_width, bar_height), 1)

                progress_text = f"{getattr(civ_state, 'research_progress', 0.0):.0f} / {cost}"
                text_surf = self.font_small.render(progress_text, True, (255, 255, 255))
                text_rect = text_surf.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
                window.blit(text_surf, text_rect)

                y_offset += bar_height + 10
        else:
            self._draw_text(window, "No active research", self.padding, y_offset, self.font_normal, (150, 150, 150))
            y_offset += 20

        # Separator
        pygame.draw.line(window, (60, 60, 80), (self.padding, y_offset), (self.width - self.padding, y_offset), 1)
        y_offset += 10

        # Available technologies
        self._draw_text(window, "Available Technologies:", self.padding, y_offset, self.font_header, (150, 150, 255))
        y_offset += 25

        list_height = self.height - y_offset - 20
        list_surface = pygame.Surface((self.width - 2 * self.padding, list_height))
        list_surface.fill((25, 25, 35))

        # Get available techs (guarded)
        try:
            available_techs = tech_system.tech_tree.get_available_technologies(
                civ_state.researched_techs,
                civ_state.current_age,
                civ_state.available_resources
            )
        except Exception:
            available_techs = []

        # Show debug info if no techs available
        if not available_techs:
            debug_y = 10
            self._draw_text(list_surface, "No available technologies", 10, debug_y, self.font_normal, (150, 150, 150))
            debug_y += 20
            
            # Debug info
            self._draw_text(list_surface, f"Current Age: {civ_state.current_age}", 10, debug_y, self.font_small, (100, 150, 100))
            debug_y += 18
            
            self._draw_text(list_surface, f"Researched: {len(civ_state.researched_techs)} techs", 10, debug_y, self.font_small, (100, 150, 100))
            debug_y += 18
            
            self._draw_text(list_surface, f"Resources: {list(civ_state.available_resources)}", 10, debug_y, self.font_small, (100, 150, 100))
            debug_y += 18
            
            # Show total techs in tree
            total_techs = len(tech_system.tech_tree.technologies)
            self._draw_text(list_surface, f"Total techs in tree: {total_techs}", 10, debug_y, self.font_small, (100, 100, 150))
        
        tech_y = 5 - self.scroll_y
        for tech in available_techs:
            if -50 < tech_y < list_height:
                tech_rect = pygame.Rect(5, tech_y, self.width - 2 * self.padding - 10, 45)
                cat = getattr(tech, "category", None)
                color = self.category_colors.get(cat, (100, 100, 100))
                darker_color = tuple(c // 2 for c in color)
                pygame.draw.rect(list_surface, darker_color, tech_rect)
                pygame.draw.rect(list_surface, color, tech_rect, 1)

                # Name
                name = getattr(tech, "name", "Unknown Tech")
                name_text = self.font_normal.render(name, True, (255, 255, 255))
                list_surface.blit(name_text, (10, tech_y + 5))

                # Cost
                cost = getattr(tech, "research_cost", 0)
                cost_text = self.font_small.render(f"Cost: {cost}", True, (200, 200, 200))
                list_surface.blit(cost_text, (10, tech_y + 25))

                # Category label
                cat_name = getattr(cat, "name", str(cat)) if cat is not None else "Misc"
                cat_text = self.font_small.render(cat_name, True, color)
                list_surface.blit(cat_text, (self.width - 2 * self.padding - 100, tech_y + 25))
            tech_y += 50

        pygame.draw.rect(list_surface, (60, 60, 80), (0, 0, self.width - 2 * self.padding, list_height), 1)
        window.blit(list_surface, (self.padding, y_offset))

        # Scrollbar
        total_height = len(available_techs) * 50 + 10
        if total_height > list_height:
            scrollbar_x = self.width - self.padding - 10
            scrollbar_height = max(20, list_height * list_height // max(1, total_height))
            scrollbar_y = y_offset + (self.scroll_y * list_height // max(1, total_height))
            pygame.draw.rect(window, (60, 60, 60), (scrollbar_x, y_offset, 10, list_height))
            pygame.draw.rect(window, (120, 120, 120), (scrollbar_x, scrollbar_y, 10, scrollbar_height))

        # Blit
        surface.blit(window, (x, y))

    def _draw_text(self, surface: pygame.Surface, text: str, x: int, y: int,
                   font: pygame.font.Font, color: Tuple[int, int, int]):
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, (x, y))

    def _draw_civ_dropdown(self, surface: pygame.Surface, civs_name_map: Dict[int, str], y_offset: int):
        """Draw civilization selector dropdown."""
        if not civs_name_map:
            return
            
        # Dropdown button
        dropdown_width = 200
        dropdown_height = 25
        dropdown_x = (self.width - dropdown_width) // 2
        
        self.dropdown_rect = pygame.Rect(dropdown_x, y_offset, dropdown_width, dropdown_height)
        
        # Current selection
        current_civ_name = civs_name_map.get(self.selected_civ_id, "No Civ Selected")
        
        # Draw main dropdown button
        button_color = (60, 60, 80) if not self.dropdown_open else (80, 80, 100)
        pygame.draw.rect(surface, button_color, self.dropdown_rect)
        pygame.draw.rect(surface, (100, 100, 120), self.dropdown_rect, 1)
        
        # Dropdown text
        text_surface = self.font_normal.render(current_civ_name, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.dropdown_rect.center)
        surface.blit(text_surface, text_rect)
        
        # Dropdown arrow
        arrow_x = dropdown_x + dropdown_width - 20
        arrow_y = y_offset + dropdown_height // 2
        arrow_points = [
            (arrow_x, arrow_y - 3),
            (arrow_x + 6, arrow_y + 3),
            (arrow_x - 6, arrow_y + 3)
        ]
        pygame.draw.polygon(surface, (200, 200, 200), arrow_points)
        
        # Store dropdown info for later rendering (don't draw list here)
        if self.dropdown_open:
            self.dropdown_items = list(civs_name_map.items())
        else:
            self.dropdown_items = []

    def handle_click(self, mouse_x: int, mouse_y: int, screen_size: Tuple[int, int], civs_name_map: Dict[int, str] = None) -> bool:
        """Returns True if window was closed."""
        if not self.visible:
            return False
        screen_w, screen_h = screen_size
        window_x = (screen_w - self.width) // 2
        window_y = (screen_h - self.height) // 2
        
        # Convert screen coordinates to window coordinates
        local_x = mouse_x - window_x
        local_y = mouse_y - window_y
        
        # Handle dropdown clicks - check list items first
        if self.dropdown_open and civs_name_map:
            # Calculate dropdown list position (same as in render_dropdown_overlay)
            screen_w, screen_h = screen_size
            window_x = (screen_w - self.width) // 2
            window_y = (screen_h - self.height) // 2
            dropdown_width = 200
            dropdown_height = 25
            dropdown_x = window_x + (self.width - dropdown_width) // 2
            dropdown_y = window_y + 40 + dropdown_height  # y_offset + dropdown_height
            list_height = min(len(civs_name_map) * 25, 150)  # Max 6 items visible
            dropdown_list_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, list_height)
            
            # First check if clicking on dropdown list items (highest priority)
            if dropdown_list_rect.collidepoint(mouse_x, mouse_y):
                # Calculate which item was clicked
                relative_y = mouse_y - dropdown_y
                item_index = relative_y // 25
                civ_ids = list(civs_name_map.keys())
                if 0 <= item_index < len(civ_ids):
                    self.selected_civ_id = civ_ids[item_index]
                    self.dropdown_open = False
                    return False  # Don't close window
            # Then check if clicking dropdown button while open
            elif civs_name_map and self.dropdown_rect.collidepoint(local_x, local_y):
                # Clicked dropdown button while open - close it
                self.dropdown_open = False
                return False
            else:
                # Click outside dropdown closes it
                self.dropdown_open = False
                return False
        elif civs_name_map and self.dropdown_rect.collidepoint(local_x, local_y):
            # Open dropdown (only if not currently open)
            self.dropdown_open = True
            return False  # Don't close window
        
        # Close button
        close_x = self.width - 30
        close_y = 5
        if close_x <= local_x <= close_x + 25 and close_y <= local_y <= close_y + 25:
            self.hide()
            return True
        return False

    def handle_scroll(self, delta: int):
        if self.visible:
            self.scroll_y = max(0, self.scroll_y - delta * 20)
    
    def render_dropdown_overlay(self, screen: pygame.Surface):
        """Render dropdown list on top of everything else."""
        if not self.visible or not self.dropdown_open or not self.dropdown_items:
            return
            
        # Calculate window position
        screen_w, screen_h = screen.get_size()
        window_x = (screen_w - self.width) // 2
        window_y = (screen_h - self.height) // 2
        
        # Dropdown position
        dropdown_width = 200
        dropdown_height = 25
        dropdown_x = window_x + (self.width - dropdown_width) // 2
        dropdown_y = window_y + 40 + dropdown_height  # y_offset + dropdown_height
        
        # List dimensions
        list_height = min(len(self.dropdown_items) * 25, 150)  # Max 6 items visible
        list_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, list_height)
        
        # Background
        pygame.draw.rect(screen, (40, 40, 50), list_rect)
        pygame.draw.rect(screen, (100, 100, 120), list_rect, 1)
        
        # Items
        for i, (civ_id, civ_name) in enumerate(self.dropdown_items):
            if i * 25 >= list_height:
                break
                
            item_y = dropdown_y + i * 25
            item_rect = pygame.Rect(dropdown_x, item_y, dropdown_width, 25)
            
            # Highlight current selection or hovered item
            if civ_id == self.selected_civ_id:
                pygame.draw.rect(screen, (80, 100, 80), item_rect)
            elif i == self.hovered_item:
                # Glow effect for hovered item
                pygame.draw.rect(screen, (120, 120, 160), item_rect)  # Light blue glow
                pygame.draw.rect(screen, (160, 160, 200), item_rect, 2)  # Brighter border
                
            # Item text
            text_color = (255, 255, 255) if i != self.hovered_item else (255, 255, 200)  # Slightly yellow when hovered
            item_text = self.font_small.render(civ_name, True, text_color)
            item_text_rect = item_text.get_rect(center=item_rect.center)
            screen.blit(item_text, item_text_rect)
            
        # Update screen rect for click detection
        self.dropdown_screen_rect = list_rect
    
    def update_hover(self, mouse_x: int, mouse_y: int):
        """Update which dropdown item is being hovered."""
        if self.visible and self.dropdown_open and self.dropdown_items:
            if hasattr(self, 'dropdown_screen_rect') and self.dropdown_screen_rect.collidepoint(mouse_x, mouse_y):
                # Calculate which item is hovered
                relative_y = mouse_y - self.dropdown_screen_rect.y
                item_index = relative_y // 25
                if 0 <= item_index < len(self.dropdown_items):
                    self.hovered_item = item_index
                else:
                    self.hovered_item = -1
            else:
                self.hovered_item = -1
        else:
            self.hovered_item = -1


class TechInfoPanel:
    """Panel extension to show technology info in the main info panel."""
    @staticmethod
    def draw_tech_info(surface: pygame.Surface, x: int, y: int, width: int,
                       civ_id: int, tech_system: Optional["TechnologySystem"],
                       font_header: pygame.font.Font, font_normal: pygame.font.Font,
                       font_small: pygame.font.Font) -> int:
        if tech_system is None or civ_id not in getattr(tech_system, "civ_states", {}):
            return y

        state = tech_system.civ_states[civ_id]

        header = font_header.render("TECHNOLOGY", True, (200, 200, 100))
        surface.blit(header, (x, y))
        pygame.draw.line(surface, (100, 100, 50), (x, y + 20), (x + width - 30, y + 20), 1)
        y += 25

        age_val = getattr(state.current_age, "value", str(state.current_age))
        age_box = pygame.Rect(x + 5, y + 2, 10, 10)
        pygame.draw.rect(surface, (150, 150, 150), age_box)

        age_text = font_normal.render(f"Age: {age_val}", True, (180, 180, 180))
        surface.blit(age_text, (x + 20, y))
        y += 20

        tech_text = font_normal.render(f"Technologies: {len(state.researched_techs)}", True, (180, 180, 180))
        surface.blit(tech_text, (x + 5, y))
        y += 20

        if state.current_research:
            tech = tech_system.tech_tree.technologies.get(state.current_research)
            if tech:
                research_text = font_small.render(f"Researching: {getattr(tech, 'name', 'Tech')}", True, (150, 200, 150))
                surface.blit(research_text, (x + 5, y))
                y += 18

                bar_width = width - 40
                bar_height = 8
                bar_x = x + 5
                bar_y = y
                pygame.draw.rect(surface, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height))
                cost = max(1, int(getattr(tech, "research_cost", 1)))
                progress = float(getattr(state, "research_progress", 0.0)) / float(cost)
                fill_width = int(bar_width * min(1.0, progress))
                if fill_width > 0:
                    pygame.draw.rect(surface, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))
                pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_y, bar_width, bar_height), 1)
                y += bar_height + 5
        else:
            no_research_text = font_small.render("No active research", True, (150, 150, 150))
            surface.blit(no_research_text, (x + 5, y))
            y += 18

        # Optional bonuses string if present on state
        try:
            bonuses = state.calculate_total_bonuses(tech_system.tech_tree)
            lines = []
            if getattr(bonuses, "food_multiplier", 1.0) > 1.0:
                lines.append(f"Food: +{(bonuses.food_multiplier - 1)*100:.0f}%")
            if getattr(bonuses, "production_multiplier", 1.0) > 1.0:
                lines.append(f"Prod: +{(bonuses.production_multiplier - 1)*100:.0f}%")
            if getattr(bonuses, "military_strength", 0) > 0:
                lines.append(f"Military: +{bonuses.military_strength:.0f}")
            if lines:
                y += 5
                bonus_text = font_small.render("Active Bonuses:", True, (200, 200, 100))
                surface.blit(bonus_text, (x + 5, y))
                y += 15
                for line in lines:
                    ln = font_small.render(line, True, (180, 200, 180))
                    surface.blit(ln, (x + 10, y))
                    y += 15
        except Exception:
            pass

        y += 10
        return y


class TechHotkeys:
    """Keyboard shortcuts for technology features."""
    @staticmethod
    def handle_keypress(event: pygame.event.Event,
                        tech_window: TechTreeWindow,
                        selected_civ_id: Optional[int]) -> bool:
        if event.key == pygame.K_t:
            if tech_window.visible:
                tech_window.hide()
            elif selected_civ_id is not None:
                tech_window.show(selected_civ_id)
            return True
        return False


class AgeProgressIndicator:
    """Visual indicator for age progression."""
    def __init__(self):
        self.font = pygame.font.Font(None, 14)
        # Simple, neutral color map (works even without full Age enum)
        self.age_colors = {
            getattr(Age, "DISSEMINATION", "DISSEMINATION"): (150, 100, 50),
            getattr(Age, "COPPER", "COPPER"): (200, 150, 100),
            getattr(Age, "BRONZE", "BRONZE"): (180, 140, 80),
            getattr(Age, "IRON", "IRON"): (160, 160, 160),
            getattr(Age, "CLASSICAL", "CLASSICAL"): (200, 180, 150),
            getattr(Age, "MEDIEVAL", "MEDIEVAL"): (120, 120, 140),
            getattr(Age, "RENAISSANCE", "RENAISSANCE"): (180, 150, 200),
            getattr(Age, "INDUSTRIAL", "INDUSTRIAL"): (100, 100, 120),
        }

    def draw(self, surface: pygame.Surface, x: int, y: int,
             civ_name: str, current_age, tech_count: int) -> None:
        bg_rect = pygame.Rect(x, y, 200, 25)
        pygame.draw.rect(surface, (30, 30, 40), bg_rect)
        pygame.draw.rect(surface, (60, 60, 80), bg_rect, 1)

        age_key = getattr(current_age, "name", current_age)
        age_color = self.age_colors.get(age_key, (100, 100, 100))
        age_rect = pygame.Rect(x + 2, y + 2, 21, 21)
        pygame.draw.rect(surface, age_color, age_rect)

        name_text = self.font.render(civ_name, True, (200, 200, 200))
        surface.blit(name_text, (x + 28, y + 5))

        tech_text = self.font.render(f"[{tech_count} techs]", True, (150, 150, 150))
        surface.blit(tech_text, (x + 120, y + 5))

        # Next-age progress (best-effort: requires min_techs on Age)
        try:
            next_age = current_age.next()
            if next_age:
                need = max(1, int(getattr(next_age, "min_techs_required", 1)))
                progress = min(1.0, tech_count / float(need))
                bar_x, bar_y, bar_w, bar_h = x + 28, y + 18, 165, 4
                pygame.draw.rect(surface, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
                fill_w = int(bar_w * progress)
                if fill_w > 0:
                    next_color = self.age_colors.get(getattr(next_age, "name", "X"), (100, 100, 100))
                    darker = tuple(c // 2 for c in next_color)
                    pygame.draw.rect(surface, darker, (bar_x, bar_y, fill_w, bar_h))
        except Exception:
            pass


class TechMapOverlay:
    """Overlay for the hex map showing technological advancement (age dots)."""
    def __init__(self):
        self.show_age_overlay = False
        self.font = pygame.font.Font(None, 12)

    def toggle(self):
        self.show_age_overlay = not self.show_age_overlay

    def draw_hex_overlay(self, surface: pygame.Surface, hex_center: Tuple[int, int],
                         hex_radius: float, owner_civ_id: Optional[int],
                         tech_system: Optional["TechnologySystem"]) -> None:
        if not self.show_age_overlay or owner_civ_id is None or tech_system is None:
            return
        if owner_civ_id not in getattr(tech_system, "civ_states", {}):
            return
        state = tech_system.civ_states[owner_civ_id]
        # Choose color by age (coarse)
        color = (180, 150, 200)
        indicator_radius = int(min(8, hex_radius * 0.3))
        cx, cy = hex_center
        pygame.draw.circle(surface, (0, 0, 0), (int(cx), int(cy)), indicator_radius + 1)
        pygame.draw.circle(surface, color, (int(cx), int(cy)), indicator_radius)


class TechNotification:
    """Notification popup for technology discoveries."""
    def __init__(self):
        self.notifications: List[Dict] = []
        self.font_header = pygame.font.Font(None, 20)
        self.font_normal = pygame.font.Font(None, 16)
        self.notification_duration = 3000  # ms

    def add_tech_discovered(self, civ_name: str, tech_name: str, timestamp: int):
        self.notifications.append({'type': 'tech_discovered', 'civ': civ_name, 'tech': tech_name,
                                   'timestamp': timestamp, 'alpha': 255})

    def add_age_advanced(self, civ_name: str, age_name: str, timestamp: int):
        self.notifications.append({'type': 'age_advanced', 'civ': civ_name, 'age': age_name,
                                   'timestamp': timestamp, 'alpha': 255})

    def update(self, current_time: int):
        self.notifications = [
            n for n in self.notifications if current_time - n['timestamp'] < self.notification_duration
        ]
        for n in self.notifications:
            age = current_time - n['timestamp']
            if age > self.notification_duration * 0.7:
                fade_duration = self.notification_duration * 0.3
                fade_progress = (age - self.notification_duration * 0.7) / max(1, fade_duration)
                n['alpha'] = int(255 * max(0.0, 1 - fade_progress))

    def draw(self, surface: pygame.Surface, x: int, y: int):
        y_offset = 0
        for notif in self.notifications[:5]:
            width, height = 300, 50
            s = pygame.Surface((width, height))
            s.set_alpha(notif['alpha'])
            if notif['type'] == 'tech_discovered':
                bg_color = (50, 100, 50)
                icon_color = (100, 200, 100)
            else:
                bg_color = (100, 80, 50)
                icon_color = (200, 160, 100)

            s.fill(bg_color)
            pygame.draw.rect(s, icon_color, (0, 0, width, height), 2)

            icon_rect = pygame.Rect(5, 5, 40, 40)
            pygame.draw.rect(s, icon_color, icon_rect, 2)
            if notif['type'] == 'tech_discovered':
                pygame.draw.circle(s, icon_color, (25, 20), 8)
                pygame.draw.line(s, icon_color, (25, 28), (25, 35), 2)
                pygame.draw.line(s, icon_color, (20, 35), (30, 35), 2)
            else:
                pygame.draw.polygon(s, icon_color,
                                    [(25, 10), (35, 20), (35, 30), (25, 40), (15, 30), (15, 20)])

            if notif['type'] == 'tech_discovered':
                header = f"{notif['civ']} discovered"
                detail = notif['tech']
            else:
                header = f"{notif['civ']} entered"
                detail = notif['age']

            header_text = self.font_normal.render(header, True, (255, 255, 255))
            detail_text = self.font_header.render(detail, True, (255, 255, 200))
            s.blit(header_text, (50, 8))
            s.blit(detail_text, (50, 25))
            surface.blit(s, (x, y + y_offset))
            y_offset += height + 5


# =============================== Existing GUI =================================

class ViewMode(Enum):
    POLITICAL = "political"
    TERRAIN = "terrain"
    POPULATION = "population"
    RESOURCES = "resources"
    CULTURE = "culture"
    RELIGION = "religion"


@dataclass
class Camera:
    """Camera for panning and zooming the hex map."""
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    min_zoom: float = 0.05
    max_zoom: float = 3.0

    def pan(self, dx: float, dy: float):
        self.x += dx / self.zoom
        self.y += dy / self.zoom

    def zoom_at(self, zoom_delta: float, focus_x: float, focus_y: float, screen_width: int, screen_height: int):
        old_zoom = self.zoom
        new_zoom = self.zoom * (1 + zoom_delta)
        self.zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        
        # Only adjust position if zoom actually changed
        if abs(self.zoom - old_zoom) > 1e-6:
            # Convert screen focus point to world coordinates using old zoom
            old_wx = (focus_x - screen_width * 0.5) / old_zoom + self.x
            old_wy = (focus_y - screen_height * 0.5) / old_zoom + self.y
            
            # Adjust camera position so the focus point stays at the same screen position
            self.x = old_wx - (focus_x - screen_width * 0.5) / self.zoom
            self.y = old_wy - (focus_y - screen_height * 0.5) / self.zoom

    def world_to_screen(self, wx: float, wy: float, screen_width: int, screen_height: int) -> Tuple[int, int]:
        sx = (wx - self.x) * self.zoom + screen_width * 0.5
        sy = (wy - self.y) * self.zoom + screen_height * 0.5
        return round(sx), round(sy)

    def screen_to_world(self, sx: int, sy: int, screen_width: int, screen_height: int) -> Tuple[float, float]:
        wx = (sx - screen_width * 0.5) / self.zoom + self.x
        wy = (sy - screen_height * 0.5) / self.zoom + self.y
        return wx, wy


class HexRenderer:
    """Renders hexagonal map with different view modes (pointy-top in top-down)."""

    BIOME_COLORS = {
        0: (34, 139, 34),      # GRASS - green
        1: (238, 203, 173),    # COAST - sandy
        2: (139, 137, 137),    # MOUNTAIN - gray
        3: (0, 119, 190),      # OCEAN - blue
        4: (238, 203, 120),    # DESERT - yellow-sand
        5: (176, 224, 230),    # TUNDRA - pale blue-green
        6: (240, 248, 255),    # GLACIER - almost white
        7: (107, 142, 35),     # MARSH - olive green
        8: (189, 183, 107),    # STEPPE - khaki
        9: (244, 164, 96),     # SAVANNA - sandy brown
        10: (34, 100, 34),     # TAIGA - dark green
        11: (34, 120, 34),     # TEMPERATE_FOREST - medium green
        12: (0, 100, 0),       # TROPICAL_FOREST - deep green
    }

    def __init__(self, world_state: WorldState, hex_radius: float = 40.0):
        self.world_state = world_state
        self.hex_radius = hex_radius
        self.selected_hex: Optional[Tuple[int, int]] = None
        self.hovered_hex: Optional[Tuple[int, int]] = None
        self.civ_colors = make_palette(10)  # Support up to 10 civs
        
        # Fonts for different zoom levels
        self.font_large = pygame.font.Font(None, 32)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.font_tiny = pygame.font.Font(None, 14)

        self.capital_icon: Optional[pygame.Surface] = self._load_image_first_found([
            "media/capital.png",
            "assets/icons/capital.png",
        ])
        self._capital_scaled_cache: Dict[int, pygame.Surface] = {}  # key: pixel size
        
        # Country label renderer
        self.country_label_renderer = CountryLabelRenderer() if CountryLabelRenderer else None


    def get_font_for_zoom(self, zoom: float) -> pygame.font.Font:
        """Pick a readable font size based on zoom level."""
        if zoom >= 1.5:
            return self.font_large
        elif zoom >= 1.0:
            return self.font_medium
        elif zoom >= 0.5:
            return self.font_small
        else:
            return self.font_tiny

    def render(self, surface: pygame.Surface, camera: "Camera", view_mode: "ViewMode",
               tech_overlay: Optional["TechMapOverlay"] = None,
               tech_system: Optional["TechnologySystem"] = None,
               civs: Optional[List] = None) -> None:
        """Draw the entire hex map onto `surface`."""
        surface.fill((10, 10, 30))
        H, W = self.world_state.height, self.world_state.width

        # PASS 1: hex tiles (with viewport culling for performance)
        screen_w, screen_h = surface.get_size()
        margin = self.hex_radius * 2  # Extra margin for partial visibility
        
        for r in range(H):
            for q in range(W):
                # Quick viewport culling: check if hex center is roughly visible
                cx, cy = _evenq_center(q, r, self.hex_radius)
                sx, sy = camera.world_to_screen(cx, cy, screen_w, screen_h)
                
                # Skip hexes that are clearly outside the visible area
                if (sx < -margin or sx > screen_w + margin or 
                    sy < -margin or sy > screen_h + margin):
                    continue
                
                color = self.get_hex_color(q, r, view_mode)
                outline = None
                if view_mode == ViewMode.TERRAIN and self.world_state.owner_map[r, q] >= 0:
                    owner = int(self.world_state.owner_map[r, q])
                    outline = self.civ_colors[owner % len(self.civ_colors)]
                self.draw_hex(surface, q, r, color, camera, outline, tech_overlay, tech_system)

        # PASS 2: settlements/labels
        if civs and camera.zoom > 0.1:
            self.draw_settlement_overlays(surface, camera, civs)
            
        # PASS 3: civilization borders
        self._draw_civ_borders(surface, camera)
        
        # PASS 4: selection and hover highlights
        self._draw_selection_highlights(surface, camera)
        
        # PASS 5: country labels (EU4-style)
        if civs and self.country_label_renderer:
            self.country_label_renderer.render_country_labels(
                surface, self.world_state, civs, camera, self.hex_radius, _evenq_center)

    def draw_settlement_overlays(self, surface: pygame.Surface, camera: "Camera", civs: List) -> None:
        H, W = self.world_state.height, self.world_state.width
        font = self.get_font_for_zoom(camera.zoom)
        drawn_civ_labels: set[int] = set()

        for r in range(H):
            for q in range(W):
                owner = int(self.world_state.owner_map[r, q])
                if owner < 0 or owner >= len(civs):
                    continue

                population = int(self.world_state.pop_map[r, q])
                settlement_code = int(self.world_state.settlement_map[r, q])
                is_capital = (settlement_code == 4)  # Capital is settlement type 4
                
                # Show all capitals regardless of population, others need min population
                if not is_capital and population <= 10:
                    continue

                cx, cy = _evenq_center(q, r, self.hex_radius)
                sx, sy = camera.world_to_screen(cx, cy, surface.get_width(), surface.get_height())
                if not (0 <= sx < surface.get_width() and 0 <= sy < surface.get_height()):
                    continue

                civ = civs[owner]

                stype = self.get_settlement_type(settlement_code)
                self.draw_settlement_icon(surface, sx, sy, stype, is_capital, camera.zoom)

                # Only show settlement names when zoomed in (country labels handle civ names)
                if camera.zoom >= 1.2 and (is_capital or settlement_code >= 2):
                    # Show settlement type instead of civ name when zoomed in
                    label = f"{stype.title()}"
                    if is_capital:
                        label = f"{civ.name} (Capital)"
                    elif settlement_code >= 2:  # Towns and cities get names
                        label = f"{stype.title()}"
                    
                    if owner not in drawn_civ_labels:
                        lx = sx + int(15 * camera.zoom)
                        ly = sy - int(10 * camera.zoom)
                        self.draw_text_with_border(surface, label, lx, ly, font)
                        drawn_civ_labels.add(owner)




    def _load_image_first_found(self, candidate_rel_paths: List[str]) -> Optional[pygame.Surface]:
        """
        Try to load an image from several repo-relative paths.
        Returns a Surface or None if all candidates fail. Safe to call after pygame.init().
        """
        import pathlib
        # Anchor to this file's directory (repo-relative), not the CWD.
        here = pathlib.Path(__file__).resolve().parent
        for rel in candidate_rel_paths:
            p = (here / rel).resolve()
            if p.exists():
                try:
                    return pygame.image.load(str(p)).convert_alpha()
                except Exception:
                    pass
        return None

    def get_hex_at_point(self, wx: float, wy: float) -> Optional[Tuple[int, int]]:
        """World -> (q,r) using even-q centers (regular flat-top hexes)."""
        r_hex = self.hex_radius
        H, W = self.world_state.height, self.world_state.width
        
        # Quick mathematical approximation to find nearby hexes instead of brute force
        hex_w = 2.0 * r_hex
        hex_h = SQRT3 * r_hex
        horiz = 0.75 * hex_w  # 1.5 * radius
        vert = hex_h  # sqrt(3) * radius
        
        # Estimate q,r from world coordinates
        approx_q = int(round(wx / horiz))
        approx_r = int(round((wy - (hex_h * 0.5 if (approx_q & 1) else 0.0) - hex_h * 0.5) / vert))
        
        # Check a small area around the approximation instead of all hexes
        pick_r2 = (0.95 * r_hex) ** 2
        best_q = best_r = None
        best_d2 = float("inf")
        
        # Only check a 3x3 area around the approximation
        for dr in range(-1, 2):
            for dq in range(-1, 2):
                q = approx_q + dq
                r = approx_r + dr
                
                if 0 <= q < W and 0 <= r < H:
                    cx, cy = _evenq_center(q, r, r_hex)
                    d2 = (wx - cx) ** 2 + (wy - cy) ** 2
                    if d2 < best_d2 and d2 <= pick_r2:
                        best_d2, best_q, best_r = d2, q, r

        return (best_q, best_r) if best_q is not None else None

    def draw_hex(self, surface: pygame.Surface, q: int, r: int,
                 color: Tuple[int, int, int], camera: "Camera",
                 outline_color: Optional[Tuple[int, int, int]] = None,
                 tech_overlay: Optional["TechMapOverlay"] = None,
                 tech_system: Optional["TechnologySystem"] = None):
        """Draw one flat-top hex at its even-q center."""
        cx, cy = _evenq_center(q, r, self.hex_radius)

        # vertices
        verts = []
        for i in range(6):
            ang = math.radians(60 * i)
            vx = cx + self.hex_radius * math.cos(ang)
            vy = cy + self.hex_radius * math.sin(ang)
            sx, sy = camera.world_to_screen(vx, vy, surface.get_width(), surface.get_height())
            verts.append((sx, sy))

        # simple cull
        if all(
            sx < -50 or sx > surface.get_width() + 50 or
            sy < -50 or sy > surface.get_height() + 50
            for sx, sy in verts
        ):
            return

        pygame.draw.polygon(surface, color, verts)
        
        # Draw semi-transparent hex grid borders (skip when zoomed out for performance)
        if camera.zoom > 0.6:
            pygame.draw.polygon(surface, (60, 60, 60), verts, 1)
        
        # Keep basic outlines (selection/hover will be drawn later)
        if outline_color:
            pygame.draw.polygon(surface, outline_color, verts, 2)

        # Optional tech overlay dot
        if tech_overlay is not None:
            cx_s, cy_s = camera.world_to_screen(cx, cy, surface.get_width(), surface.get_height())
            owner = self.world_state.owner_map[r, q]
            if owner >= 0:
                tech_overlay.draw_hex_overlay(surface, (cx_s, cy_s), self.hex_radius * camera.zoom, owner, tech_system)

    def _hex_vertices_world(self, q: int, r: int) -> List[Tuple[float, float]]:
        """Get 6 world-space vertices for flat-top hex at (q,r)."""
        cx, cy = _evenq_center(q, r, self.hex_radius)
        verts = []
        for i in range(6):
            ang = math.radians(60 * i)  # 0°, 60°, 120°, 180°, 240°, 300°
            vx = cx + self.hex_radius * math.cos(ang)
            vy = cy + self.hex_radius * math.sin(ang)
            verts.append((vx, vy))
        return verts
    
    def _edge_world_by_dir(self, q: int, r: int, dir_idx: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get world-space edge vertices for direction index.
        dir_idx: 0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE
        Flat-top hex vertices: 0°=E, 60°=SE, 120°=SW, 180°=W, 240°=NW, 300°=NE
        """
        verts = self._hex_vertices_world(q, r)
        # For flat-top hex: vertex 0 is at 0° (E), going clockwise
        # Direction to edge vertex pairs (adjacent vertices form edges):
        edge_map = [
            (0, 1),  # E:  vertex 0 (0°) to vertex 1 (60°) 
            (5, 0),  # NE: vertex 5 (300°) to vertex 0 (0°)
            (4, 5),  # NW: vertex 4 (240°) to vertex 5 (300°)
            (3, 4),  # W:  vertex 3 (180°) to vertex 4 (240°)
            (2, 3),  # SW: vertex 2 (120°) to vertex 3 (180°)
            (1, 2),  # SE: vertex 1 (60°) to vertex 2 (120°)
        ]
        v1_idx, v2_idx = edge_map[dir_idx]
        return (verts[v1_idx], verts[v2_idx])
    
    def _to_screen_float(self, camera: "Camera", x: float, y: float, w: int, h: int) -> Tuple[float, float]:
        """Convert world coordinates to screen coordinates (no rounding)."""
        # Use camera's world_to_screen logic but without rounding
        screen_x = (x - camera.x) * camera.zoom + w // 2
        screen_y = (y - camera.y) * camera.zoom + h // 2
        return (screen_x, screen_y)
    
    def _draw_checker_line(self, surface: pygame.Surface, p1: Tuple[float, float], p2: Tuple[float, float], 
                          col_a: Tuple[int, int, int], col_b: Tuple[int, int, int], width: int, dash_px: int = 8):
        """Draw alternating colored dashes along line segment."""
        x1, y1 = p1
        x2, y2 = p2
        length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        if length < 1:
            return
            
        num_dashes = max(1, int(length / dash_px))
        
        for i in range(num_dashes):
            t1 = i / num_dashes
            t2 = (i + 1) / num_dashes
            
            sx1 = x1 + t1 * (x2 - x1)
            sy1 = y1 + t1 * (y2 - y1)
            sx2 = x1 + t2 * (x2 - x1)
            sy2 = y1 + t2 * (y2 - y1)
            
            color = col_a if i % 2 == 0 else col_b
            pygame.draw.line(surface, color, (int(sx1), int(sy1)), (int(sx2), int(sy2)), width)
    
    def _get_neighbor_even_q(self, q: int, r: int, dir_idx: int) -> Tuple[int, int]:
        """Get neighbor coordinates for direction index using even-q offset.
        dir_idx: 0=E, 1=NE, 2=NW, 3=W, 4=SW, 5=SE
        """
        # Correct even-q offset neighbor patterns for flat-top hexes
        if q % 2 == 0:  # Even column
            offsets = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, -1), (0, 1)]  # [E, NE, NW, W, SW, SE]
        else:  # Odd column  
            offsets = [(1, 0), (1, 1), (0, -1), (-1, 0), (-1, 1), (0, 1)]    # [E, NE, NW, W, SW, SE]
        
        dq, dr = offsets[dir_idx]
        return (q + dq, r + dr)
    
    def _draw_civ_borders(self, surface: pygame.Surface, camera: "Camera"):
        """Draw borders only between hexes with different owners."""
        h, w = self.world_state.owner_map.shape
        screen_w, screen_h = surface.get_size()
        drawn_edges = set()  # Global deduplication across all civs
        
        base_width = max(1, int(2 * camera.zoom))
        checker_width = max(1, int(1.25 * camera.zoom))
        
        # Process all owned hexes and draw borders only where owners differ
        for r in range(h):
            for q in range(w):
                owner = self.world_state.owner_map[r, q]
                if owner < 0:  # Skip unowned hexes
                    continue
                
                # Quick viewport culling for border drawing
                cx, cy = _evenq_center(q, r, self.hex_radius)
                sx, sy = camera.world_to_screen(cx, cy, screen_w, screen_h)
                margin = self.hex_radius * 3  # Larger margin for borders
                if (sx < -margin or sx > screen_w + margin or 
                    sy < -margin or sy > screen_h + margin):
                    continue
                    
                # Check all 6 directions for borders with different owners
                for dir_idx in range(6):
                    nq, nr = self._get_neighbor_even_q(q, r, dir_idx)
                    
                    # Get neighbor owner (OOB = -1, same as unclaimed)
                    if 0 <= nr < h and 0 <= nq < w:
                        neighbor_owner = self.world_state.owner_map[nr, nq]
                    else:
                        neighbor_owner = -1  # Out of bounds
                    
                    # Only draw border if owners are DIFFERENT
                    if neighbor_owner != owner:
                        # Create edge key to prevent double drawing
                        # Use canonical representation (smaller coordinate first)
                        if (q, r) <= (nq, nr):
                            edge_key = ((q, r), (nq, nr))
                        else:
                            edge_key = ((nq, nr), (q, r))
                            
                        if edge_key in drawn_edges:
                            continue
                        drawn_edges.add(edge_key)
                        
                        # Draw the border edge
                        (wx1, wy1), (wx2, wy2) = self._edge_world_by_dir(q, r, dir_idx)
                        
                        # Convert to screen space
                        sx1, sy1 = self._to_screen_float(camera, wx1, wy1, screen_w, screen_h)
                        sx2, sy2 = self._to_screen_float(camera, wx2, wy2, screen_w, screen_h)
                        
                        # Draw black base line
                        pygame.draw.line(surface, (0, 0, 0), (int(sx1), int(sy1)), (int(sx2), int(sy2)), base_width)
                        
                        # If neighbor is another civ (not wilderness), add checkered pattern
                        if neighbor_owner >= 0:
                            civ_color = self.civ_colors[owner % len(self.civ_colors)]
                            neighbor_color = self.civ_colors[neighbor_owner % len(self.civ_colors)]
                            self._draw_checker_line(surface, (sx1, sy1), (sx2, sy2), civ_color, neighbor_color, checker_width, dash_px=8)
    
    def _draw_selection_highlights(self, surface: pygame.Surface, camera: "Camera"):
        """Draw selection and hover highlights after all borders."""
        screen_w, screen_h = surface.get_size()
        
        # Draw hovered hex highlight
        if self.hovered_hex:
            q, r = self.hovered_hex
            if 0 <= r < self.world_state.height and 0 <= q < self.world_state.width:
                cx, cy = _evenq_center(q, r, self.hex_radius)
                verts = []
                for i in range(6):
                    ang = math.radians(60 * i)
                    vx = cx + self.hex_radius * math.cos(ang)
                    vy = cy + self.hex_radius * math.sin(ang)
                    sx, sy = camera.world_to_screen(vx, vy, screen_w, screen_h)
                    verts.append((sx, sy))
                
                # Check if on screen
                if any(0 <= sx <= screen_w and 0 <= sy <= screen_h for sx, sy in verts):
                    pygame.draw.polygon(surface, (255, 255, 255), verts, 3)
        
        # Draw selected hex highlight (on top of hover)
        if self.selected_hex:
            q, r = self.selected_hex
            if 0 <= r < self.world_state.height and 0 <= q < self.world_state.width:
                cx, cy = _evenq_center(q, r, self.hex_radius)
                verts = []
                for i in range(6):
                    ang = math.radians(60 * i)
                    vx = cx + self.hex_radius * math.cos(ang)
                    vy = cy + self.hex_radius * math.sin(ang)
                    sx, sy = camera.world_to_screen(vx, vy, screen_w, screen_h)
                    verts.append((sx, sy))
                
                # Check if on screen
                if any(0 <= sx <= screen_w and 0 <= sy <= screen_h for sx, sy in verts):
                    pygame.draw.polygon(surface, (255, 255, 0), verts, 4)

    def get_hex_color(self, q: int, r: int, view_mode: "ViewMode") -> Tuple[int, int, int]:
        if view_mode == ViewMode.TERRAIN:
            biome = self.world_state.biome_map[r, q]
            return self.BIOME_COLORS.get(biome, (100, 100, 100))

        elif view_mode == ViewMode.POLITICAL:
            owner = self.world_state.owner_map[r, q]
            biome = self.world_state.biome_map[r, q]
            terrain_color = self.BIOME_COLORS.get(biome, (100, 100, 100))
            
            if owner >= 0:
                # Blend political color with terrain (70% political, 30% terrain)
                political_color = self.civ_colors[owner % len(self.civ_colors)]
                blended = tuple(int(p * 0.7 + t * 0.3) for p, t in zip(political_color, terrain_color))
                return blended
            else:
                # Unowned areas show terrain with reduced brightness
                return tuple(int(c * 0.6) for c in terrain_color)

        elif view_mode == ViewMode.POPULATION:
            pop = self.world_state.pop_map[r, q]
            if pop > 0:
                intensity = min(255, int(pop * 2))
                return (intensity, intensity // 2, 0)
            return (20, 20, 20)

        elif view_mode == ViewMode.RESOURCES:
            yields = biome_yields(self.world_state.biome_map)
            food = yields["food"][r, q]
            intensity = int(min(255, food * 200))
            return (0, intensity, 0)

        elif view_mode == ViewMode.CULTURE:
            if hasattr(self.world_state, 'culture_map') and self.world_state.culture_map is not None:
                culture_id = self.world_state.culture_map[r, q]
                if culture_id >= 0 and culture_id < len(self.cultures):
                    return self.cultures[culture_id].color
            return (50, 50, 50)  # Uncultured areas

        elif view_mode == ViewMode.RELIGION:
            if hasattr(self.world_state, 'religion_map') and self.world_state.religion_map is not None:
                religion_id = self.world_state.religion_map[r, q]
                if religion_id >= 0 and religion_id < len(self.religions):
                    return self.religions[religion_id].color
            return (30, 30, 30)  # Irreligious areas

        return (100, 100, 100)

    def draw_text_with_border(self, surface: pygame.Surface, text: str, x: int, y: int, 
                              font: pygame.font.Font, text_color=(255, 255, 255), border_color=(0, 0, 0)):
        """Draw text with a black border for better visibility."""
        # Draw border by drawing text in multiple positions
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:  # Don't draw at center position yet
                    border_surface = font.render(text, True, border_color)
                    surface.blit(border_surface, (x + dx, y + dy))
        
        # Draw main text
        text_surface = font.render(text, True, text_color)
        surface.blit(text_surface, (x, y))
        return text_surface.get_rect(topleft=(x, y))

    def get_settlement_type(self, settlement_code: int) -> str:
        """Get settlement type name from settlement map code."""
        settlement_names = {
            0: "hamlet",
            1: "village", 
            2: "town",
            3: "city",
            4: "capital"
        }
        return settlement_names.get(settlement_code, "hamlet")

    def draw_settlement_icon(self, surface: pygame.Surface, cx: int, cy: int,
                             settlement_type: str, is_capital: bool, zoom: float):
        """Draw settlement icon based on type and capital status (with PNG capital if available)."""
        icon_size = max(4, int(8 * zoom))

        if is_capital:
            # If we have a PNG, use it with cached scaling; else fallback to vector star.
            if self.capital_icon is not None:
                target_px = icon_size * 2
                scaled = self._capital_scaled_cache.get(target_px)
                if scaled is None:
                    # Cache by exact pixel size to avoid per-frame rescale cost
                    scaled = pygame.transform.smoothscale(self.capital_icon, (target_px, target_px))
                    self._capital_scaled_cache[target_px] = scaled
                surface.blit(scaled, (cx - icon_size, cy - icon_size))
                return
            else:
                # Fallback: draw golden star
                star_points = []
                for i in range(10):
                    angle = i * math.pi / 5
                    radius = icon_size if i % 2 == 0 else icon_size * 0.5
                    px = cx + radius * math.cos(angle - math.pi / 2)
                    py = cy + radius * math.sin(angle - math.pi / 2)
                    star_points.append((px, py))
                pygame.draw.polygon(surface, (255, 215, 0), star_points)
                pygame.draw.polygon(surface, (0, 0, 0), star_points, max(1, int(zoom)))
                return

        if settlement_type == "city":
            rect = pygame.Rect(cx - icon_size, cy - icon_size, icon_size * 2, icon_size * 2)
            pygame.draw.rect(surface, (200, 200, 200), rect)
            pygame.draw.rect(surface, (0, 0, 0), rect, max(1, int(zoom)))
        elif settlement_type == "town":
            pygame.draw.circle(surface, (150, 150, 150), (cx, cy), icon_size)
            pygame.draw.circle(surface, (0, 0, 0), (cx, cy), icon_size, max(1, int(zoom)))
        elif settlement_type == "village":
            points = [(cx, cy - icon_size), (cx - icon_size, cy + icon_size), (cx + icon_size, cy + icon_size)]
            pygame.draw.polygon(surface, (100, 100, 100), points)
            pygame.draw.polygon(surface, (0, 0, 0), points, max(1, int(zoom)))


class InfoPanel:
    """Expandable panel showing civilization details."""

    def __init__(self):
        self.font_title = pygame.font.Font(None, 24)
        self.font_normal = pygame.font.Font(None, 18)
        self.font_small = pygame.font.Font(None, 16)
        self.expanded = False
        self.current_civ_index = 0
        self.collapsed_rect = pygame.Rect(10, 40, 120, 30)
        self.expanded_size = 220
        self.expanded_rect = self.collapsed_rect.copy()
        self.change_civ_rect = pygame.Rect(0, 0, 0, 0)
        self.close_rect = pygame.Rect(0, 0, 0, 0)
        self.dropdown_open = False
        self.dropdown_rect = pygame.Rect(0, 0, 0, 0)
        self.dropdown_screen_rect = pygame.Rect(0, 0, 0, 0)
        self.dropdown_items = []
        self.hovered_item = -1  # Index of currently hovered dropdown item

    def get_current_civ_id(self, civs: List) -> Optional[int]:
        if not civs:
            return None
        self.current_civ_index %= len(civs)
        return civs[self.current_civ_index].id

    def draw(self, surface: pygame.Surface, world_state: WorldState, civs: List,
             cultures: List, religions: List, engine_civs: List = None):
        if not self.expanded:
            pygame.draw.rect(surface, (30, 30, 40), self.collapsed_rect)
            pygame.draw.rect(surface, (60, 60, 80), self.collapsed_rect, 2)
            txt = self.font_small.render("Info", True, (200, 200, 200))
            surface.blit(txt, (self.collapsed_rect.x + 35, self.collapsed_rect.y + 7))
            return

        self.expanded_rect = pygame.Rect(
            self.collapsed_rect.x, self.collapsed_rect.y,
            self.expanded_size, self.expanded_size
        )
        pygame.draw.rect(surface, (30, 30, 40), self.expanded_rect)
        pygame.draw.rect(surface, (60, 60, 80), self.expanded_rect, 2)

        # Close button
        self.close_rect = pygame.Rect(
            self.expanded_rect.right - 25, self.expanded_rect.y + 5, 20, 20
        )
        pygame.draw.rect(surface, (80, 50, 50), self.close_rect)
        x_txt = self.font_small.render("X", True, (220, 220, 220))
        surface.blit(x_txt, (self.close_rect.x + 6, self.close_rect.y + 2))

        # Civ selector dropdown
        self._draw_civ_dropdown(surface, civs, self.expanded_rect.x + 10, self.expanded_rect.y + 10)

        civ = None
        if civs:
            self.current_civ_index %= len(civs)
            civ = civs[self.current_civ_index]

        x = self.expanded_rect.x + 10
        y = self.expanded_rect.y + 50  # After dropdown + some padding
        if civ:
            # Get culture name from engine civ first (most accurate), then GUI civ
            culture_name = "Unknown"
            engine_civ = None
            if engine_civs:
                engine_civ = next((ec for ec in engine_civs if ec.civ_id == civ.id), None)
                
            if engine_civ and hasattr(engine_civ, 'main_culture') and engine_civ.main_culture:
                culture_name = engine_civ.main_culture
            elif hasattr(civ, 'main_culture') and civ.main_culture:
                culture_name = civ.main_culture
            elif hasattr(civ, 'culture_id') and 0 <= civ.culture_id < len(cultures):
                culture_name = cultures[civ.culture_id].name
                
            religion_name = "Unknown"
            if 0 <= civ.religion_id < len(religions):
                religion_name = religions[civ.religion_id].name
            total_pop = int(world_state.pop_map[world_state.owner_map == civ.id].sum())
            display_total_pop = total_pop * 500  # Inflate population x500 for display
            male = int(display_total_pop * 0.5)
            female = int(display_total_pop) - male
            self._draw_text(surface, f"Name: {civ.name}", x, y); y += 20
            self._draw_text(surface, f"Main Religion: {religion_name}", x, y); y += 20
            self._draw_text(surface, f"Main Culture: {culture_name}", x, y); y += 20
            self._draw_text(surface, f"Male Pop: {male:,}", x, y); y += 20
            self._draw_text(surface, f"Female Pop: {female:,}", x, y); y += 20
            gov = getattr(civ, "government", "Unknown")
            self._draw_text(surface, f"Government: {gov}", x, y); y += 20
            society = getattr(civ, "society", "Unknown")
            self._draw_text(surface, f"Society: {society}", x, y)
        else:
            self._draw_text(surface, "No civilizations", x, y)

    def _draw_text(self, surface: pygame.Surface, text: str, x: int, y: int):
        surface.blit(self.font_normal.render(text, True, (200, 200, 200)), (x, y))

    def _draw_civ_dropdown(self, surface: pygame.Surface, civs: List, x: int, y: int):
        """Draw civilization selector dropdown."""
        if not civs:
            return
            
        # Dropdown button
        dropdown_width = 150
        dropdown_height = 25
        
        self.dropdown_rect = pygame.Rect(x, y, dropdown_width, dropdown_height)
        
        # Current selection
        current_civ_name = civs[self.current_civ_index % len(civs)].name if civs else "No Civ Selected"
        
        # Draw main dropdown button
        button_color = (60, 60, 80) if not self.dropdown_open else (80, 80, 100)
        pygame.draw.rect(surface, button_color, self.dropdown_rect)
        pygame.draw.rect(surface, (100, 100, 120), self.dropdown_rect, 1)
        
        # Dropdown text
        text_surface = self.font_small.render(current_civ_name, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.dropdown_rect.center)
        surface.blit(text_surface, text_rect)
        
        # Dropdown arrow
        arrow_x = x + dropdown_width - 15
        arrow_y = y + dropdown_height // 2
        arrow_points = [
            (arrow_x, arrow_y - 3),
            (arrow_x + 6, arrow_y + 3),
            (arrow_x - 6, arrow_y + 3)
        ]
        pygame.draw.polygon(surface, (200, 200, 200), arrow_points)
        
        # Store dropdown info for later rendering (don't draw list here)
        if self.dropdown_open and civs:
            self.dropdown_items = civs
        else:
            self.dropdown_items = []

    def handle_click(self, mouse_x: int, mouse_y: int, civs: List) -> bool:
        if not self.expanded:
            if self.collapsed_rect.collidepoint(mouse_x, mouse_y):
                self.expanded = True
                return True
            return False

        if self.close_rect.collidepoint(mouse_x, mouse_y):
            self.expanded = False
            return True
            
        # Handle dropdown clicks - check list items first
        if self.dropdown_open and civs:
            # Calculate dropdown list position (same as in render_dropdown_overlay)
            dropdown_width = 150
            dropdown_height = 25
            dropdown_x = self.expanded_rect.x + 10
            dropdown_y = self.expanded_rect.y + 10 + dropdown_height
            list_height = min(len(civs) * 25, 125)  # Max 5 items visible
            dropdown_list_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, list_height)
            
            # First check if clicking on dropdown list items (highest priority)
            if dropdown_list_rect.collidepoint(mouse_x, mouse_y):
                # Calculate which item was clicked
                relative_y = mouse_y - dropdown_y
                item_index = relative_y // 25
                if 0 <= item_index < len(civs):
                    self.current_civ_index = item_index
                    self.dropdown_open = False
                    return True
            # Then check if clicking dropdown button while open
            elif civs and self.dropdown_rect.collidepoint(mouse_x, mouse_y):
                # Clicked dropdown button while open - close it
                self.dropdown_open = False
                return True
            else:
                # Click outside dropdown closes it
                self.dropdown_open = False
                return True
        elif civs and self.dropdown_rect.collidepoint(mouse_x, mouse_y):
            # Open dropdown (only if not currently open)
            self.dropdown_open = True
            return True
        if self.expanded_rect.collidepoint(mouse_x, mouse_y):
            return True
        return False
    
    def render_dropdown_overlay(self, screen: pygame.Surface):
        """Render dropdown list on top of everything else."""
        if not self.expanded or not self.dropdown_open or not self.dropdown_items:
            return
            
        # Dropdown position (same as in _draw_civ_dropdown)
        dropdown_width = 150
        dropdown_height = 25
        dropdown_x = self.expanded_rect.x + 10
        dropdown_y = self.expanded_rect.y + 10 + dropdown_height
        
        # List dimensions
        list_height = min(len(self.dropdown_items) * 25, 125)  # Max 5 items visible
        list_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, list_height)
        
        # Background
        pygame.draw.rect(screen, (40, 40, 50), list_rect)
        pygame.draw.rect(screen, (100, 100, 120), list_rect, 1)
        
        # Items
        for i, civ in enumerate(self.dropdown_items):
            if i * 25 >= list_height:
                break
                
            item_y = dropdown_y + i * 25
            item_rect = pygame.Rect(dropdown_x, item_y, dropdown_width, 25)
            
            # Highlight current selection or hovered item
            if i == self.current_civ_index % len(self.dropdown_items):
                pygame.draw.rect(screen, (80, 100, 80), item_rect)
            elif i == self.hovered_item:
                # Glow effect for hovered item
                pygame.draw.rect(screen, (120, 120, 160), item_rect)  # Light blue glow
                pygame.draw.rect(screen, (160, 160, 200), item_rect, 2)  # Brighter border
                
            # Item text
            text_color = (255, 255, 255) if i != self.hovered_item else (255, 255, 200)  # Slightly yellow when hovered
            item_text = self.font_small.render(civ.name, True, text_color)
            item_text_rect = item_text.get_rect(center=item_rect.center)
            screen.blit(item_text, item_text_rect)
            
        # Update screen rect for click detection
        self.dropdown_screen_rect = list_rect
    
    def update_hover(self, mouse_x: int, mouse_y: int):
        """Update which dropdown item is being hovered."""
        if self.expanded and self.dropdown_open and self.dropdown_items:
            if hasattr(self, 'dropdown_screen_rect') and self.dropdown_screen_rect.collidepoint(mouse_x, mouse_y):
                # Calculate which item is hovered
                relative_y = mouse_y - self.dropdown_screen_rect.y
                item_index = relative_y // 25
                if 0 <= item_index < len(self.dropdown_items):
                    self.hovered_item = item_index
                else:
                    self.hovered_item = -1
            else:
                self.hovered_item = -1
        else:
            self.hovered_item = -1


class ControlPanel:
    """Bottom control panel with game controls."""
    def __init__(self, height: int = 60):
        self.height = height
        self.font = pygame.font.Font(None, 18)
        self.paused = False
        self.game_speed = 1
        self.view_mode = ViewMode.POLITICAL

    def draw(self, surface: pygame.Surface, world_state=None, civs=None):
        panel_y = surface.get_height() - self.height
        panel_rect = pygame.Rect(0, panel_y, surface.get_width(), self.height)
        pygame.draw.rect(surface, (30, 30, 40), panel_rect)
        pygame.draw.rect(surface, (60, 60, 80), panel_rect, 2)

        x_offset = 10
        y_center = panel_y + self.height // 2

        # Pause/Play
        pause_rect = pygame.Rect(x_offset, y_center - 15, 60, 30)
        color = (150, 50, 50) if self.paused else (50, 150, 50)
        pygame.draw.rect(surface, color, pause_rect)
        text = self.font.render("PLAY" if self.paused else "PAUSE", True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=pause_rect.center))
        x_offset += 70

        speed_text = self.font.render(f"Speed: {self.game_speed}x", True, (200, 200, 200))
        surface.blit(speed_text, (x_offset, y_center - 8)); x_offset += 80

        for i, speed in enumerate([1, 2, 3]):
            speed_rect = pygame.Rect(x_offset + i * 35, y_center - 15, 30, 30)
            color = (100, 100, 150) if self.game_speed == speed else (50, 50, 70)
            pygame.draw.rect(surface, color, speed_rect)
            txt = self.font.render(str(speed), True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=speed_rect.center))
        x_offset += 120

        mode_text = self.font.render("View:", True, (200, 200, 200))
        surface.blit(mode_text, (x_offset, y_center - 8)); x_offset += 50
        for i, (mode, label) in enumerate([
            (ViewMode.POLITICAL, "Political"),
            (ViewMode.TERRAIN, "Terrain"),
            (ViewMode.POPULATION, "Population"),
            (ViewMode.RESOURCES, "Resources")
        ]):
            mode_rect = pygame.Rect(x_offset + i * 75, y_center - 15, 70, 30)
            color = (100, 100, 150) if self.view_mode == mode else (50, 50, 70)
            pygame.draw.rect(surface, color, mode_rect)
            txt = self.font.render(label, True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=mode_rect.center))
        x_offset += 320

        # Time Scale (if world_state provided)
        if world_state:
            scale_text = self.font.render("Time:", True, (200, 200, 200))
            surface.blit(scale_text, (x_offset, y_center - 8)); x_offset += 45
            for i, (scale, label) in enumerate([
                ("week", "Week"),
                ("month", "Month"), 
                ("year", "Year")
            ]):
                scale_rect = pygame.Rect(x_offset + i * 60, y_center - 15, 55, 30)
                color = (100, 150, 100) if world_state.time_scale == scale else (50, 70, 50)
                pygame.draw.rect(surface, color, scale_rect)
                txt = self.font.render(label, True, (255, 255, 255))
                surface.blit(txt, txt.get_rect(center=scale_rect.center))
            x_offset += 200

        # Help  
        help_texts = [
            "Mouse: Drag to pan, Wheel to zoom, Click to select",
            "Space: Pause/Play | 1-3: Speed | 4-6: Time Scale | Q/W/E/R: View modes | T: Tech Tree"
        ]
        for i, msg in enumerate(help_texts):
            t = self.font.render(msg, True, (150, 150, 150))
            surface.blit(t, (surface.get_width() - 480, panel_y + 10 + i * 20))

    def handle_click(self, mouse_x: int, mouse_y: int, screen_height: int, world_state=None, civs=None) -> str:
        if mouse_y < screen_height - self.height:
            return ""
        y_center = screen_height - self.height // 2
        # Pause
        if 10 <= mouse_x <= 70 and y_center - 15 <= mouse_y <= y_center + 15:
            self.paused = not self.paused
            return "pause_toggle"
        # Speed
        for i, speed in enumerate([1, 2, 3]):
            x = 160 + i * 35
            if x <= mouse_x <= x + 30 and y_center - 15 <= mouse_y <= y_center + 15:
                self.game_speed = speed
                return f"speed_{speed}"
        # View modes
        for i, mode in enumerate([ViewMode.POLITICAL, ViewMode.TERRAIN, ViewMode.POPULATION, ViewMode.RESOURCES]):
            x = 330 + i * 75
            if x <= mouse_x <= x + 70 and y_center - 15 <= mouse_y <= y_center + 15:
                self.view_mode = mode
                return f"view_{mode.value}"
        
        # Time Scale (if world_state provided)
        if world_state:
            for i, scale in enumerate(["week", "month", "year"]):
                x = 695 + i * 60  # Offset after view modes + "Time:" label
                if x <= mouse_x <= x + 55 and y_center - 15 <= mouse_y <= y_center + 15:
                    world_state.time_scale = scale
                    return f"time_scale_{scale}"
                    
        return ""


class GodsimGUI:
    """Main GUI application for GodsimPy."""
    def __init__(self, world_state: WorldState = None, world_path: str = None):
        pygame.init()

        # Display
        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption("GodsimPy - Civilization Simulation")

        # Load or create world
        if world_state:
            self.world_state = world_state
        elif world_path and os.path.exists(world_path):
            self.world_state = load_npz(world_path)
        else:
            self.world_state = self._create_new_world()

        # Terrain features
        self.feature_map = generate_features(
            self.world_state.biome_map,
            np.random.default_rng(self.world_state.seed + 1000)
        )

        # Generate cultures and religions if not already present
        from sim.cultures import create_cultures_and_religions
        if not hasattr(self.world_state, 'culture_map') or self.world_state.culture_map is None:
            self.cultures, self.religions, culture_map, religion_map = create_cultures_and_religions(
                self.world_state.height, self.world_state.width, self.world_state.biome_map,
                num_cultures=8, num_religions=5, seed=self.world_state.seed + 5000
            )
            self.world_state.culture_map = culture_map
            self.world_state.religion_map = religion_map
        else:
            # Reconstruct culture/religion objects from existing maps
            self.cultures, self.religions = self._reconstruct_cultures_religions()

        # Civs
        self.civs = []
        if (self.world_state.owner_map >= 0).sum() == 0:
            self.world_state, self.civs = initialize_civs(
                self.world_state,
                n_civs=5,
                base_pop=50.0,
                seed=self.world_state.seed + 2000,
                cultures=self.cultures,
                religions=self.religions
            )
        else:
            num_civs = self.world_state.owner_map.max() + 1
            if num_civs > 0:
                # For existing civs, we need to generate them properly with culture names
                colors = make_palette(num_civs)
                
                # Find existing civ capitals
                civ_capitals = {}
                for r in range(self.world_state.height):
                    for c in range(self.world_state.width):
                        owner = self.world_state.owner_map[r, c]
                        if owner >= 0 and owner not in civ_capitals:
                            civ_capitals[owner] = (r, c)
                
                # Create name generator for consistent naming
                from name_generator import NameGenerator
                name_gen = NameGenerator(self.world_state.seed + 2000)
                
                for i in range(num_civs):
                    # Get culture info from the tile where this civ's capital is
                    culture_name = "Unknown Culture"
                    linguistic_type = "latin"
                    
                    if i in civ_capitals:
                        r, c = civ_capitals[i]
                        if hasattr(self.world_state, 'culture_map') and self.world_state.culture_map is not None:
                            culture_id = self.world_state.culture_map[r, c]
                            if culture_id >= 0 and culture_id < len(self.cultures):
                                culture_name = self.cultures[culture_id].name
                                if hasattr(self.cultures[culture_id], 'linguistic_type'):
                                    linguistic_type = self.cultures[culture_id].linguistic_type
                    
                    # Generate civ name using the culture's linguistic type
                    civ_name = name_gen.generate_country_name(style=linguistic_type)
                    
                    from sim.civilization import Civilization
                    self.civs.append(Civilization(
                        id=i,
                        name=civ_name,
                        color=colors[i],
                        rng_seed=self.world_state.seed ^ (i * 9973 + 12345),
                        capital=civ_capitals.get(i),
                        culture_id=self.world_state.culture_map[civ_capitals[i]] if i in civ_capitals and hasattr(self.world_state, 'culture_map') else -1,
                        religion_id=self.world_state.religion_map[civ_capitals[i]] if i in civ_capitals and hasattr(self.world_state, 'religion_map') else -1
                    ))

        # Engine with military features
        self.engine = self._engine_from_state(self.world_state)
        self.selected_army: Optional[Army] = None

        # Components
        self.camera = Camera()
        self.hex_renderer = HexRenderer(self.world_state)
        self.info_panel = InfoPanel()
        self.control_panel = ControlPanel()
        self.isometric_mode = False

        # --- Tech GUI bits (safe if technology not available) ---
        self.tech_window = TechTreeWindow()
        self.age_indicator = AgeProgressIndicator()
        self.tech_overlay = TechMapOverlay()
        self.tech_notifications = TechNotification()
        # Attach the engine's TechnologySystem if available
        self.tech_system: Optional["TechnologySystem"] = getattr(self.engine, "tech_system", None) if _TECH_AVAILABLE else None

        # Popup (optional)
        try:
            from gui.hex_popup import HexPopup
        except ImportError:
            try:
                from hex_popup import HexPopup  # type: ignore[reportMissingImports]
            except ImportError:
                HexPopup = None
        self.hex_popup = HexPopup() if 'HexPopup' in locals() and HexPopup else None

        # State
        self.running = True
        self.clock = pygame.time.Clock()
        self.mouse_dragging = False
        self.drag_start = (0, 0)
        self.last_update = 0
        self.update_interval = 1000  # ms between simulation updates
        self.needs_redraw = True  # Track if we need to redraw the screen

    def _create_new_world(self) -> WorldState:
        w, h = 64, 48
        seed = np.random.randint(0, 100000)
        height, biomes, sea, _ = build_world(
            w, h, seed,
            plate_count=12,
            hex_radius=12.0,
            sea_level_percentile=0.5,
            mountain_h=0.8,
            use_advanced_biomes=True,
        )
        return from_worldgen(height, biomes, sea, w, h, 12.0, seed)

    def _engine_from_state(self, ws: WorldState) -> SimulationEngine:
        """Build a SimulationEngine from the current ``WorldState``."""
        eng = SimulationEngine(width=ws.width, height=ws.height, seed=ws.seed)
        # Create civs in the engine mirroring GUI civs
        for civ in self.civs:
            # Get the culture name from the culture at the civ's capital
            main_culture = "Unknown Culture"
            linguistic_type = "latin"
            
            if civ.capital and hasattr(self.world_state, 'culture_map') and self.world_state.culture_map is not None:
                r, c = civ.capital
                culture_id = self.world_state.culture_map[r, c]
                if culture_id >= 0 and culture_id < len(self.cultures):
                    main_culture = self.cultures[culture_id].name
                    if hasattr(self.cultures[culture_id], 'linguistic_type'):
                        linguistic_type = self.cultures[culture_id].linguistic_type
            
            eng.world.civs[civ.id] = Civ(
                civ_id=civ.id, 
                name=civ.name,
                stock_food=100, 
                tiles=[],
                main_culture=main_culture,
                linguistic_type=linguistic_type
            )
            # Initialize tech system for this civilization
            if hasattr(eng, 'tech_system') and eng.tech_system:
                eng.tech_system.initialize_civ(civ.id)
        # Populate tiles
        for t in eng.world.tiles:
            t.height = float(ws.height_map[t.r, t.q])
            bval = int(ws.biome_map[t.r, t.q])
            try:
                t.biome = Biome(bval).name.lower()
            except Exception:
                t.biome = "grass"
            owner = int(ws.owner_map[t.r, t.q])
            t.owner = owner if owner >= 0 else None
            if t.owner is not None and t.owner in eng.world.civs:
                eng.world.civs[t.owner].tiles.append((t.q, t.r))
            t.pop = int(ws.pop_map[t.r, t.q])
        eng.world.sea_level = ws.sea_level
        eng.world.time_scale = ws.time_scale
        cal = eng.world.calendar
        cal.year = ws.date_year
        cal.month = ws.date_month
        cal.day = ws.date_day
        apply_all_fixes(eng)
        return eng

    def _sync_engine_to_state(self) -> None:
        """Copy mutable state from engine back into world_state for rendering."""
        ws = self.world_state
        for t in self.engine.world.tiles:
            ws.owner_map[t.r, t.q] = t.owner if t.owner is not None else -1
            ws.pop_map[t.r, t.q] = float(t.pop)
        cal = self.engine.world.calendar
        ws.set_date_tuple(cal.month, cal.day, cal.year)
        ws.turn = self.engine.world.turn
        ws.time_scale = self.engine.world.time_scale

    def _move_selection(self, dq: int, dr: int) -> None:
        if not self.hex_renderer.selected_hex:
            return
        q, r = self.hex_renderer.selected_hex
        nq, nr = q + dq, r + dr
        if 0 <= nq < self.world_state.width and 0 <= nr < self.world_state.height:
            self.hex_renderer.selected_hex = (nq, nr)
            self.selected_army = None
            for a in self.engine.world.armies:
                if a.q == nq and a.r == nr:
                    self.selected_army = a
                    break

    def _order_army(self, dq: int, dr: int) -> None:
        if self.selected_army is None:
            return
        target = (self.selected_army.q + dq, self.selected_army.r + dr)
        if self.engine.world.in_bounds(*target):
            self.engine.set_army_target(self.selected_army, target)

    def _reconstruct_cultures_religions(self):
        """Reconstruct culture and religion objects from existing maps."""
        from sim.cultures import (
            generate_culture_names, generate_religion_names, generate_religion_symbols, 
            create_palette
        )
        
        # Find unique culture/religion IDs
        unique_cultures = set()
        unique_religions = set()
        
        culture_origins = {}
        religion_origins = {}
        
        h, w = self.world_state.culture_map.shape
        for r in range(h):
            for c in range(w):
                culture_id = self.world_state.culture_map[r, c]
                religion_id = self.world_state.religion_map[r, c]
                
                if culture_id >= 0:
                    unique_cultures.add(culture_id)
                    if culture_id not in culture_origins:
                        culture_origins[culture_id] = (r, c)
                
                if religion_id >= 0:
                    unique_religions.add(religion_id)
                    if religion_id not in religion_origins:
                        religion_origins[religion_id] = (r, c)
        
        # Create culture objects
        from sim.cultures import Culture, Religion
        num_cultures = max(unique_cultures) + 1 if unique_cultures else 0
        num_religions = max(unique_religions) + 1 if unique_religions else 0
        
        culture_names = generate_culture_names(num_cultures)
        culture_colors = create_palette(num_cultures, hue_offset=0.0)
        cultures = []
        
        for i in range(num_cultures):
            culture = Culture(
                id=i,
                name=culture_names[i],
                color=culture_colors[i],
                origin=culture_origins.get(i, (0, 0))
            )
            cultures.append(culture)
        
        # Create religion objects
        religion_names = generate_religion_names(num_religions)
        religion_symbols = generate_religion_symbols(num_religions)
        religion_colors = create_palette(num_religions, hue_offset=0.3)
        religions = []
        
        for i in range(num_religions):
            religion = Religion(
                id=i,
                name=religion_names[i],
                color=religion_colors[i],
                symbol=religion_symbols[i],
                origin=religion_origins.get(i, (0, 0))
            )
            religions.append(religion)
        
        return cultures, religions

    def handle_events(self):
        events_handled = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                events_handled = True

            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                events_handled = True

            elif event.type == pygame.KEYDOWN:
                events_handled = True
                if event.key == pygame.K_SPACE:
                    self.control_panel.paused = not self.control_panel.paused
                elif event.key == pygame.K_1:
                    self.control_panel.game_speed = 1
                elif event.key == pygame.K_2:
                    self.control_panel.game_speed = 2
                elif event.key == pygame.K_3:
                    self.control_panel.game_speed = 3
                elif event.key == pygame.K_4:
                    self.world_state.time_scale = "week"
                elif event.key == pygame.K_5:
                    self.world_state.time_scale = "month"
                elif event.key == pygame.K_6:
                    self.world_state.time_scale = "year"
                elif event.key == pygame.K_q:
                    self.control_panel.view_mode = ViewMode.POLITICAL
                elif event.key == pygame.K_w:
                    self.control_panel.view_mode = ViewMode.TERRAIN
                elif event.key == pygame.K_e:
                    self.control_panel.view_mode = ViewMode.POPULATION
                elif event.key == pygame.K_r:
                    self.control_panel.view_mode = ViewMode.RESOURCES
                elif event.key == pygame.K_TAB:
                    self.isometric_mode = not self.isometric_mode
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    save_npz(self.world_state, "quicksave.npz")
                    print("World saved to quicksave.npz")
                # --- Tech hotkey: open/close tree for selected civ (if tech available) ---
                elif _TECH_AVAILABLE and TechHotkeys.handle_keypress(
                        event, self.tech_window,
                        self.civs[0].id if self.civs else None):
                    pass
                # Spawn army with 'A'
                elif event.key == pygame.K_a:
                    if self.hex_renderer.selected_hex:
                        q, r = self.hex_renderer.selected_hex
                        owner = int(self.world_state.owner_map[r, q])
                        if owner >= 0:
                            try:
                                self.selected_army = self.engine.add_army(owner, (q, r))
                                self._sync_engine_to_state()
                            except Exception:
                                pass
                # Toggle tech overlay with 'O'
                elif _TECH_AVAILABLE and event.key == pygame.K_o:
                    self.tech_overlay.toggle()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.hex_renderer.selected_hex:
                        q, r = self.hex_renderer.selected_hex
                        self.selected_army = None
                        for a in self.engine.world.armies:
                            if a.q == q and a.r == r:
                                self.selected_army = a
                                break
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    dq = dr = 0
                    if event.key == pygame.K_LEFT:
                        dq = -1
                    elif event.key == pygame.K_RIGHT:
                        dq = 1
                    elif event.key == pygame.K_UP:
                        dr = -1
                    elif event.key == pygame.K_DOWN:
                        dr = 1
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        self._order_army(dq, dr)
                    else:
                        self._move_selection(dq, dr)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                events_handled = True
                if event.button == 1:
                    # Tech window close click
                    civ_name_map = {civ.id: civ.name for civ in self.civs}
                    if self.tech_window.handle_click(event.pos[0], event.pos[1], self.screen.get_size(), civ_name_map):
                        continue
                    # Hex popup close
                    if self.hex_popup and self.hex_popup.visible:
                        if self.hex_popup.handle_click(event.pos[0], event.pos[1]):
                            continue
                    # Panels
                    if self.info_panel.handle_click(event.pos[0], event.pos[1], self.civs):
                        continue
                    action = self.control_panel.handle_click(event.pos[0], event.pos[1], self.screen.get_height(), self.world_state, self.civs)
                    if action:
                        continue
                    # Select hex / start drag
                    # Calculate map rendering area (same as in render method)
                    render_width = self.screen.get_width()
                    render_height = self.screen.get_height() - self.control_panel.height
                    
                    if event.pos[1] < render_height and event.pos[0] < render_width:
                        # Use map surface dimensions for coordinate conversion
                        wx, wy = self.camera.screen_to_world(
                            event.pos[0], event.pos[1],
                            render_width, render_height
                        )
                        hex_pos = self.hex_renderer.get_hex_at_point(wx, wy)
                        if hex_pos:
                            self.hex_renderer.selected_hex = hex_pos
                            if self.hex_popup:
                                sx, sy = self.camera.world_to_screen(wx, wy, render_width, render_height)
                                self.hex_popup.show(hex_pos[0], hex_pos[1], sx, sy)
                        else:
                            if self.hex_popup:
                                self.hex_popup.hide()
                        self.mouse_dragging = True
                        self.drag_start = event.pos
                        # Select army on clicked hex if present
                        self.selected_army = None
                        for a in self.engine.world.armies:
                            if a.q == hex_pos[0] and a.r == hex_pos[1]:
                                self.selected_army = a
                                break

                elif event.button == 4:  # wheel up
                    # Check if scrolling tech window first
                    if self.tech_window.visible and self._mouse_over_tech_window(event.pos[0], event.pos[1]):
                        self.tech_window.handle_scroll(1)
                    else:
                        # Use smaller zoom steps for smoother zooming
                        # Use map surface dimensions for zoom focus point
                        render_width = self.screen.get_width()
                        render_height = self.screen.get_height() - self.control_panel.height
                        
                        # Only zoom if mouse is over map area
                        if event.pos[1] < render_height and event.pos[0] < render_width:
                            self.camera.zoom_at(0.1, event.pos[0], event.pos[1], render_width, render_height)
                elif event.button == 5:  # wheel down
                    # Check if scrolling tech window first  
                    if self.tech_window.visible and self._mouse_over_tech_window(event.pos[0], event.pos[1]):
                        self.tech_window.handle_scroll(-1)
                    else:
                        # Use smaller zoom steps for smoother zooming
                        # Use map surface dimensions for zoom focus point
                        render_width = self.screen.get_width()
                        render_height = self.screen.get_height() - self.control_panel.height
                        
                        # Only zoom if mouse is over map area
                        if event.pos[1] < render_height and event.pos[0] < render_width:
                            self.camera.zoom_at(-0.1, event.pos[0], event.pos[1], render_width, render_height)
                elif event.button == 3 and self.selected_army is not None:
                    render_width = self.screen.get_width()
                    render_height = self.screen.get_height() - self.control_panel.height
                    if event.pos[1] < render_height and event.pos[0] < render_width:
                        wx, wy = self.camera.screen_to_world(
                            event.pos[0], event.pos[1],
                            render_width, render_height
                        )
                        hex_pos = self.hex_renderer.get_hex_at_point(wx, wy)
                        if hex_pos:
                            self.engine.set_army_target(self.selected_army, hex_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                events_handled = True
                if event.button == 1:
                    self.mouse_dragging = False

            elif event.type == pygame.MOUSEMOTION:
                events_handled = True
                if self.mouse_dragging:
                    dx = event.pos[0] - self.drag_start[0]
                    dy = event.pos[1] - self.drag_start[1]
                    self.camera.pan(-dx, -dy)
                    self.drag_start = event.pos
                else:
                    # Calculate map rendering area (same as in render method)
                    render_width = self.screen.get_width()
                    render_height = self.screen.get_height() - self.control_panel.height
                    
                    if (event.pos[1] < render_height and event.pos[0] < render_width):
                        # Use map surface dimensions for coordinate conversion
                        wx, wy = self.camera.screen_to_world(
                            event.pos[0], event.pos[1],
                            render_width, render_height
                        )
                        self.hex_renderer.hovered_hex = self.hex_renderer.get_hex_at_point(wx, wy)
                
                # Update dropdown hover effects
                self.info_panel.update_hover(event.pos[0], event.pos[1])
                if _TECH_AVAILABLE:
                    self.tech_window.update_hover(event.pos[0], event.pos[1])
        
        return events_handled

    def _mouse_over_tech_window(self, mouse_x: int, mouse_y: int) -> bool:
        """Check if mouse is over the tech tree window."""
        if not self.tech_window.visible:
            return False
        
        # Calculate window position (same logic as in tech window draw)
        screen_w, screen_h = self.screen.get_size()
        x = (screen_w - self.tech_window.width) // 2
        y = (screen_h - self.tech_window.height) // 2
        
        return (x <= mouse_x <= x + self.tech_window.width and 
                y <= mouse_y <= y + self.tech_window.height)

    def update(self):
        # Sync pause
        self.world_state.paused = self.control_panel.paused

        simulation_updated = False
        if not self.control_panel.paused:
            current_time = pygame.time.get_ticks()
            adjusted = max(1, self.update_interval // max(1, self.control_panel.game_speed))
            if current_time - self.last_update > adjusted:
                # Step the simulation engine and mirror state back for rendering
                self.engine.world.time_scale = self.world_state.time_scale
                try:
                    self.engine.advance_turn()
                except Exception:
                    pass
                self._sync_engine_to_state()
                self.last_update = current_time
                simulation_updated = True

        # Tech notifications (optional): if your engine emits events, push them here.
        self.tech_notifications.update(pygame.time.get_ticks())

        if self.hex_popup:
            self.hex_popup.update()
        
        return simulation_updated

    def render(self):
        self.screen.fill((10, 10, 30))

        # Map area dims
        render_width = self.screen.get_width()
        render_height = self.screen.get_height() - self.control_panel.height
        map_surface = pygame.Surface((render_width, render_height))

        if self.isometric_mode:
            img = render_iso(
                self.world_state.height_map,
                self.world_state.biome_map,
                self.world_state.hex_radius,
                sea_level=self.world_state.sea_level,
            )
            iso_surf = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
            iso_surf = pygame.transform.smoothscale(iso_surf, (render_width, render_height))
            map_surface.blit(iso_surf, (0, 0))
        else:
            self.hex_renderer.render(
                map_surface, self.camera, self.control_panel.view_mode,
                tech_overlay=self.tech_overlay if _TECH_AVAILABLE else None,
                tech_system=self.tech_system,
                civs=self.civs
            )

        # Draw armies on top of the map
        if not self.isometric_mode:
            for a in self.engine.world.armies:
                cx, cy = _evenq_center(a.q, a.r, self.hex_renderer.hex_radius)
                sx, sy = self.camera.world_to_screen(cx, cy, render_width, render_height)
                rad = int(self.hex_renderer.hex_radius * 0.3 * self.camera.zoom)
                rect_w = rad * 2
                rect_h = rad
                rect = pygame.Rect(sx - rect_w // 2, sy - rect_h // 2, rect_w, rect_h)
                pygame.draw.rect(map_surface, (255, 255, 255), rect)
                pygame.draw.rect(map_surface, (0, 0, 0), rect, 2)
                pygame.draw.line(map_surface, (0, 0, 0), rect.topleft, rect.bottomright, 2)
                pygame.draw.line(map_surface, (0, 0, 0), rect.topright, rect.bottomleft, 2)
                if a is self.selected_army:
                    pygame.draw.rect(map_surface, (255, 255, 255), rect.inflate(4, 4), 2)

        self.screen.blit(map_surface, (0, 0))

        # Panels
        # Pass both GUI civs and engine civs for culture info
        engine_civs = list(self.engine.world.civs.values()) if hasattr(self, 'engine') and self.engine else []
        self.info_panel.draw(self.screen, self.world_state, self.civs, self.cultures, self.religions, engine_civs)
        self.control_panel.draw(self.screen, self.world_state, self.civs)

        # Hex popup
        if self.hex_popup:
            self.hex_popup.draw(self.screen, self.world_state, self.civs, self.feature_map)

        # Age indicators removed - use civ selector instead

        # Tech tree window (centered)
        if _TECH_AVAILABLE:
            # Civ name map for window header
            civ_name_map = {civ.id: civ.name for civ in self.civs}
            self.tech_window.draw(self.screen, self.tech_system, civ_name_map)

        # Tech notifications (top-right)
        if _TECH_AVAILABLE:
            self.tech_notifications.draw(self.screen, self.screen.get_width() - 320, 10)

        # FPS
        fps = int(self.clock.get_fps())
        fps_text = pygame.font.Font(None, 20).render(f"FPS: {fps}", True, (200, 200, 200))
        self.screen.blit(fps_text, (10, 10))
        if self.selected_army is not None and self.selected_army in self.engine.world.armies:
            info = (f"Army civ:{self.selected_army.civ_id} "
                    f"str:{self.selected_army.strength} "
                    f"tgt:{self.selected_army.target}")
            info_text = pygame.font.Font(None, 20).render(info, True, (200, 200, 200))
            self.screen.blit(info_text, (10, 30))

        # Date display (bottom left, above control panel)
        month, day, year = self.world_state.get_date_tuple()
        date_string = f"{month:02d}/{day:02d}/{year}"
        date_font = pygame.font.Font(None, 24)
        date_text = date_font.render(date_string, True, (220, 220, 220))
        date_y = self.screen.get_height() - self.control_panel.height - 30
        self.screen.blit(date_text, (10, date_y))

        # Update hover states and render dropdown overlays on top of everything else
        mouse_x, mouse_y = pygame.mouse.get_pos()
        self.info_panel.update_hover(mouse_x, mouse_y)
        if _TECH_AVAILABLE:
            self.tech_window.update_hover(mouse_x, mouse_y)
            
        self.info_panel.render_dropdown_overlay(self.screen)
        if _TECH_AVAILABLE:
            self.tech_window.render_dropdown_overlay(self.screen)

        pygame.display.flip()

    # (Kept for completeness; your array-based top-down renderer)
    def render_topdown_view(self, surface: pygame.Surface, view_mode: ViewMode):
        H, W = self.world_state.height, self.world_state.width
        if view_mode == ViewMode.TERRAIN:
            color_array = self.world_state.biome_map.copy()
            img = render_topdown(color_array, self.world_state.hex_radius, scale=1)
        elif view_mode == ViewMode.POLITICAL:
            img = render_topdown_political(
                self.world_state.owner_map, self.world_state.biome_map,
                self.hex_renderer.civ_colors, self.hex_renderer.BIOME_COLORS,
                self.world_state.hex_radius
            )
        elif view_mode == ViewMode.POPULATION:
            color_array = np.zeros((H, W), dtype=np.int32)
            for r in range(H):
                for q in range(W):
                    pop = self.world_state.pop_map[r, q]
                    color_array[r, q] = min(3, int(pop / 5)) if pop > 0 else 0
            img = render_topdown(color_array, self.world_state.hex_radius, scale=1)
        else:
            img = render_topdown_height(self.world_state.height_map, self.world_state.hex_radius, scale=1)

        topdown_surf = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
        surf_w, surf_h = surface.get_size()
        img_w, img_h = img.size
        scale = min(surf_w / img_w, surf_h / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        topdown_surf = pygame.transform.smoothscale(topdown_surf, (new_w, new_h))
        x_off = (surf_w - new_w) // 2
        y_off = (surf_h - new_h) // 2
        surface.fill((16, 18, 24))
        surface.blit(topdown_surf, (x_off, y_off))

    def run(self):
        while self.running:
            events_handled = self.handle_events()
            simulation_updated = self.update()
            
            # Optimized rendering: only render when necessary
            should_render = (self.needs_redraw or 
                           events_handled or 
                           simulation_updated or
                           (not self.control_panel.paused))  # Always render when not paused for smooth animation
            
            if should_render:
                self.render()
                self.needs_redraw = False
            
            # Maintain 60 FPS even when paused for smooth UI interaction
            target_fps = 60
            self.clock.tick(target_fps)
        pygame.quit()


def main():
    """Entry point for the GUI application."""
    import argparse
    parser = argparse.ArgumentParser(description="GodsimPy GUI")
    parser.add_argument("--load", type=str, help="Path to world NPZ file to load")
    parser.add_argument("--width", type=int, default=100, help="World width in hexes")
    parser.add_argument("--height", type=int, default=60, help="World height in hexes")
    parser.add_argument("--seed", type=int, help="Random seed for world generation")
    parser.add_argument("--civs", type=int, default=5, help="Number of civilizations")
    args = parser.parse_args()

    world_state = None
    if args.load and os.path.exists(args.load):
        print(f"Loading world from {args.load}")
        world_state = load_npz(args.load)
    else:
        print(f"Generating new world ({args.width}x{args.height})")
        seed = args.seed if args.seed else np.random.randint(0, 100000)
        height, biomes, sea, _ = build_world(
            args.width, args.height, seed,
            plate_count=12, hex_radius=12.0,
            sea_level_percentile=0.5, mountain_h=0.8,
            use_advanced_biomes=True,
        )
        world_state = from_worldgen(height, biomes, sea, args.width, args.height, 12.0, seed)
        # Don't initialize civs here - let GodsimGUI do it properly with cultures

    gui = GodsimGUI(world_state=world_state)
    gui.run()


if __name__ == "__main__":
    main()
