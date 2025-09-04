"""Pygame front-end with simple army controls and overlay."""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Tuple

import pygame

from engine import SimulationEngine, Army
from fixes.engine_integration_complete import apply_all_fixes
from worldgen.hexgrid import axial_to_pixel, hex_polygon, pixel_to_axial

BIOME_COLORS = [
    (int(0.20 * 255), int(0.70 * 255), int(0.20 * 255)),
    (int(0.95 * 255), int(0.85 * 255), int(0.25 * 255)),
    (int(0.60 * 255), int(0.60 * 255), int(0.60 * 255)),
    (int(0.05 * 255), int(0.15 * 255), int(0.45 * 255)),
]

OWNER_TINTS = [
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 165, 0),
]


class GameGUI:
    """Interactive hex-map GUI with a selection cursor and overlay."""

    def __init__(self, show_overlay: bool = True) -> None:
        pygame.init()
        self.clock = pygame.time.Clock()
        self.eng = SimulationEngine(width=48, height=32, seed=1)
        apply_all_fixes(engine)
        self.hex_px = 24
        self.zoom = 1.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.view_mode = "topdown"
        self.iso_scale = 1.0
        self.screen = pygame.display.set_mode((1280, 800))
        pygame.display.set_caption("Sim GUI")
        self.font = pygame.font.SysFont("consolas", 16)
        self.selected_hex: Tuple[int, int] = (0, 0)
        self.selected_army: Optional[Army] = None
        self.show_overlay = show_overlay
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
        self.center_on(*self.selected_hex)

    # utils
    def clamp_camera(self) -> None:
        sw, sh = self.screen.get_size()
        max_x = max(0.0, self.world_w - sw / self.zoom)
        max_y = max(0.0, self.world_h - sh / self.zoom)
        self.camera_x = min(max(self.camera_x, 0.0), max_x)
        self.camera_y = min(max(self.camera_y, 0.0), max_y)

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        sx = (x - self.camera_x) * self.zoom
        sy = (y - self.camera_y) * self.zoom
        return int(sx), int(sy)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        wx = sx / self.zoom + self.camera_x
        wy = sy / self.zoom + self.camera_y
        return wx, wy

    def project_point(self, sx: int, sy: int) -> Tuple[int, int]:
        if self.view_mode == "topdown":
            return sx, sy
        sw, sh = self.screen.get_size()
        cx, cy = sw * 0.5, sh * 0.5
        dx = (sx - cx) * self.iso_scale
        dy = (sy - cy) * self.iso_scale
        ix = dx - dy
        iy = 0.5 * (dx + dy)
        return int(cx + ix), int(cy + iy)

    def unproject_point(self, px: int, py: int) -> Tuple[int, int]:
        if self.view_mode == "topdown":
            return px, py
        sw, sh = self.screen.get_size()
        cx, cy = sw * 0.5, sh * 0.5
        dx = px - cx
        dy = py - cy
        inv_scale = (1.0 / self.iso_scale) if self.iso_scale != 0 else 1.0
        ux = (0.5 * dx + 1.0 * dy) * inv_scale
        uy = (-0.5 * dx + 1.0 * dy) * inv_scale
        return int(cx + ux), int(cy + uy)

    def screen_to_hex(self, sx: int, sy: int) -> Tuple[int, int]:
        upx, upy = self.unproject_point(sx, sy)
        wx, wy = self.screen_to_world(upx, upy)
        return pixel_to_axial(wx, wy, self.hex_px)

    def tile_color(self, tile) -> Tuple[int, int, int]:
        try:
            b = int(tile.biome)
        except Exception:
            b = 0
        base = BIOME_COLORS[b % len(BIOME_COLORS)]
        k = min(1.0, 0.3 + tile.pop / 200.0)
        col = tuple(min(255, int(c * k)) for c in base)
        if tile.owner is not None:
            tint = OWNER_TINTS[tile.owner % len(OWNER_TINTS)]
            col = tuple(min(255, (c + t) // 2) for c, t in zip(col, tint))
        return col

    def center_on(self, q: int, r: int) -> None:
        wx, wy = axial_to_pixel(q, r, self.hex_px)
        sw, sh = self.screen.get_size()
        self.camera_x = wx - (sw / self.zoom) / 2
        self.camera_y = wy - (sh / self.zoom) / 2
        self.clamp_camera()

    def move_selection(self, dq: int, dr: int) -> None:
        q, r = self.selected_hex
        nq, nr = q + dq, r + dr
        if self.eng.world.in_bounds(nq, nr):
            self.selected_hex = (nq, nr)
            self.center_on(nq, nr)
            self.selected_army = None
            for a in self.eng.world.armies:
                if a.q == nq and a.r == nr:
                    self.selected_army = a
                    break

    def order_step(self, dq: int, dr: int) -> None:
        if self.selected_army is None:
            return
        target = (self.selected_army.q + dq, self.selected_army.r + dr)
        if self.eng.world.in_bounds(*target):
            self.eng.set_army_target(self.selected_army, target)

    def handle_mouse(self, ev: pygame.event.Event) -> None:
        if ev.button == 1:
            q, r = self.screen_to_hex(*ev.pos)
            if self.eng.world.in_bounds(q, r):
                self.selected_hex = (q, r)
                self.center_on(q, r)
                self.selected_army = None
                for a in self.eng.world.armies:
                    if a.q == q and a.r == r:
                        self.selected_army = a
                        break
        elif ev.button == 3 and self.selected_army is not None:
            q, r = self.screen_to_hex(*ev.pos)
            if self.eng.world.in_bounds(q, r):
                self.eng.set_army_target(self.selected_army, (q, r))

    def handle_key(self, ev: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
        if ev.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit(0)
        elif ev.key == pygame.K_SPACE:
            self.eng.advance_turn()
        elif ev.key == pygame.K_s and mods & pygame.KMOD_CTRL:
            self.eng.save_json("autosave.json")
        elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.zoom = min(4.0, self.zoom * 1.2)
            self.clamp_camera()
        elif ev.key == pygame.K_MINUS:
            self.zoom = max(0.25, self.zoom / 1.2)
            self.clamp_camera()
        elif ev.key == pygame.K_a:
            q, r = self.selected_hex
            t = self.eng.world.get_tile(q, r)
            if t.owner is not None:
                self.selected_army = self.eng.add_army(t.owner, (q, r))
        elif ev.key == pygame.K_v:
            self.show_overlay = not self.show_overlay
        elif ev.key == pygame.K_i:
            self.view_mode = "isometric" if self.view_mode == "topdown" else "topdown"
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            q, r = self.selected_hex
            self.selected_army = None
            for a in self.eng.world.armies:
                if a.q == q and a.r == r:
                    self.selected_army = a
                    break
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            if mods & pygame.KMOD_SHIFT:
                self.order_step(-1, 0)
            else:
                self.move_selection(-1, 0)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            if mods & pygame.KMOD_SHIFT:
                self.order_step(1, 0)
            else:
                self.move_selection(1, 0)
        elif ev.key in (pygame.K_UP, pygame.K_w):
            if mods & pygame.KMOD_SHIFT:
                self.order_step(0, -1)
            else:
                self.move_selection(0, -1)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            if mods & pygame.KMOD_SHIFT:
                self.order_step(0, 1)
            else:
                self.move_selection(0, 1)

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
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()
        sys.exit(0)

    def draw(self) -> None:
        scr = self.screen
        scr.fill((8, 8, 12))
        w = self.eng.world
        zoom = self.zoom
        sw, sh = scr.get_size()
        for t in w.tiles:
            cx, cy = axial_to_pixel(t.q, t.r, self.hex_px)
            sx, sy = self.world_to_screen(cx, cy)
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
            rad = int(self.hex_px * 0.3 * zoom)
            rect_w = rad * 2
            rect_h = rad
            rect = pygame.Rect(psx - rect_w // 2, psy - rect_h // 2, rect_w, rect_h)
            pygame.draw.rect(scr, (255, 255, 255), rect)
            pygame.draw.rect(scr, (0, 0, 0), rect, 2)
            pygame.draw.line(scr, (0, 0, 0), rect.topleft, rect.bottomright, 2)
            pygame.draw.line(scr, (0, 0, 0), rect.topright, rect.bottomleft, 2)
            if a is self.selected_army:
                pygame.draw.rect(scr, (255, 255, 255), rect.inflate(4, 4), 2)
        date = self.eng.world.calendar
        dstr = f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
        hud_parts = [f"{dstr}", f"scale:{self.eng.world.time_scale}", f"view:{self.view_mode}"]
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
        if self.show_overlay:
            pygame.draw.rect(scr, (255, 255, 255), (0, 0, sw - 1, sh - 1), 1)
            pygame.draw.line(scr, (0, 0, 0), (0, 0), (sw - 1, sh - 1), 1)
            pygame.draw.line(scr, (0, 0, 0), (sw - 1, 0), (0, sh - 1), 1)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spawn-demo-armies", type=int, default=0)
    parser.add_argument("--no-overlay", action="store_true")
    args = parser.parse_args(argv)
    gui = GameGUI(show_overlay=not args.no_overlay)
    for i in range(args.spawn_demo_armies):
        cid = gui.eng.add_civ(f"Civ{i}", (i, 0))
        gui.eng.add_army(cid, (i, 0))
    gui.run()


if __name__ == "__main__":
    main()
