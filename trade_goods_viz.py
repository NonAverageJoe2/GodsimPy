"""Minimal visualisation helpers for the trade goods system.

These classes provide tiny wrappers around ``pygame`` drawing functions so the
example game can render information about trade goods.  The implementation is
intentionally lightweight – it only draws simple shapes and text and is not
optimised for performance.  It is sufficient for demonstration purposes and
allows the new trade goods system to integrate with the existing codebase.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import pygame

from trade_goods import GOOD_COLOURS, TileTradeGoods


class TradeGoodsRenderer:
    """Utility class responsible for drawing trade good information."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font = pygame.font.Font(None, 16)

    # ------------------------------------------------------------------
    def _colour_for(self, name: str) -> Tuple[int, int, int]:
        for good, col in GOOD_COLOURS.items():
            if good.name == name:
                return col
        # deterministic fallback colour
        base = abs(hash(name)) & 0xFFFFFF
        return ((base >> 16) & 255, (base >> 8) & 255, base & 255)

    # ------------------------------------------------------------------
    def draw_pie_chart(self, centre: Tuple[int, int], radius: int,
                       data: Dict[str, float], show_labels: bool = True) -> None:
        """Draw a very small pie chart showing the distribution of ``data``."""
        total = sum(data.values())
        if total <= 0:
            return
        start = 0.0
        cx, cy = centre
        for name, value in data.items():
            frac = value / total
            end = start + frac * 2 * math.pi
            points = [(cx, cy)]
            steps = max(2, int(frac * 30))
            for i in range(steps + 1):
                ang = start + (end - start) * i / steps
                points.append((cx + radius * math.cos(ang),
                               cy + radius * math.sin(ang)))
            pygame.draw.polygon(self.screen, self._colour_for(name), points)
            start = end

    # ------------------------------------------------------------------
    def draw_trade_panel(self, pos: Tuple[int, int], tile_goods: TileTradeGoods,
                         title: str) -> None:
        """Draw a simple information panel listing tile trade goods."""
        x, y = pos
        width, height = 260, 160
        pygame.draw.rect(self.screen, (0, 0, 0), (x, y, width, height))
        pygame.draw.rect(self.screen, (200, 200, 200), (x, y, width, height), 2)
        title_surf = self.font.render(title, True, (255, 255, 255))
        self.screen.blit(title_surf, (x + 5, y + 5))
        y_off = 25
        for good, prod in tile_goods.active_goods.items():
            text = f"{good.name}: {prod.percentage:.1f}%"
            surf = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surf, (x + 10, y + y_off))
            y_off += 18

    # ------------------------------------------------------------------
    def draw_province_overview(self, pos: Tuple[int, int], title: str,
                               goods: Dict[str, float]) -> None:
        x, y = pos
        width, height = 220, 120
        pygame.draw.rect(self.screen, (0, 0, 0), (x, y, width, height))
        pygame.draw.rect(self.screen, (200, 200, 200), (x, y, width, height), 2)
        title_surf = self.font.render(title, True, (255, 255, 255))
        self.screen.blit(title_surf, (x + 5, y + 5))
        y_off = 25
        for name, amount in goods.items():
            text = f"{name}: {amount:.1f}"
            surf = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surf, (x + 10, y + y_off))
            y_off += 18


class TradeGoodsUI:
    """Convenience wrapper bundling the renderer with selection state."""

    def __init__(self, screen: pygame.Surface, manager):
        self.screen = screen
        self.manager = manager
        self.renderer = TradeGoodsRenderer(screen)
        self.selected_tile: Tuple[int, int] | None = None
