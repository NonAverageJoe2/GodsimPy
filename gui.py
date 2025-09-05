"""Simple Pygame GUI for interacting with the simulation world, with
toggleable Top-Down and Isometric projections.
"""

from __future__ import annotations

import sys
from typing import Optional, Tuple

import pygame

from engine import SimulationEngine, Army
from worldgen.hexgrid import axial_to_pixel, hex_polygon, pixel_to_axial

# Biome colors roughly matching ``render.py``
BIOME_COLORS = [
    (int(0.20 * 255), int(0.70 * 255), int(0.20 * 255)),  # grass/land
    (int(0.95 * 255), int(0.85 * 255), int(0.25 * 255)),  # sand/coast
    (int(0.60 * 255), int(0.60 * 255), int(0.60 * 255)),  # mountain
    (int(0.05 * 255), int(0.15 * 255), int(0.45 * 255)),  # ocean
]

# Ownership tint colors
OWNER_TINTS = [
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 165, 0),
]


class GameGUI:
    """Interactive hex-map GUI with basic controls."""

    def __init__(self, world_path: str) -> None:
        pygame.init()
        self.clock = pygame.time.Clock()

        self.eng = SimulationEngine()
        self.eng.load_json(world_path)

        self.hex_px = 24  # base hex radius in pixels
        self.zoom = 1.0
        self.camera_x = 0.0
        self.camera_y = 0.0

        # View mode: "topdown" (orthographic) or "isometric"
        self.view_mode = "topdown"
        # Isometric scale lets you widen/narrow the diamond shape
        self.iso_scale = 1.0

        self.screen = pygame.display.set_mode((1280, 800))
        pygame.display.set_caption("Sim GUI")
        self.font = pygame.font.SysFont("consolas", 16)

        self.selected_hex: Optional[Tuple[int, int]] = None
        self.selected_army: Optional[Army] = None

        # Pre-compute world bounds in pixel space for camera clamping
        w = self.eng.world
        xs, ys = [], []
        for (q, r) in (
            (0, 0),
            (w.width_hex - 1, 0),
            (0, w.height_hex - 1),
            (w.width_hex - 1, w.height_hex - 1),
        ):
            x, y = axial_to_pixel(q, r, self.hex_px)
            xs.extend([x - self.hex_px, x + self.hex_px])
            ys.extend([y - self.hex_px, y + self.hex_px])
        self.world_w = max(xs) if xs else 0.0
        self.world_h = max(ys) if ys else 0.0

    # ------------------------------------------------------------------ utils --
    def clamp_camera(self) -> None:
        # Clamps in topdown world space; OK for both modes since we un/project
        sw, sh = self.screen.get_size()
        max_x = max(0.0, self.world_w - sw / self.zoom)
        max_y = max(0.0, self.world_h - sh / self.zoom)
        if self.camera_x < 0.0:
            self.camera_x = 0.0
        elif self.camera_x > max_x:
            self.camera_x = max_x
        if self.camera_y < 0.0:
            self.camera_y = 0.0
        elif self.camera_y > max_y:
            self.camera_y = max_y

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        sx = (x - self.camera_x) * self.zoom
        sy = (y - self.camera_y) * self.zoom
        return int(sx), int(sy)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        wx = sx / self.zoom + self.camera_x
        wy = sy / self.zoom + self.camera_y
        return wx, wy

    # --- Projection helpers ---------------------------------------------------
    # We project AFTER the camera transform so panning & zooming behave uniformly.

    def project_point(self, sx: int, sy: int) -> Tuple[int, int]:
        """Project a screen-space point (topdown) into the current view."""
        if self.view_mode == "topdown":
            return sx, sy

        # Isometric: apply matrix [[1,-1],[0.5,0.5]] with an overall scale.
        sw, sh = self.screen.get_size()
        cx, cy = sw * 0.5, sh * 0.5

        dx = (sx - cx) * self.iso_scale
        dy = (sy - cy) * self.iso_scale

        ix = dx - dy
        iy = 0.5 * (dx + dy)

        return int(cx + ix), int(cy + iy)

    def unproject_point(self, px: int, py: int) -> Tuple[int, int]:
        """Inverse of project_point (for mouse picking)."""
        if self.view_mode == "topdown":
            return px, py

        sw, sh = self.screen.get_size()
        cx, cy = sw * 0.5, sh * 0.5

        dx = px - cx
        dy = py - cy

        # Inverse of [[1,-1],[0.5,0.5]] is [[0.5,1],[-0.5,1]]; account for iso_scale.
        inv_scale = (1.0 / self.iso_scale) if self.iso_scale != 0 else 1.0
        ux = (0.5 * dx + 1.0 * dy) * inv_scale
        uy = (-0.5 * dx + 1.0 * dy) * inv_scale

        return int(cx + ux), int(cy + uy)

    def screen_to_hex(self, sx: int, sy: int) -> Tuple[int, int]:
        # Convert from displayed pixel -> topdown pixel -> axial hex
        # so picking works in both view modes
        upx, upy = self.unproject_point(sx, sy)
        wx, wy = self.screen_to_world(upx, upy)
        return pixel_to_axial(wx, wy, self.hex_px)

    def tile_color(self, tile) -> Tuple[int, int, int]:
        try:
            b = int(tile.biome)
        except Exception:
            b = 0
        base = BIOME_COLORS[b % len(BIOME_COLORS)]
        # Brightness from population (0 -> 0.3, high pop -> 1.0)
        k = min(1.0, 0.3 + tile.pop / 200.0)
        col = tuple(min(255, int(c * k)) for c in base)
        if tile.owner is not None:
            tint = OWNER_TINTS[tile.owner % len(OWNER_TINTS)]
            col = tuple(min(255, (c + t) // 2) for c, t in zip(col, tint))
        return col

    # ----------------------------------------------------------------- events --
    def handle_mouse(self, ev: pygame.event.Event) -> None:
        if ev.button == 1:  # left click select
            q, r = self.screen_to_hex(*ev.pos)
            if self.eng.world.in_bounds(q, r):
                self.selected_hex = (q, r)
                self.selected_army = None
                for a in self.eng.world.armies:
                    if a.q == q and a.r == r:
                        self.selected_army = a
                        break
        elif ev.button == 3:  # right click set army target
            if self.selected_army is None:
                return
            q, r = self.screen_to_hex(*ev.pos)
            if self.eng.world.in_bounds(q, r):
                self.eng.set_army_target(self.selected_army, (q, r))

    def handle_key(self, ev: pygame.event.Event) -> None:
        if ev.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit(0)
        elif ev.key == pygame.K_SPACE:
            self.eng.advance_turn()
        elif ev.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.eng.save_json("autosave.json")
        elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.zoom = min(4.0, self.zoom * 1.2)
            self.clamp_camera()
        elif ev.key == pygame.K_MINUS:
            self.zoom = max(0.25, self.zoom / 1.2)
            self.clamp_camera()
        elif ev.key == pygame.K_a and self.selected_hex is not None:
            q, r = self.selected_hex
            t = self.eng.world.get_tile(q, r)
            if t.owner is not None:
                self.selected_army = self.eng.add_army(t.owner, (q, r))
        elif ev.key == pygame.K_v:
            # Toggle view mode
            self.view_mode = "isometric" if self.view_mode == "topdown" else "topdown"
        elif ev.key == pygame.K_LEFTBRACKET:
            # Narrow iso diamond
            self.iso_scale = max(0.5, self.iso_scale * 0.9)
        elif ev.key == pygame.K_RIGHTBRACKET:
            # Widen iso diamond
            self.iso_scale = min(2.0, self.iso_scale * 1.1)

    # ------------------------------------------------------------------- main --
    def run(self) -> None:
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    self.handle_key(ev)
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse(ev)

            keys = pygame.key.get_pressed()
            pan = 10.0 / self.zoom
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.camera_x -= pan
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.camera_x += pan
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.camera_y -= pan
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.camera_y += pan
            self.clamp_camera()

            self.draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------------- draw --
    def draw(self) -> None:
        scr = self.screen
        scr.fill((8, 8, 12))
        w = self.eng.world
        zoom = self.zoom
        sw, sh = scr.get_size()

        # NOTE: Culling is conservative in isometric mode; we keep it simple.

        for t in w.tiles:
            cx, cy = axial_to_pixel(t.q, t.r, self.hex_px)
            sx, sy = self.world_to_screen(cx, cy)
            # Project after camera & zoom
            psx, psy = self.project_point(sx, sy)

            size = self.hex_px * zoom
            if (
                psx + size < 0
                or psy + size < 0
                or psx - size > sw
                or psy - size > sh
            ):
                continue

            pts = hex_polygon(t.q, t.r, self.hex_px)
            pts = [self.world_to_screen(px, py) for px, py in pts]
            pts = [self.project_point(px, py) for px, py in pts]

            pygame.draw.polygon(scr, self.tile_color(t), pts)
            if self.selected_hex == (t.q, t.r):
                pygame.draw.polygon(scr, (255, 255, 255), pts, 2)

        for a in w.armies:
            cx, cy = axial_to_pixel(a.q, a.r, self.hex_px)
            sx, sy = self.world_to_screen(cx, cy)
            psx, psy = self.project_point(sx, sy)
            if psx < -10 or psy < -10 or psx > sw + 10 or psy > sh + 10:
                continue
            col = OWNER_TINTS[a.civ_id % len(OWNER_TINTS)]
            rad = int(self.hex_px * 0.3 * zoom)
            pygame.draw.circle(scr, (0, 0, 0), (psx, psy), rad + 2)
            pygame.draw.circle(scr, col, (psx, psy), rad)
            if a is self.selected_army:
                pygame.draw.circle(scr, (255, 255, 255), (psx, psy), rad + 3, 2)

        # HUD -----------------------------------------------------------------
        date = self.eng.world.calendar
        dstr = f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
        hud_parts = [
            f"{dstr}",
            f"scale:{self.eng.world.time_scale}",
            f"view:{self.view_mode}",
        ]
        if self.view_mode == "isometric":
            hud_parts.append(f"iso_scale:{self.iso_scale:.2f}")
        if self.selected_hex is not None:
            q, r = self.selected_hex
            t = self.eng.world.get_tile(q, r)
            hud_parts.append(
                f"hex({q},{r}) biome:{t.biome} pop:{t.pop} owner:{t.owner}"
            )
        if self.selected_army is not None and self.selected_army in w.armies:
            aid = w.armies.index(self.selected_army)
            hud_parts.append(
                f"army{aid} str:{self.selected_army.strength} tgt:{self.selected_army.target}"
            )
        hud = self.font.render(" | ".join(hud_parts), True, (240, 240, 240))
        scr.blit(hud, (8, 8))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gui.py path/to/world.json")
        sys.exit(1)
    GameGUI(sys.argv[1]).run()
