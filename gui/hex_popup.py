#!/usr/bin/env python3
"""Hex tile information popup for detailed tile inspection."""

import pygame
import numpy as np
from typing import Optional, Tuple, List
from sim.state import WorldState
from sim.resources import biome_yields, carrying_capacity, yields_with_features
from sim.terrain import describe_feature


class HexPopup:
    """Popup window that displays detailed information about a hex tile."""
    
    def __init__(self):
        self.visible = False
        self.tile_pos: Optional[Tuple[int, int]] = None
        self.screen_pos: Tuple[int, int] = (0, 0)
        
        # Fonts
        self.font_title = pygame.font.Font(None, 20)
        self.font_header = pygame.font.Font(None, 18)
        self.font_normal = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 14)
        
        # Popup dimensions
        self.width = 280
        self.height = 400
        self.padding = 10
        
        # Animation
        self.alpha = 0
        self.target_alpha = 0
        self.fade_speed = 15
        
        # Cached data to avoid expensive recalculations
        self._cached_tile_pos: Optional[Tuple[int, int]] = None
        self._cached_popup_surface: Optional[pygame.Surface] = None
        self._cached_world_turn: Optional[int] = None
        self._cached_yields: Optional[dict] = None
        
    def show(self, tile_q: int, tile_r: int, screen_x: int, screen_y: int):
        """Show the popup for a specific tile."""
        new_tile_pos = (tile_q, tile_r)
        
        # Invalidate cache if tile changed
        if new_tile_pos != self._cached_tile_pos:
            self._cached_tile_pos = None
            self._cached_popup_surface = None
            self._cached_world_turn = None
            self._cached_yields = None
        
        self.tile_pos = new_tile_pos
        self.screen_pos = (screen_x, screen_y)
        self.visible = True
        self.target_alpha = 255
        
    def hide(self):
        """Hide the popup."""
        self.target_alpha = 0
        
    def update(self):
        """Update animation state."""
        if self.alpha < self.target_alpha:
            self.alpha = min(255, self.alpha + self.fade_speed)
        elif self.alpha > self.target_alpha:
            self.alpha = max(0, self.alpha - self.fade_speed)
            if self.alpha == 0:
                self.visible = False
    
    def draw(self, surface: pygame.Surface, world_state: WorldState, 
             civs: List, feature_map: Optional[np.ndarray] = None):
        """Draw the popup on the screen."""
        if not self.visible or self.alpha == 0 or not self.tile_pos:
            return
        
        # Check if we need to regenerate the popup content
        need_regenerate = (self._cached_tile_pos != self.tile_pos or 
                          self._cached_world_turn != world_state.turn or
                          self._cached_popup_surface is None)
        
        if need_regenerate:
            self._generate_popup_content(world_state, civs, feature_map)
        
        # Calculate popup position (avoid going off-screen)
        x = self.screen_pos[0] + 20
        y = self.screen_pos[1] - self.height // 2
        
        # Adjust if popup would go off-screen
        if x + self.width > surface.get_width():
            x = self.screen_pos[0] - self.width - 20
        if y < 0:
            y = 10
        if y + self.height > surface.get_height():
            y = surface.get_height() - self.height - 10
        
        # Apply current alpha to cached surface and draw
        if self._cached_popup_surface:
            display_surface = self._cached_popup_surface.copy()
            display_surface.set_alpha(self.alpha)
            surface.blit(display_surface, (x, y))
    
    def _generate_popup_content(self, world_state: WorldState, civs: List, 
                               feature_map: Optional[np.ndarray] = None):
        """Generate the popup content surface (cached)."""
        if not self.tile_pos:
            return
            
        q, r = self.tile_pos
        
        # Create popup surface
        popup_surface = pygame.Surface((self.width, self.height))
        
        # Draw background
        pygame.draw.rect(popup_surface, (20, 20, 30), (0, 0, self.width, self.height))
        pygame.draw.rect(popup_surface, (100, 100, 120), (0, 0, self.width, self.height), 2)
        
        # Draw content
        y_offset = self.padding
        
        # Title with coordinates
        title_text = f"Hex Tile ({q}, {r})"
        self._draw_text(popup_surface, title_text, self.padding, y_offset, 
                       self.font_title, (255, 255, 100))
        y_offset += 25
        
        # Separator line
        pygame.draw.line(popup_surface, (60, 60, 80), 
                        (self.padding, y_offset), 
                        (self.width - self.padding, y_offset), 1)
        y_offset += 10
        
        # Terrain Information
        self._draw_section(popup_surface, "TERRAIN", y_offset)
        y_offset += 22
        
        # Biome
        biome_names = {
            0: ("Grassland", (34, 139, 34)),
            1: ("Coast", (238, 203, 173)),
            2: ("Mountain", (139, 137, 137)),
            3: ("Ocean", (0, 119, 190)),
            4: ("Desert", (238, 203, 173))
        }
        biome = world_state.biome_map[r, q]
        biome_name, biome_color = biome_names.get(biome, ("Unknown", (100, 100, 100)))
        
        # Draw biome with color indicator
        color_box = pygame.Rect(self.padding + 5, y_offset + 2, 10, 10)
        pygame.draw.rect(popup_surface, biome_color, color_box)
        self._draw_text(popup_surface, f"Biome: {biome_name}", self.padding + 20, y_offset)
        y_offset += 18
        
        # Height
        height = world_state.height_map[r, q]
        height_text = f"Elevation: {height:.2f}"
        self._draw_text(popup_surface, height_text, self.padding + 5, y_offset)
        y_offset += 18
        
        # Terrain feature
        if feature_map is not None:
            feature = feature_map[r, q]
            feature_name = describe_feature(feature)
            if feature_name != "None":
                self._draw_text(popup_surface, f"Feature: {feature_name}", 
                               self.padding + 5, y_offset)
                y_offset += 18
        
        y_offset += 10
        
        # Ownership Information
        self._draw_section(popup_surface, "OWNERSHIP", y_offset)
        y_offset += 22
        
        owner = world_state.owner_map[r, q]
        if owner >= 0 and owner < len(civs):
            civ = civs[owner]
            # Draw civ color
            color_box = pygame.Rect(self.padding + 5, y_offset + 2, 10, 10)
            pygame.draw.rect(popup_surface, civ.color, color_box)
            self._draw_text(popup_surface, f"Owner: {civ.name}", self.padding + 20, y_offset)
            y_offset += 18
            
            # Territory age (based on turn - this is approximate)
            self._draw_text(popup_surface, f"Controlled for: ~{world_state.turn // 2} turns", 
                           self.padding + 5, y_offset)
            y_offset += 18
        else:
            self._draw_text(popup_surface, "Owner: Uncontrolled", self.padding + 5, y_offset, 
                           color=(150, 150, 150))
            y_offset += 18
        
        y_offset += 10
        
        # Population Information
        self._draw_section(popup_surface, "POPULATION", y_offset)
        y_offset += 22
        
        pop = world_state.pop_map[r, q]
        self._draw_text(popup_surface, f"Current: {int(pop)} people", self.padding + 5, y_offset)
        y_offset += 18
        
        # Calculate carrying capacity (cache yields calculation)
        if self._cached_yields is None:
            if feature_map is not None:
                self._cached_yields = yields_with_features(world_state.biome_map, feature_map)
            else:
                self._cached_yields = biome_yields(world_state.biome_map)
        
        yields = self._cached_yields
        K = carrying_capacity(yields["food"])
        capacity = K[r, q]
        self._draw_text(popup_surface, f"Capacity: {int(capacity)} people", 
                       self.padding + 5, y_offset)
        y_offset += 18
        
        # Population percentage bar
        if capacity > 0:
            fill_percent = min(1.0, pop / capacity)
            bar_width = self.width - 2 * self.padding - 10
            bar_height = 12
            bar_x = self.padding + 5
            bar_y = y_offset
            
            # Background
            pygame.draw.rect(popup_surface, (40, 40, 40), 
                           (bar_x, bar_y, bar_width, bar_height))
            # Fill
            fill_color = (50, 200, 50) if fill_percent < 0.8 else (200, 200, 50) if fill_percent < 1.0 else (200, 50, 50)
            pygame.draw.rect(popup_surface, fill_color,
                           (bar_x, bar_y, int(bar_width * fill_percent), bar_height))
            # Border
            pygame.draw.rect(popup_surface, (80, 80, 80),
                           (bar_x, bar_y, bar_width, bar_height), 1)
            
            # Percentage text
            percent_text = f"{int(fill_percent * 100)}%"
            text_surf = self.font_small.render(percent_text, True, (255, 255, 255))
            text_rect = text_surf.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
            popup_surface.blit(text_surf, text_rect)
            
            y_offset += bar_height + 8
        
        y_offset += 10
        
        # Resource Yields
        self._draw_section(popup_surface, "RESOURCES", y_offset)
        y_offset += 22
        
        food = yields["food"][r, q]
        prod = yields["prod"][r, q]
        
        # Food with icon
        self._draw_resource_bar(popup_surface, "Food", food, 1.2, 
                               (50, 200, 50), self.padding + 5, y_offset)
        y_offset += 20
        
        # Production with icon
        self._draw_resource_bar(popup_surface, "Production", prod, 1.2,
                               (200, 150, 50), self.padding + 5, y_offset)
        y_offset += 20
        
        # Strategic value (simple calculation)
        strategic_value = (food * 2 + prod) / 3.0
        self._draw_resource_bar(popup_surface, "Strategic", strategic_value, 1.0,
                               (150, 150, 200), self.padding + 5, y_offset)
        y_offset += 25
        
        # Neighbors summary
        self._draw_section(popup_surface, "NEIGHBORS", y_offset)
        y_offset += 22
        
        # Count neighboring civs (this is quick so we keep it fresh)
        neighbor_civs = set()
        for dq, dr in [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]:
            nq, nr = q + dq, r + dr
            if 0 <= nq < world_state.width and 0 <= nr < world_state.height:
                n_owner = world_state.owner_map[nr, nq]
                if n_owner >= 0:
                    neighbor_civs.add(n_owner)
        
        if neighbor_civs:
            if owner >= 0:
                neighbor_civs.discard(owner)  # Remove self
            
            if neighbor_civs:
                for civ_id in list(neighbor_civs)[:3]:  # Show up to 3 neighbors
                    if civ_id < len(civs):
                        civ = civs[civ_id]
                        color_box = pygame.Rect(self.padding + 5, y_offset + 2, 8, 8)
                        pygame.draw.rect(popup_surface, civ.color, color_box)
                        self._draw_text(popup_surface, civ.name, self.padding + 18, y_offset,
                                       font=self.font_small)
                        y_offset += 15
            else:
                self._draw_text(popup_surface, "No foreign neighbors", self.padding + 5, y_offset,
                               font=self.font_small, color=(150, 150, 150))
        else:
            self._draw_text(popup_surface, "Isolated tile", self.padding + 5, y_offset,
                           font=self.font_small, color=(150, 150, 150))
        
        # Cache the generated surface and metadata
        self._cached_popup_surface = popup_surface
        self._cached_tile_pos = self.tile_pos
        self._cached_world_turn = world_state.turn
    
    def _draw_text(self, surface: pygame.Surface, text: str, x: int, y: int,
                   font: Optional[pygame.font.Font] = None, 
                   color: Tuple[int, int, int] = (200, 200, 200)):
        """Draw text on the surface."""
        if font is None:
            font = self.font_normal
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, (x, y))
    
    def _draw_section(self, surface: pygame.Surface, title: str, y: int):
        """Draw a section header."""
        self._draw_text(surface, title, self.padding, y, self.font_header, (150, 150, 255))
        pygame.draw.line(surface, (60, 60, 100),
                        (self.padding, y + 18),
                        (self.width - self.padding, y + 18), 1)
    
    def _draw_resource_bar(self, surface: pygame.Surface, label: str, value: float, max_value: float,
                          color: Tuple[int, int, int], x: int, y: int):
        """Draw a resource bar with label and value."""
        # Label
        self._draw_text(surface, f"{label}:", x, y, font=self.font_small)
        
        # Value text
        value_text = f"{value:.2f}"
        value_x = x + 80
        self._draw_text(surface, value_text, value_x, y, font=self.font_small)
        
        # Bar
        bar_x = x + 120
        bar_width = self.width - bar_x - self.padding - 5
        bar_height = 10
        
        # Background
        pygame.draw.rect(surface, (40, 40, 40), (bar_x, y + 2, bar_width, bar_height))
        
        # Fill
        fill_width = int(bar_width * min(1.0, value / max_value))
        if fill_width > 0:
            pygame.draw.rect(surface, color, (bar_x, y + 2, fill_width, bar_height))
        
        # Border
        pygame.draw.rect(surface, (80, 80, 80), (bar_x, y + 2, bar_width, bar_height), 1)
    
    def handle_click(self, mouse_x: int, mouse_y: int) -> bool:
        """Check if click is on the popup. Returns True if clicked outside to close."""
        if not self.visible:
            return False
        
        # Calculate popup bounds
        x = self.screen_pos[0] + 20
        y = self.screen_pos[1] - self.height // 2
        
        # Check if click is outside popup
        if (mouse_x < x or mouse_x > x + self.width or
            mouse_y < y or mouse_y > y + self.height):
            self.hide()
            return True
        
        return False