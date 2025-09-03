#!/usr/bin/env python3
"""GodsimPy GUI - Main application for interactive civilization simulation."""

import os
import sys
import math
import pygame
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List
from enum import Enum

# --- top-down deskew helpers (used by HexRenderer) ---
DESKEW_Y = 1.0 / math.sqrt(3.0)

SQRT3 = math.sqrt(3.0)

def _evenq_center(q: int, r: int, radius: float) -> tuple[float, float]:
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

def _deskew(x: float, y: float) -> tuple[float, float]:
    # Cancel axial's built-in √3 vertical stretch so top-down looks rectangular
    return x, y * DESKEW_Y

def _to_rect_space(x: float, y: float, q: int, r_hex: float) -> tuple[float, float]:
    """
    Convert raw axial pixel coords (flat-top) into rectangular top-down space:
      y' = y / √3  -  0.5 * r_hex * q
    """
    return x, y * DESKEW_Y - 0.5 * r_hex * q

from sim.state import WorldState, load_npz, save_npz
from sim.loop import advance_turn
from sim.resources import biome_yields
from sim.terrain import generate_features, describe_feature
from sim.civilization import initialize_civs, make_palette
from worldgen import axial_to_world_flat, build_world, build_biomes
from sim.state import from_worldgen
from render import render_topdown, render_iso
from render.render_topdown import render_topdown_height, render_topdown_political
# NEW: pointy-top mapping for square-looking top-down
from worldgen.hexgrid import axial_to_world_pointy

# Import hex popup if available
try:
    from gui.hex_popup import HexPopup
except ImportError:
    # Fallback if hex_popup.py is in same directory
    try:
        from hex_popup import HexPopup
    except ImportError:
        HexPopup = None


class ViewMode(Enum):
    POLITICAL = "political"
    TERRAIN = "terrain"
    POPULATION = "population"
    RESOURCES = "resources"


@dataclass
class Camera:
    """Camera for panning and zooming the hex map."""
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    min_zoom: float = 0.3
    max_zoom: float = 3.0

    def pan(self, dx: float, dy: float):
        self.x += dx / self.zoom
        self.y += dy / self.zoom
    
    def zoom_at(self, zoom_delta: float, focus_x: float, focus_y: float):
        old_zoom = self.zoom
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * (1 + zoom_delta)))
        
        # Adjust position to zoom at focus point
        scale_change = self.zoom / old_zoom
        self.x = focus_x - (focus_x - self.x) * scale_change
        self.y = focus_y - (focus_y - self.y) * scale_change
    
    def world_to_screen(self, wx: float, wy: float, screen_width: int, screen_height: int) -> Tuple[int, int]:
        sx = (wx - self.x) * self.zoom + screen_width // 2
        sy = (wy - self.y) * self.zoom + screen_height // 2
        return int(sx), int(sy)
    
    def screen_to_world(self, sx: int, sy: int, screen_width: int, screen_height: int) -> Tuple[float, float]:
        wx = (sx - screen_width // 2) / self.zoom + self.x
        wy = (sy - screen_height // 2) / self.zoom + self.y
        return wx, wy


class HexRenderer:
    """Renders hexagonal map with different view modes (pointy-top in top-down)."""
    
    # Color schemes for different biomes
    BIOME_COLORS = {
        0: (34, 139, 34),    # Grass - Forest Green
        1: (238, 203, 173),  # Coast - Peach
        2: (139, 137, 137),  # Mountain - Gray
        3: (0, 119, 190),    # Ocean - Deep Blue
        4: (238, 203, 173),  # Sand/Desert - Sandy
    }
    
    def __init__(self, world_state: WorldState, hex_radius: float = 40.0):
        self.world_state = world_state
        self.hex_radius = hex_radius
        self.selected_hex: Optional[Tuple[int, int]] = None
        self.hovered_hex: Optional[Tuple[int, int]] = None
        self.civ_colors = make_palette(10)  # Support up to 10 civs

    
        
    def get_hex_at_point(self, wx: float, wy: float) -> Optional[Tuple[int, int]]:
        """World -> (q,r) using even-q centers (regular flat-top hexes)."""
        best_q = best_r = None
        best_d2 = float("inf")
        r_hex = self.hex_radius
        pick_r2 = (0.95 * r_hex) ** 2

        for r in range(self.world_state.height):
            for q in range(self.world_state.width):
                cx, cy = _evenq_center(q, r, r_hex)
                d2 = (wx - cx) ** 2 + (wy - cy) ** 2
                if d2 < best_d2 and d2 <= pick_r2:
                    best_d2, best_q, best_r = d2, q, r

        return (best_q, best_r) if best_q is not None else None

    def draw_hex(
        self,
        surface: pygame.Surface,
        q: int,
        r: int,
        color: Tuple[int, int, int],
        camera: Camera,
        outline_color: Optional[Tuple[int, int, int]] = None,
    ):
        """Draw one flat-top hex at its even-q center."""
        cx, cy = _evenq_center(q, r, self.hex_radius)

        verts = []
        # flat-top vertices: 0°, 60°, 120°, ...
        for i in range(6):
            ang = math.radians(60 * i)
            vx = cx + self.hex_radius * math.cos(ang)
            vy = cy + self.hex_radius * math.sin(ang)
            sx, sy = camera.world_to_screen(vx, vy, surface.get_width(), surface.get_height())
            verts.append((sx, sy))

        # (optional) quick cull
        if all(
            sx < -50 or sx > surface.get_width() + 50 or
            sy < -50 or sy > surface.get_height() + 50
            for sx, sy in verts
        ):
            return

        pygame.draw.polygon(surface, color, verts)
        if outline_color:
            pygame.draw.polygon(surface, outline_color, verts, 2)
        elif self.selected_hex == (q, r):
            pygame.draw.polygon(surface, (255, 255, 0), verts, 3)
        elif self.hovered_hex == (q, r):
            pygame.draw.polygon(surface, (255, 255, 255), verts, 2)
    
    def get_hex_color(self, q: int, r: int, view_mode: ViewMode) -> Tuple[int, int, int]:
        """Get color for hex based on view mode."""
        if view_mode == ViewMode.TERRAIN:
            biome = self.world_state.biome_map[r, q]
            return self.BIOME_COLORS.get(biome, (100, 100, 100))
        
        elif view_mode == ViewMode.POLITICAL:
            owner = self.world_state.owner_map[r, q]
            if owner >= 0:
                return self.civ_colors[owner % len(self.civ_colors)]
            else:
                # Darken terrain color for unowned tiles
                biome = self.world_state.biome_map[r, q]
                base_color = self.BIOME_COLORS.get(biome, (100, 100, 100))
                return tuple(int(c * 0.6) for c in base_color)
        
        elif view_mode == ViewMode.POPULATION:
            pop = self.world_state.pop_map[r, q]
            if pop > 0:
                # Color intensity based on population
                intensity = min(255, int(pop * 2))
                return (intensity, intensity // 2, 0)
            else:
                return (20, 20, 20)
        
        elif view_mode == ViewMode.RESOURCES:
            yields = biome_yields(self.world_state.biome_map)
            food = yields["food"][r, q]
            # Green intensity based on food yield
            intensity = int(min(255, food * 200))
            return (0, intensity, 0)
        
        return (100, 100, 100)
    
    def render(self, surface: pygame.Surface, camera: Camera, view_mode: ViewMode):
        """Render the entire hex map (pointy-top in top-down)."""
        # Clear background
        surface.fill((10, 10, 30))
        
        # Draw hexes
        for r in range(self.world_state.height):
            for q in range(self.world_state.width):
                color = self.get_hex_color(q, r, view_mode)
                outline = None
                
                # Outline owned tiles in terrain view
                if view_mode == ViewMode.TERRAIN and self.world_state.owner_map[r, q] >= 0:
                    owner = self.world_state.owner_map[r, q]
                    outline = self.civ_colors[owner % len(self.civ_colors)]
                
                self.draw_hex(surface, q, r, color, camera, outline)


class InfoPanel:
    """Right-side information panel for civilization and tile info."""
    
    def __init__(self, width: int = 300):
        self.width = width
        self.font_title = pygame.font.Font(None, 24)
        self.font_normal = pygame.font.Font(None, 18)
        self.font_small = pygame.font.Font(None, 16)
        self.collapsed = False
        self.selected_tile: Optional[Tuple[int, int]] = None
        self.feature_map: Optional[np.ndarray] = None
        
    def draw(self, surface: pygame.Surface, world_state: WorldState, civs: List):
        """Draw the info panel."""
        panel_height = surface.get_height()
        panel_x = surface.get_width() - self.width
        
        # Draw panel background
        panel_rect = pygame.Rect(panel_x, 0, self.width, panel_height)
        pygame.draw.rect(surface, (30, 30, 40), panel_rect)
        pygame.draw.rect(surface, (60, 60, 80), panel_rect, 2)
        
        # Draw collapse button
        button_rect = pygame.Rect(panel_x + 5, 5, 30, 20)
        pygame.draw.rect(surface, (50, 50, 70), button_rect)
        arrow = "<" if not self.collapsed else ">"
        arrow_text = self.font_small.render(arrow, True, (200, 200, 200))
        surface.blit(arrow_text, (panel_x + 15, 7))
        
        if self.collapsed:
            return
        
        # Title
        title = self.font_title.render("INFO", True, (255, 255, 255))
        surface.blit(title, (panel_x + 45, 5))
        
        y_offset = 35
        
        # World info section
        self._draw_section_header(surface, "WORLD", panel_x + 10, y_offset)
        y_offset += 25
        
        # Date and turn
        m, d, y = world_state.get_date_tuple()
        date_text = f"Date: {m}/{d}/{y}"
        turn_text = f"Turn: {world_state.turn}"
        time_text = f"Time Scale: {world_state.time_scale}"
        
        self._draw_text(surface, date_text, panel_x + 15, y_offset)
        y_offset += 20
        self._draw_text(surface, turn_text, panel_x + 15, y_offset)
        y_offset += 20
        self._draw_text(surface, time_text, panel_x + 15, y_offset)
        y_offset += 30
        
        # Population info
        total_pop = world_state.pop_map.sum()
        owned_tiles = (world_state.owner_map >= 0).sum()
        self._draw_section_header(surface, "STATISTICS", panel_x + 10, y_offset)
        y_offset += 25
        self._draw_text(surface, f"Total Population: {int(total_pop)}", panel_x + 15, y_offset)
        y_offset += 20
        self._draw_text(surface, f"Owned Tiles: {owned_tiles}", panel_x + 15, y_offset)
        y_offset += 30
        
        # Civilizations section
        if civs:
            self._draw_section_header(surface, "CIVILIZATIONS", panel_x + 10, y_offset)
            y_offset += 25
            
            for civ in civs[:5]:  # Show top 5 civs
                # Calculate civ population
                civ_pop = world_state.pop_map[world_state.owner_map == civ.id].sum()
                civ_tiles = (world_state.owner_map == civ.id).sum()
                
                # Draw civ color box
                color_box = pygame.Rect(panel_x + 15, y_offset, 12, 12)
                pygame.draw.rect(surface, civ.color, color_box)
                
                # Draw civ name and stats
                civ_text = f"{civ.name}: {int(civ_pop)} pop, {civ_tiles} tiles"
                self._draw_text(surface, civ_text, panel_x + 32, y_offset, size='small')
                y_offset += 18
            
            y_offset += 20
        
        # Selected tile info
        if self.selected_tile:
            q, r = self.selected_tile
            self._draw_section_header(surface, f"TILE ({q}, {r})", panel_x + 10, y_offset)
            y_offset += 25
            
            # Biome
            biome_names = {0: "Grassland", 1: "Coast", 2: "Mountain", 3: "Ocean", 4: "Desert"}
            biome = world_state.biome_map[r, q]
            biome_name = biome_names.get(biome, "Unknown")
            self._draw_text(surface, f"Biome: {biome_name}", panel_x + 15, y_offset)
            y_offset += 20
            
            # Terrain feature
            if self.feature_map is not None:
                feature = self.feature_map[r, q]
                feature_name = describe_feature(feature)
                if feature_name != "None":
                    self._draw_text(surface, f"Feature: {feature_name}", panel_x + 15, y_offset)
                    y_offset += 20
            
            # Owner
            owner = world_state.owner_map[r, q]
            if owner >= 0 and owner < len(civs):
                self._draw_text(surface, f"Owner: {civs[owner].name}", panel_x + 15, y_offset)
                y_offset += 20
            else:
                self._draw_text(surface, "Owner: None", panel_x + 15, y_offset)
                y_offset += 20
            
            # Population
            pop = world_state.pop_map[r, q]
            self._draw_text(surface, f"Population: {int(pop)}", panel_x + 15, y_offset)
            y_offset += 20
            
            # Resources
            yields = biome_yields(world_state.biome_map)
            food = yields["food"][r, q]
            prod = yields["prod"][r, q]
            self._draw_text(surface, f"Food: {food:.2f}", panel_x + 15, y_offset)
            y_offset += 20
            self._draw_text(surface, f"Production: {prod:.2f}", panel_x + 15, y_offset)
    
    def _draw_section_header(self, surface: pygame.Surface, text: str, x: int, y: int):
        """Draw a section header."""
        header = self.font_normal.render(text, True, (200, 200, 100))
        surface.blit(header, (x, y))
        # Draw underline
        pygame.draw.line(surface, (100, 100, 50), (x, y + 20), (x + self.width - 30, y + 20), 1)
    
    def _draw_text(self, surface: pygame.Surface, text: str, x: int, y: int, 
                   color: Tuple[int, int, int] = (180, 180, 180), size: str = 'normal'):
        """Draw text at position."""
        font = self.font_small if size == 'small' else self.font_normal
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, (x, y))
    
    def handle_click(self, mouse_x: int, screen_width: int) -> bool:
        """Handle click on panel. Returns True if panel was toggled."""
        if mouse_x > screen_width - self.width and mouse_x < screen_width - self.width + 40:
            self.collapsed = not self.collapsed
            return True
        return False


class ControlPanel:
    """Bottom control panel with game controls."""
    
    def __init__(self, height: int = 60):
        self.height = height
        self.font = pygame.font.Font(None, 18)
        self.paused = False
        self.game_speed = 1  # 1, 2, 3 for normal, fast, very fast
        self.view_mode = ViewMode.POLITICAL
        
    def draw(self, surface: pygame.Surface):
        """Draw the control panel."""
        panel_y = surface.get_height() - self.height
        panel_rect = pygame.Rect(0, panel_y, surface.get_width(), self.height)
        
        # Background
        pygame.draw.rect(surface, (30, 30, 40), panel_rect)
        pygame.draw.rect(surface, (60, 60, 80), panel_rect, 2)
        
        x_offset = 10
        y_center = panel_y + self.height // 2
        
        # Pause/Play button
        pause_rect = pygame.Rect(x_offset, y_center - 15, 60, 30)
        color = (150, 50, 50) if self.paused else (50, 150, 50)
        pygame.draw.rect(surface, color, pause_rect)
        pause_text = "PLAY" if self.paused else "PAUSE"
        text = self.font.render(pause_text, True, (255, 255, 255))
        text_rect = text.get_rect(center=pause_rect.center)
        surface.blit(text, text_rect)
        x_offset += 70
        
        # Speed controls
        speed_text = self.font.render(f"Speed: {self.game_speed}x", True, (200, 200, 200))
        surface.blit(speed_text, (x_offset, y_center - 8))
        x_offset += 80
        
        # Speed buttons
        for i, speed in enumerate([1, 2, 3]):
            speed_rect = pygame.Rect(x_offset + i * 35, y_center - 15, 30, 30)
            color = (100, 100, 150) if self.game_speed == speed else (50, 50, 70)
            pygame.draw.rect(surface, color, speed_rect)
            text = self.font.render(str(speed), True, (255, 255, 255))
            text_rect = text.get_rect(center=speed_rect.center)
            surface.blit(text, text_rect)
        x_offset += 120
        
        # View mode buttons
        mode_text = self.font.render("View:", True, (200, 200, 200))
        surface.blit(mode_text, (x_offset, y_center - 8))
        x_offset += 50
        
        for i, (mode, label) in enumerate([
            (ViewMode.POLITICAL, "Political"),
            (ViewMode.TERRAIN, "Terrain"),
            (ViewMode.POPULATION, "Population"),
            (ViewMode.RESOURCES, "Resources")
        ]):
            mode_rect = pygame.Rect(x_offset + i * 75, y_center - 15, 70, 30)
            color = (100, 100, 150) if self.view_mode == mode else (50, 50, 70)
            pygame.draw.rect(surface, color, mode_rect)
            text = self.font.render(label, True, (255, 255, 255))
            text_rect = text.get_rect(center=mode_rect.center)
            surface.blit(text, text_rect)
        
        # Controls help text (right side)
        help_texts = [
            "Mouse: Drag to pan, Wheel to zoom, Click to select",
            "Space: Pause/Play | 1-3: Speed | Q/W/E/R: View modes"
        ]
        for i, help_text in enumerate(help_texts):
            text = self.font.render(help_text, True, (150, 150, 150))
            surface.blit(text, (surface.get_width() - 400, panel_y + 10 + i * 20))
    
    def handle_click(self, mouse_x: int, mouse_y: int, screen_height: int) -> str:
        """Handle click on control panel. Returns action name or empty string."""
        if mouse_y < screen_height - self.height:
            return ""
        
        y_center = screen_height - self.height // 2
        
        # Check pause button
        if 10 <= mouse_x <= 70 and y_center - 15 <= mouse_y <= y_center + 15:
            self.paused = not self.paused
            return "pause_toggle"
        
        # Check speed buttons
        for i, speed in enumerate([1, 2, 3]):
            x = 160 + i * 35
            if x <= mouse_x <= x + 30 and y_center - 15 <= mouse_y <= y_center + 15:
                self.game_speed = speed
                return f"speed_{speed}"
        
        # Check view mode buttons
        for i, mode in enumerate([ViewMode.POLITICAL, ViewMode.TERRAIN, 
                                 ViewMode.POPULATION, ViewMode.RESOURCES]):
            x = 330 + i * 75
            if x <= mouse_x <= x + 70 and y_center - 15 <= mouse_y <= y_center + 15:
                self.view_mode = mode
                return f"view_{mode.value}"
        
        return ""


class GodsimGUI:
    """Main GUI application for GodsimPy."""
    
    def __init__(self, world_state: WorldState = None, world_path: str = None):
        pygame.init()
        
        # Setup display
        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption("GodsimPy - Civilization Simulation")
        
        # Load or create world
        if world_state:
            self.world_state = world_state
        elif world_path and os.path.exists(world_path):
            self.world_state = load_npz(world_path)
        else:
            # Create a new world
            self.world_state = self._create_new_world()
        
        # Generate terrain features
        self.feature_map = generate_features(
            self.world_state.biome_map,
            np.random.default_rng(self.world_state.seed + 1000)
        )
        
        # Initialize civilizations if needed
        self.civs = []
        if (self.world_state.owner_map >= 0).sum() == 0:
            self.world_state, self.civs = initialize_civs(
                self.world_state, 
                n_civs=5,
                base_pop=50.0,
                seed=self.world_state.seed + 2000
            )
        else:
            # Reconstruct civ list from existing data
            num_civs = self.world_state.owner_map.max() + 1
            if num_civs > 0:
                colors = make_palette(num_civs)
                for i in range(num_civs):
                    from sim.civilization import Civilization
                    self.civs.append(Civilization(
                        id=i,
                        name=f"Civ {chr(65 + i)}" if i < 26 else f"Civ {i}",
                        color=colors[i],
                        rng_seed=self.world_state.seed ^ (i * 9973 + 12345)
                    ))
        
        # Initialize components
        self.camera = Camera()
        self.hex_renderer = HexRenderer(self.world_state)
        self.info_panel = InfoPanel()
        self.info_panel.feature_map = self.feature_map
        self.control_panel = ControlPanel()
        # View state: start with top-down and allow toggling isometric view
        self.isometric_mode = False
        
        # Initialize hex popup if available
        self.hex_popup = HexPopup() if HexPopup else None
        
        # State
        self.running = True
        self.clock = pygame.time.Clock()
        self.mouse_dragging = False
        self.drag_start = (0, 0)
        self.last_update = 0
        self.update_interval = 1000  # ms between simulation updates
        
    def _create_new_world(self) -> WorldState:
        """Create a new world with default parameters."""
        w, h = 64, 48
        seed = np.random.randint(0, 100000)
        
        height, _, sea, _ = build_world(
            w, h, seed, 
            plate_count=12,
            hex_radius=12.0,
            sea_level_percentile=0.5,
            mountain_h=0.8
        )
        biomes = build_biomes(height, sea, 0.8)
        
        return from_worldgen(height, biomes, sea, w, h, 12.0, seed)
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.control_panel.paused = not self.control_panel.paused
                elif event.key == pygame.K_1:
                    self.control_panel.game_speed = 1
                elif event.key == pygame.K_2:
                    self.control_panel.game_speed = 2
                elif event.key == pygame.K_3:
                    self.control_panel.game_speed = 3
                elif event.key == pygame.K_q:
                    self.control_panel.view_mode = ViewMode.POLITICAL
                elif event.key == pygame.K_w:
                    self.control_panel.view_mode = ViewMode.TERRAIN
                elif event.key == pygame.K_e:
                    self.control_panel.view_mode = ViewMode.POPULATION
                elif event.key == pygame.K_r:
                    self.control_panel.view_mode = ViewMode.RESOURCES
                elif event.key == pygame.K_TAB:
                    # Toggle between top-down and isometric views
                    self.isometric_mode = not self.isometric_mode
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # Save world
                    save_npz(self.world_state, "quicksave.npz")
                    print("World saved to quicksave.npz")
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check if clicking on hex popup to close it
                    if self.hex_popup and self.hex_popup.visible:
                        if self.hex_popup.handle_click(event.pos[0], event.pos[1]):
                            continue
                    
                    # Check if clicking on panels
                    if self.info_panel.handle_click(event.pos[0], self.screen.get_width()):
                        continue
                    
                    action = self.control_panel.handle_click(
                        event.pos[0], event.pos[1], self.screen.get_height()
                    )
                    if action:
                        continue
                    
                    # Otherwise, start dragging or select hex
                    if event.pos[1] < self.screen.get_height() - self.control_panel.height:
                        if event.pos[0] < self.screen.get_width() - (0 if self.info_panel.collapsed else self.info_panel.width):
                            # Check for double-click to show hex popup
                            wx, wy = self.camera.screen_to_world(
                                event.pos[0], event.pos[1],
                                self.screen.get_width(), self.screen.get_height()
                            )
                            hex_pos = self.hex_renderer.get_hex_at_point(wx, wy)
                            
                            if hex_pos:
                                # Single click selects hex
                                self.hex_renderer.selected_hex = hex_pos
                                self.info_panel.selected_tile = hex_pos
                                
                                # Show hex popup
                                if self.hex_popup:
                                    screen_x, screen_y = self.camera.world_to_screen(
                                        wx, wy, self.screen.get_width(), self.screen.get_height()
                                    )
                                    self.hex_popup.show(hex_pos[0], hex_pos[1], screen_x, screen_y)
                            else:
                                # Close popup if clicking on empty space
                                if self.hex_popup:
                                    self.hex_popup.hide()
                            
                            self.mouse_dragging = True
                            self.drag_start = event.pos
                
                elif event.button == 4:  # Mouse wheel up
                    self.camera.zoom_at(0.1, event.pos[0], event.pos[1])
                elif event.button == 5:  # Mouse wheel down
                    self.camera.zoom_at(-0.1, event.pos[0], event.pos[1])
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.mouse_dragging = False
            
            elif event.type == pygame.MOUSEMOTION:
                if self.mouse_dragging:
                    dx = event.pos[0] - self.drag_start[0]
                    dy = event.pos[1] - self.drag_start[1]
                    self.camera.pan(-dx, -dy)
                    self.drag_start = event.pos
                else:
                    # Update hover hex
                    if (event.pos[1] < self.screen.get_height() - self.control_panel.height and
                        event.pos[0] < self.screen.get_width() - (0 if self.info_panel.collapsed else self.info_panel.width)):
                        wx, wy = self.camera.screen_to_world(
                            event.pos[0], event.pos[1],
                            self.screen.get_width(), self.screen.get_height()
                        )
                        self.hex_renderer.hovered_hex = self.hex_renderer.get_hex_at_point(wx, wy)
    
    def update(self):
        """Update simulation state."""
        # Sync pause state between control panel and world state
        self.world_state.paused = self.control_panel.paused
        
        if not self.control_panel.paused:
            current_time = pygame.time.get_ticks()
            
            # Adjust update interval based on game speed
            adjusted_interval = self.update_interval // self.control_panel.game_speed
            
            if current_time - self.last_update > adjusted_interval:
                # Advance simulation
                advance_turn(
                    self.world_state,
                    feature_map=self.feature_map,
                    steps=1
                )
                self.last_update = current_time
        
        # Update hex popup animation
        if self.hex_popup:
            self.hex_popup.update()
    
    def render(self):
        """Render the game."""
        # Clear screen
        self.screen.fill((10, 10, 30))
        
        # Calculate render area (accounting for panels)
        render_width = self.screen.get_width()
        if not self.info_panel.collapsed:
            render_width -= self.info_panel.width
        render_height = self.screen.get_height() - self.control_panel.height
        
        # Create subsurface for map drawing
        map_surface = pygame.Surface((render_width, render_height))

        if self.isometric_mode:
            # Render isometric view using array-based renderer
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
            # Default top-down view using fixed HexRenderer
            self.hex_renderer.render(map_surface, self.camera, self.control_panel.view_mode)

        # Blit map surface to screen
        self.screen.blit(map_surface, (0, 0))
        
        # Draw panels
        self.info_panel.draw(self.screen, self.world_state, self.civs)
        self.control_panel.draw(self.screen)
        
        # Draw hex popup if visible
        if self.hex_popup:
            self.hex_popup.draw(self.screen, self.world_state, self.civs, self.feature_map)
        
        # Draw FPS counter
        fps = int(self.clock.get_fps())
        fps_text = pygame.font.Font(None, 20).render(f"FPS: {fps}", True, (200, 200, 200))
        self.screen.blit(fps_text, (10, 10))
        
        # Update display
        pygame.display.flip()
    
    def render_topdown_view(self, surface: pygame.Surface, view_mode: ViewMode):
        """Render top-down view using render_topdown functions."""
        # Create appropriate color/biome array based on view mode
        H, W = self.world_state.height, self.world_state.width
        color_array = np.zeros((H, W), dtype=np.int32)
        
        if view_mode == ViewMode.TERRAIN:
            # Use biome data directly
            color_array = self.world_state.biome_map.copy()
            img = render_topdown(color_array, self.world_state.hex_radius, scale=1)
            
        elif view_mode == ViewMode.POLITICAL:
            # For political mode, we need to create a custom image with proper colors
            # Create a PIL image directly with political colors
            from PIL import Image, ImageDraw
            import math
            from worldgen.hexgrid import axial_to_world_flat, SQRT3
            
            # Calculate canvas bounds
            xs, ys = [], []
            for r in range(H):
                for q in range(W):
                    x, z = axial_to_world_flat(q, r, self.world_state.hex_radius)
                    xs.append(x)
                    ys.append(z)
            
            padding = self.world_state.hex_radius * 2
            min_x, max_x = min(xs) - padding, max(xs) + padding
            min_y, max_y = min(ys) - padding, max(ys) + padding
            total_width = max_x - min_x
            total_height = max_y - min_y
            
            img_w = int(total_width)
            img_h = int(total_height)
            
            img = Image.new("RGBA", (img_w, img_h), (16, 18, 24, 255))
            draw = ImageDraw.Draw(img)
            
            # Get civ colors from HexRenderer
            civ_colors = self.hex_renderer.civ_colors
            biome_colors = self.hex_renderer.BIOME_COLORS
            
            def hex_points_flat(cx, cy, radius):
                pts = []
                for i in range(6):
                    ang = math.radians(60*i)
                    x = cx + math.cos(ang) * radius
                    y = cy + math.sin(ang) * radius
                    pts.append((x, y))
                return pts
            
            # Draw each hex
            for r in range(H):
                for q in range(W):
                    x, z = axial_to_world_flat(q, r, self.world_state.hex_radius)
                    x -= min_x
                    y = z - min_y
                    
                    pts = hex_points_flat(x, y, self.world_state.hex_radius)
                    
                    # Get political color
                    owner = self.world_state.owner_map[r, q]
                    if owner >= 0:
                        color = civ_colors[owner % len(civ_colors)]
                    else:
                        # Darken terrain color for unowned tiles
                        biome = self.world_state.biome_map[r, q]
                        base_color = biome_colors.get(biome, (100, 100, 100))
                        color = tuple(int(c * 0.6) for c in base_color)
                    
                    draw.polygon(pts, fill=color)
            
        elif view_mode == ViewMode.POPULATION:
            # Create population-based array
            for r in range(H):
                for q in range(W):
                    pop = self.world_state.pop_map[r, q]
                    if pop > 0:
                        color_array[r, q] = min(3, int(pop / 5))  # Scale population to 0-3
                    else:
                        color_array[r, q] = 0
            img = render_topdown(color_array, self.world_state.hex_radius, scale=1)
            
        else:  # RESOURCES or fallback
            # Use height data for resources view
            img = render_topdown_height(self.world_state.height_map, self.world_state.hex_radius, scale=1)
        
        # Convert PIL image to pygame surface
        topdown_surf = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
        
        # Scale to fit the surface while maintaining aspect ratio
        surf_w, surf_h = surface.get_size()
        img_w, img_h = img.size
        
        # Calculate scale to fit while preserving aspect ratio
        scale_x = surf_w / img_w
        scale_y = surf_h / img_h
        scale = min(scale_x, scale_y)
        
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        topdown_surf = pygame.transform.smoothscale(topdown_surf, (new_w, new_h))
        
        # Center the image on the surface
        x_offset = (surf_w - new_w) // 2
        y_offset = (surf_h - new_h) // 2
        
        # Clear background
        surface.fill((16, 18, 24))  # Match render background color
        surface.blit(topdown_surf, (x_offset, y_offset))
    
    def run(self):
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)  # Cap at 60 FPS
        
        pygame.quit()


def main():
    """Entry point for the GUI application."""
    import argparse
    
    parser = argparse.ArgumentParser(description="GodsimPy GUI")
    parser.add_argument("--load", type=str, help="Path to world NPZ file to load")
    parser.add_argument("--width", type=int, default=200, help="World width in hexes")
    parser.add_argument("--height", type=int, default=120, help="World height in hexes")
    parser.add_argument("--seed", type=int, help="Random seed for world generation")
    parser.add_argument("--civs", type=int, default=5, help="Number of civilizations")
    
    args = parser.parse_args()
    
    world_state = None
    
    if args.load and os.path.exists(args.load):
        print(f"Loading world from {args.load}")
        world_state = load_npz(args.load)
    else:
        # Generate new world
        print(f"Generating new world ({args.width}x{args.height})")
        seed = args.seed if args.seed else np.random.randint(0, 100000)
        
        height, _, sea, _ = build_world(
            args.width, args.height, seed,
            plate_count=12,
            hex_radius=12.0,
            sea_level_percentile=0.5,
            mountain_h=0.8
        )
        biomes = build_biomes(height, sea, 0.8)
        world_state = from_worldgen(height, biomes, sea, args.width, args.height, 12.0, seed)
        
        # Initialize civilizations
        world_state, _ = initialize_civs(world_state, n_civs=args.civs, base_pop=50.0, seed=seed + 1000)
    
    # Create and run GUI
    gui = GodsimGUI(world_state=world_state)
    gui.run()


if __name__ == "__main__":
    main()
