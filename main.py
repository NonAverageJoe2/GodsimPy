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

    def draw(self, surface: pygame.Surface, tech_system: Optional[TechnologySystem], civs_name_map: Dict[int, str]):
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
            surface.blit(window, (x, y))
            return

        civ_name = civs_name_map.get(civ_id, f"Civ {civ_id}")
        civ_state = tech_system.civ_states.get(civ_id)

        # Title
        title = f"{civ_name} - Technology Tree"
        title_text = self.font_title.render(title, True, (255, 255, 255))
        title_text_rect = title_text.get_rect(center=(self.width // 2, 17))
        window.blit(title_text, title_text_rect)

        # Age / progress
        y_offset = 45
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

    def handle_click(self, mouse_x: int, mouse_y: int, screen_size: Tuple[int, int]) -> bool:
        """Returns True if window was closed."""
        if not self.visible:
            return False
        screen_w, screen_h = screen_size
        window_x = (screen_w - self.width) // 2
        window_y = (screen_h - self.height) // 2
        close_x = window_x + self.width - 30
        close_y = window_y + 5
        if close_x <= mouse_x <= close_x + 25 and close_y <= mouse_y <= close_y + 25:
            self.hide()
            return True
        return False

    def handle_scroll(self, delta: int):
        if self.visible:
            self.scroll_y = max(0, self.scroll_y - delta * 20)


class TechInfoPanel:
    """Panel extension to show technology info in the main info panel."""
    @staticmethod
    def draw_tech_info(surface: pygame.Surface, x: int, y: int, width: int,
                       civ_id: int, tech_system: Optional[TechnologySystem],
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
                         tech_system: Optional[TechnologySystem]) -> None:
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
        # zoom around focus
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

    BIOME_COLORS = {
        0: (34, 139, 34),    # Grass
        1: (238, 203, 173),  # Coast
        2: (139, 137, 137),  # Mountain
        3: (0, 119, 190),    # Ocean
        4: (238, 203, 173),  # Desert
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

        H, W = self.world_state.height, self.world_state.width
        for r in range(H):
            for q in range(W):
                cx, cy = _evenq_center(q, r, r_hex)
                d2 = (wx - cx) ** 2 + (wy - cy) ** 2
                if d2 < best_d2 and d2 <= pick_r2:
                    best_d2, best_q, best_r = d2, q, r

        return (best_q, best_r) if best_q is not None else None

    def draw_hex(self, surface: pygame.Surface, q: int, r: int,
                 color: Tuple[int, int, int], camera: Camera,
                 outline_color: Optional[Tuple[int, int, int]] = None,
                 tech_overlay: Optional[TechMapOverlay] = None,
                 tech_system: Optional[TechnologySystem] = None):
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
        if outline_color:
            pygame.draw.polygon(surface, outline_color, verts, 2)
        elif self.selected_hex == (q, r):
            pygame.draw.polygon(surface, (255, 255, 0), verts, 3)
        elif self.hovered_hex == (q, r):
            pygame.draw.polygon(surface, (255, 255, 255), verts, 2)

        # Optional tech overlay dot
        if tech_overlay is not None:
            cx_s, cy_s = camera.world_to_screen(cx, cy, surface.get_width(), surface.get_height())
            owner = self.world_state.owner_map[r, q]
            if owner >= 0:
                tech_overlay.draw_hex_overlay(surface, (cx_s, cy_s), self.hex_radius * camera.zoom, owner, tech_system)

    def get_hex_color(self, q: int, r: int, view_mode: ViewMode) -> Tuple[int, int, int]:
        if view_mode == ViewMode.TERRAIN:
            biome = self.world_state.biome_map[r, q]
            return self.BIOME_COLORS.get(biome, (100, 100, 100))

        elif view_mode == ViewMode.POLITICAL:
            owner = self.world_state.owner_map[r, q]
            if owner >= 0:
                return self.civ_colors[owner % len(self.civ_colors)]
            else:
                biome = self.world_state.biome_map[r, q]
                base = self.BIOME_COLORS.get(biome, (100, 100, 100))
                return tuple(int(c * 0.6) for c in base)

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

        return (100, 100, 100)

    def render(self, surface: pygame.Surface, camera: Camera, view_mode: ViewMode,
               tech_overlay: Optional[TechMapOverlay] = None,
               tech_system: Optional[TechnologySystem] = None):
        surface.fill((10, 10, 30))
        H, W = self.world_state.height, self.world_state.width
        for r in range(H):
            for q in range(W):
                color = self.get_hex_color(q, r, view_mode)
                outline = None
                if view_mode == ViewMode.TERRAIN and self.world_state.owner_map[r, q] >= 0:
                    owner = self.world_state.owner_map[r, q]
                    outline = self.civ_colors[owner % len(self.civ_colors)]
                self.draw_hex(surface, q, r, color, camera, outline, tech_overlay, tech_system)


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

    def draw(self, surface: pygame.Surface, world_state: WorldState, civs: List,
             tech_system: Optional[TechnologySystem] = None):
        panel_height = surface.get_height()
        panel_x = surface.get_width() - self.width

        # Background
        panel_rect = pygame.Rect(panel_x, 0, self.width, panel_height)
        pygame.draw.rect(surface, (30, 30, 40), panel_rect)
        pygame.draw.rect(surface, (60, 60, 80), panel_rect, 2)

        # Collapse toggle
        button_rect = pygame.Rect(panel_x + 5, 5, 30, 20)
        pygame.draw.rect(surface, (50, 50, 70), button_rect)
        arrow = "<" if not self.collapsed else ">"
        arrow_text = self.font_small.render(arrow, True, (200, 200, 200))
        surface.blit(arrow_text, (panel_x + 15, 7))

        if self.collapsed:
            return

        title = self.font_title.render("INFO", True, (255, 255, 255))
        surface.blit(title, (panel_x + 45, 5))

        y_offset = 35

        # WORLD
        self._draw_section_header(surface, "WORLD", panel_x + 10, y_offset)
        y_offset += 25

        m, d, y = world_state.get_date_tuple()
        self._draw_text(surface, f"Date: {m}/{d}/{y}", panel_x + 15, y_offset); y_offset += 20
        self._draw_text(surface, f"Turn: {world_state.turn}", panel_x + 15, y_offset); y_offset += 20
        self._draw_text(surface, f"Time Scale: {world_state.time_scale}", panel_x + 15, y_offset); y_offset += 30

        total_pop = world_state.pop_map.sum()
        owned_tiles = (world_state.owner_map >= 0).sum()
        self._draw_section_header(surface, "STATISTICS", panel_x + 10, y_offset); y_offset += 25
        self._draw_text(surface, f"Total Population: {int(total_pop)}", panel_x + 15, y_offset); y_offset += 20
        self._draw_text(surface, f"Owned Tiles: {owned_tiles}", panel_x + 15, y_offset); y_offset += 30

        # CIVS
        if civs:
            self._draw_section_header(surface, "CIVILIZATIONS", panel_x + 10, y_offset); y_offset += 25
            for civ in civs[:5]:
                civ_pop = world_state.pop_map[world_state.owner_map == civ.id].sum()
                civ_tiles = (world_state.owner_map == civ.id).sum()
                pygame.draw.rect(surface, civ.color, pygame.Rect(panel_x + 15, y_offset, 12, 12))
                self._draw_text(surface, f"{civ.name}: {int(civ_pop)} pop, {civ_tiles} tiles",
                                panel_x + 32, y_offset, size='small')
                y_offset += 18
            y_offset += 20

        # TILE
        if self.selected_tile:
            q, r = self.selected_tile
            self._draw_section_header(surface, f"TILE ({q}, {r})", panel_x + 10, y_offset); y_offset += 25
            biome_names = {0: "Grassland", 1: "Coast", 2: "Mountain", 3: "Ocean", 4: "Desert"}
            biome = world_state.biome_map[r, q]
            self._draw_text(surface, f"Biome: {biome_names.get(biome, 'Unknown')}", panel_x + 15, y_offset); y_offset += 20

            if self.feature_map is not None:
                feature = self.feature_map[r, q]
                feature_name = describe_feature(feature)
                if feature_name != "None":
                    self._draw_text(surface, f"Feature: {feature_name}", panel_x + 15, y_offset); y_offset += 20

            owner = world_state.owner_map[r, q]
            if 0 <= owner < len(civs):
                self._draw_text(surface, f"Owner: {civs[owner].name}", panel_x + 15, y_offset); y_offset += 20
            else:
                self._draw_text(surface, "Owner: None", panel_x + 15, y_offset); y_offset += 20

            pop = world_state.pop_map[r, q]
            self._draw_text(surface, f"Population: {int(pop)}", panel_x + 15, y_offset); y_offset += 20

            yields = biome_yields(world_state.biome_map)
            food = yields["food"][r, q]; prod = yields["prod"][r, q]
            self._draw_text(surface, f"Food: {food:.2f}", panel_x + 15, y_offset); y_offset += 20
            self._draw_text(surface, f"Production: {prod:.2f}", panel_x + 15, y_offset); y_offset += 10

            # --- TECH SECTION (only if tech_system present & tile owned) ---
            if owner >= 0 and tech_system is not None:
                y_offset = TechInfoPanel.draw_tech_info(
                    surface, panel_x + 10, y_offset + 10, self.width,
                    owner, tech_system,
                    self.font_normal, self.font_normal, self.font_small
                )

    def _draw_section_header(self, surface: pygame.Surface, text: str, x: int, y: int):
        header = self.font_normal.render(text, True, (200, 200, 100))
        surface.blit(header, (x, y))
        pygame.draw.line(surface, (100, 100, 50), (x, y + 20), (x + self.width - 30, y + 20), 1)

    def _draw_text(self, surface: pygame.Surface, text: str, x: int, y: int,
                   color: Tuple[int, int, int] = (180, 180, 180), size: str = 'normal'):
        font = self.font_small if size == 'small' else self.font_normal
        surface.blit(font.render(text, True, color), (x, y))

    def handle_click(self, mouse_x: int, screen_width: int) -> bool:
        if screen_width - self.width < mouse_x < screen_width - self.width + 40:
            self.collapsed = not self.collapsed
            return True
        return False


class ControlPanel:
    """Bottom control panel with game controls."""
    def __init__(self, height: int = 60):
        self.height = height
        self.font = pygame.font.Font(None, 18)
        self.paused = False
        self.game_speed = 1
        self.view_mode = ViewMode.POLITICAL

    def draw(self, surface: pygame.Surface):
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

        # Help
        help_texts = [
            "Mouse: Drag to pan, Wheel to zoom, Click to select",
            "Space: Pause/Play | 1-3: Speed | Q/W/E/R: View modes | T: Tech Tree"
        ]
        for i, msg in enumerate(help_texts):
            t = self.font.render(msg, True, (150, 150, 150))
            surface.blit(t, (surface.get_width() - 480, panel_y + 10 + i * 20))

    def handle_click(self, mouse_x: int, mouse_y: int, screen_height: int) -> str:
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

        # Civs
        self.civs = []
        if (self.world_state.owner_map >= 0).sum() == 0:
            self.world_state, self.civs = initialize_civs(
                self.world_state,
                n_civs=5,
                base_pop=50.0,
                seed=self.world_state.seed + 2000
            )
        else:
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

        # Components
        self.camera = Camera()
        self.hex_renderer = HexRenderer(self.world_state)
        self.info_panel = InfoPanel()
        self.info_panel.feature_map = self.feature_map
        self.control_panel = ControlPanel()
        self.isometric_mode = False

        # --- Tech GUI bits (safe if technology not available) ---
        self.tech_window = TechTreeWindow()
        self.tech_info = TechInfoPanel()
        self.age_indicator = AgeProgressIndicator()
        self.tech_overlay = TechMapOverlay()
        self.tech_notifications = TechNotification()
        # Attach a TechnologySystem if your sim exposes one:
        # Preferred: engine sets world_state.tech_system
        self.tech_system: Optional[TechnologySystem] = getattr(self.world_state, "tech_system", None) if _TECH_AVAILABLE else None

        # Popup (optional)
        try:
            from gui.hex_popup import HexPopup
        except ImportError:
            try:
                from hex_popup import HexPopup
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

    def _create_new_world(self) -> WorldState:
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

    def _selected_owner_id(self) -> Optional[int]:
        """Helper: civ id of currently selected tile owner."""
        if not self.hex_renderer.selected_hex:
            return None
        q, r = self.hex_renderer.selected_hex
        owner = self.world_state.owner_map[r, q]
        return int(owner) if owner >= 0 else None

    def handle_events(self):
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
                    self.isometric_mode = not self.isometric_mode
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    save_npz(self.world_state, "quicksave.npz")
                    print("World saved to quicksave.npz")
                # --- Tech hotkey: open/close tree for selected civ (if tech available) ---
                elif _TECH_AVAILABLE and TechHotkeys.handle_keypress(event, self.tech_window, self._selected_owner_id()):
                    pass
                # Toggle overlay with 'A' (optional UX)
                elif _TECH_AVAILABLE and event.key == pygame.K_a:
                    self.tech_overlay.toggle()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Tech window close click
                    if self.tech_window.handle_click(event.pos[0], event.pos[1], self.screen.get_size()):
                        continue
                    # Hex popup close
                    if self.hex_popup and self.hex_popup.visible:
                        if self.hex_popup.handle_click(event.pos[0], event.pos[1]):
                            continue
                    # Panels
                    if self.info_panel.handle_click(event.pos[0], self.screen.get_width()):
                        continue
                    action = self.control_panel.handle_click(event.pos[0], event.pos[1], self.screen.get_height())
                    if action:
                        continue
                    # Select hex / start drag
                    if event.pos[1] < self.screen.get_height() - self.control_panel.height:
                        if event.pos[0] < self.screen.get_width() - (0 if self.info_panel.collapsed else self.info_panel.width):
                            wx, wy = self.camera.screen_to_world(
                                event.pos[0], event.pos[1],
                                self.screen.get_width(), self.screen.get_height()
                            )
                            hex_pos = self.hex_renderer.get_hex_at_point(wx, wy)
                            if hex_pos:
                                self.hex_renderer.selected_hex = hex_pos
                                self.info_panel.selected_tile = hex_pos
                                if self.hex_popup:
                                    sx, sy = self.camera.world_to_screen(wx, wy, self.screen.get_width(), self.screen.get_height())
                                    self.hex_popup.show(hex_pos[0], hex_pos[1], sx, sy)
                            else:
                                if self.hex_popup:
                                    self.hex_popup.hide()
                            self.mouse_dragging = True
                            self.drag_start = event.pos

                elif event.button == 4:  # wheel up
                    self.camera.zoom_at(0.1, event.pos[0], event.pos[1])
                    self.tech_window.handle_scroll(1)
                elif event.button == 5:  # wheel down
                    self.camera.zoom_at(-0.1, event.pos[0], event.pos[1])
                    self.tech_window.handle_scroll(-1)

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
                    if (event.pos[1] < self.screen.get_height() - self.control_panel.height and
                        event.pos[0] < self.screen.get_width() - (0 if self.info_panel.collapsed else self.info_panel.width)):
                        wx, wy = self.camera.screen_to_world(
                            event.pos[0], event.pos[1],
                            self.screen.get_width(), self.screen.get_height()
                        )
                        self.hex_renderer.hovered_hex = self.hex_renderer.get_hex_at_point(wx, wy)

    def update(self):
        # Sync pause
        self.world_state.paused = self.control_panel.paused

        if not self.control_panel.paused:
            current_time = pygame.time.get_ticks()
            adjusted = max(1, self.update_interval // max(1, self.control_panel.game_speed))
            if current_time - self.last_update > adjusted:
                advance_turn(self.world_state, feature_map=self.feature_map, steps=1)
                self.last_update = current_time

        # Tech notifications (optional): if your engine emits events, push them here.
        self.tech_notifications.update(pygame.time.get_ticks())

        if self.hex_popup:
            self.hex_popup.update()

    def render(self):
        self.screen.fill((10, 10, 30))

        # Map area dims
        render_width = self.screen.get_width()
        if not self.info_panel.collapsed:
            render_width -= self.info_panel.width
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
                tech_system=self.tech_system
            )

        self.screen.blit(map_surface, (0, 0))

        # Panels
        self.info_panel.draw(self.screen, self.world_state, self.civs, tech_system=self.tech_system)
        self.control_panel.draw(self.screen)

        # Hex popup
        if self.hex_popup:
            self.hex_popup.draw(self.screen, self.world_state, self.civs, self.feature_map)

        # Age indicators (top-left column) if tech is available
        if _TECH_AVAILABLE and self.tech_system is not None and self.civs:
            y_off = 80
            for civ in self.civs[:5]:
                state = getattr(self.tech_system, "civ_states", {}).get(civ.id)
                if state:
                    self.age_indicator.draw(self.screen, 10, y_off,
                                            civ.name,
                                            getattr(state, "current_age", Age.DISSEMINATION),
                                            len(getattr(state, "researched_techs", [])))
                    y_off += 30

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
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
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
        print(f"Generating new world ({args.width}x{args.height})")
        seed = args.seed if args.seed else np.random.randint(0, 100000)
        height, _, sea, _ = build_world(
            args.width, args.height, seed,
            plate_count=12, hex_radius=12.0,
            sea_level_percentile=0.5, mountain_h=0.8
        )
        biomes = build_biomes(height, sea, 0.8)
        world_state = from_worldgen(height, biomes, sea, args.width, args.height, 12.0, seed)
        world_state, _ = initialize_civs(world_state, n_civs=args.civs, base_pop=50.0, seed=seed + 1000)

    gui = GodsimGUI(world_state=world_state)
    # OPTIONAL: if your simulation core already created a TechnologySystem, attach it:
    gui.tech_system = engine.tech_system
    gui.run()


if __name__ == "__main__":
    main()
