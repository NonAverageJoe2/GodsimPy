"""
Complete example showing how to use the Trade Goods System
with your existing civilization simulation
"""

import pygame
import json
from typing import Dict, List, Tuple

# Import your existing modules
import engine
from worldgen import biomes

# Import the new trade goods modules
from trade_goods import TradeGoodsManager, TradeGood
from trade_goods_viz import TradeGoodsRenderer, TradeGoodsUI


class EnhancedGameEngine:
    """Main game engine with trade goods integration"""

    def __init__(self, width=1200, height=800):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Civilization Simulation - Trade Goods Edition")

        self.clock = pygame.time.Clock()
        self.running = True

        # Initialize world
        self.world = None
        self.trade_manager = None
        self.trade_ui = None

        # UI state
        self.selected_tile = None
        self.show_trade_overlay = True
        self.show_province_view = False

    def initialize_world(self, world_file=None):
        """Initialize or load the world with trade goods"""

        if world_file:
            # Load existing world
            with open(world_file, 'r') as f:
                data = json.load(f)
            self.world = engine.World()
            self.world.load_json(data)

            # Initialize or load trade goods
            if 'trade_goods' in data:
                self.trade_manager = TradeGoodsManager(self.world)
                self.trade_manager.load_json(data['trade_goods'])
            else:
                self.trade_manager = TradeGoodsManager(self.world)
        else:
            # Generate new world
            self.world = engine.World()
            # ... (your existing world generation code)

            # Initialize trade system
            self.trade_manager = TradeGoodsManager(self.world)

        # Attach trade manager to world for easy access
        self.world.trade_manager = self.trade_manager

        # Initialize UI
        self.trade_ui = TradeGoodsUI(self.screen, self.trade_manager)

    def handle_events(self):
        """Handle user input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                # Toggle trade overlay with T
                elif event.key == pygame.K_t:
                    self.show_trade_overlay = not self.show_trade_overlay

                # Toggle province view with P
                elif event.key == pygame.K_p:
                    self.show_province_view = not self.show_province_view

                # Save game with S
                elif event.key == pygame.K_s:
                    self.save_game()

                # Advance turn with SPACE
                elif event.key == pygame.K_SPACE:
                    self.advance_turn()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.handle_tile_click(event.pos)
                elif event.button == 3:  # Right click
                    self.selected_tile = None

    def handle_tile_click(self, screen_pos):
        """Handle clicking on a tile"""
        # Convert screen position to hex coordinates
        q, r = self.screen_to_hex(screen_pos)

        # Check if valid tile
        tile = self.world.get_tile(q, r)
        if tile:
            self.selected_tile = (q, r)

            # Update trade UI
            self.trade_ui.selected_tile = (q, r)

            # Print tile trade info to console
            self.print_tile_trade_info(q, r)

    def print_tile_trade_info(self, q, r):
        """Print trade information for a tile to console"""
        if (q, r) not in self.trade_manager.tile_goods:
            print(f"No trade goods data for tile ({q}, {r})")
            return

        tile_goods = self.trade_manager.tile_goods[(q, r)]
        tile = self.world.get_tile(q, r)

        print(f"\n=== Trade Goods for tile ({q}, {r}) ===")
        print(f"Settlement: {getattr(tile, 'settlement', 'hamlet')}")
        print(f"Population: {getattr(tile, 'pop', 0)}")
        print(f"Max trade good types: {tile_goods.max_goods_types}")
        print(f"\nActive trade goods:")

        for good, prod in tile_goods.active_goods.items():
            print(f"  {good.name}:")
            print(f"    - Percentage: {prod.percentage:.1f}%")
            print(f"    - Workers: {prod.workers}")
            print(f"    - Efficiency: {prod.efficiency:.2f}")
            print(f"    - Production: {prod.amount:.1f}")

    def advance_turn(self):
        """Advance the game by one turn"""
        dt = 1.0  # One year per turn

        # Original game advancement
        engine.advance_turn(self.world, dt)

        # Evolve trade goods
        for civ_id, civ in self.world.civs.items():
            for q, r in civ.tiles:
                self.trade_manager.evolve_production(q, r, dt)

        # Apply economic effects
        self.apply_trade_economics()

        print("Turn advanced!")

    def apply_trade_economics(self):
        """Apply economic effects from trade goods"""
        for civ_id, civ in self.world.civs.items():
            trade_value = 0
            unique_goods = set()

            for q, r in civ.tiles:
                if (q, r) in self.trade_manager.tile_goods:
                    tile_goods = self.trade_manager.tile_goods[(q, r)]

                    for good, prod in tile_goods.active_goods.items():
                        unique_goods.add(good)

                        # Calculate value based on good type
                        base_value = self.get_good_value(good)
                        trade_value += prod.amount * base_value

            # Apply bonuses
            diversity_bonus = 1.0 + (len(unique_goods) * 0.02)
            total_income = trade_value * diversity_bonus

            # Convert to resources
            if hasattr(civ, 'stock_food'):
                food_gain = int(total_income * 0.3)
                civ.stock_food = min(civ.stock_food + food_gain, 999999)

            # Store wealth for future features
            if not hasattr(civ, 'wealth'):
                civ.wealth = 0
            civ.wealth += int(total_income)

    def get_good_value(self, good):
        """Get the economic value of a trade good"""
        luxury = [TradeGood.WINE, TradeGood.SILK, TradeGood.JEWELRY,
                  TradeGood.SPICES, TradeGood.INCENSE]
        processed = [TradeGood.TOOLS, TradeGood.WEAPONS, TradeGood.CLOTH,
                     TradeGood.POTTERY, TradeGood.FURNITURE, TradeGood.BRONZE]

        if good in luxury:
            return 5.0
        elif good in processed:
            return 3.0
        else:
            return 1.0

    def render(self):
        """Render the game"""
        self.screen.fill((50, 50, 100))  # Ocean blue background

        # Render world tiles
        self.render_world()

        # Render trade overlays if enabled
        if self.show_trade_overlay:
            self.render_trade_overlays()

        # Render selected tile info
        if self.selected_tile:
            self.render_tile_info_panel()

        # Render province view if enabled
        if self.show_province_view:
            self.render_province_view()

        # Render UI elements
        self.render_ui()

        pygame.display.flip()

    def render_world(self):
        """Render the base world map"""
        # This would be your existing world rendering code
        # For now, a simple hex grid representation

        for civ_id, civ in self.world.civs.items():
            for q, r in civ.tiles:
                tile = self.world.get_tile(q, r)
                if tile:
                    x, y = self.hex_to_screen(q, r)

                    # Draw hex (simplified)
                    color = self.get_tile_color(tile)
                    pygame.draw.circle(self.screen, color, (x, y), 20)

                    # Draw settlement marker
                    settlement = getattr(tile, 'settlement', None)
                    if settlement:
                        marker_color = (255, 255, 255)
                        if settlement == 'capital':
                            pygame.draw.circle(self.screen, marker_color, (x, y), 8)
                        elif settlement == 'city':
                            pygame.draw.circle(self.screen, marker_color, (x, y), 6)
                        elif settlement == 'town':
                            pygame.draw.circle(self.screen, marker_color, (x, y), 4)

    def render_trade_overlays(self):
        """Render small pie charts over tiles showing trade goods"""
        for (q, r), tile_goods in self.trade_manager.tile_goods.items():
            if len(tile_goods.active_goods) == 0:
                continue

            x, y = self.hex_to_screen(q, r)

            # Only show for towns and cities
            tile = self.world.get_tile(q, r)
            settlement = getattr(tile, 'settlement', '')

            if settlement in ['town', 'city', 'capital']:
                goods_data = {
                    good.name: prod.percentage
                    for good, prod in tile_goods.active_goods.items()
                }

                # Draw small pie chart
                renderer = TradeGoodsRenderer(self.screen)
                renderer.draw_pie_chart((x, y + 30), 15, goods_data,
                                       show_labels=False)

    def render_tile_info_panel(self):
        """Render detailed information panel for selected tile"""
        if not self.selected_tile:
            return

        q, r = self.selected_tile

        if (q, r) in self.trade_manager.tile_goods:
            tile_goods = self.trade_manager.tile_goods[(q, r)]
            tile = self.world.get_tile(q, r)
            settlement = getattr(tile, 'settlement', 'Settlement')

            # Use the trade UI to render the panel
            self.trade_ui.renderer.draw_trade_panel((900, 50),
                                                   tile_goods,
                                                   f"{settlement} at ({q},{r})")

    def render_province_view(self):
        """Render province-level trade overview"""
        # Group tiles by civilization
        for civ_id, civ in self.world.civs.items():
            # Get aggregated trade data for this civ
            province_goods = self.trade_manager.get_province_trade_summary(civ.tiles)

            if province_goods:
                # Position based on civ ID
                x = 50 + (civ_id % 3) * 300
                y = 50 + (civ_id // 3) * 300

                self.trade_ui.renderer.draw_province_overview(
                    (x, y),
                    f"Civilization {civ_id}",
                    province_goods
                )

    def render_ui(self):
        """Render UI elements and instructions"""
        font = pygame.font.Font(None, 24)

        instructions = [
            "Controls:",
            "T - Toggle trade overlay",
            "P - Toggle province view",
            "SPACE - Advance turn",
            "S - Save game",
            "ESC - Exit",
            "Click tile for details"
        ]

        y = 10
        for instruction in instructions:
            text = font.render(instruction, True, (255, 255, 255))
            self.screen.blit(text, (10, y))
            y += 25

    def get_tile_color(self, tile):
        """Get color for a tile based on biome"""
        biome = getattr(tile, 'biome', 0)

        # Handle both string and int biomes
        biome_colors = {
            'grass': (100, 200, 100),
            'forest': (50, 150, 50),
            'mountain': (150, 150, 150),
            'desert': (240, 220, 130),
            'ocean': (50, 50, 200),
            'coast': (100, 100, 200),
            0: (100, 200, 100),  # grass
            1: (100, 100, 200),  # coast
            2: (150, 150, 150),  # mountain
            3: (50, 50, 200),    # ocean
            4: (240, 220, 130),  # desert
        }

        return biome_colors.get(biome, (100, 100, 100))

    def hex_to_screen(self, q, r):
        """Convert hex coordinates to screen position"""
        # Simple offset coordinate conversion
        size = 30
        x = size * (3/2 * q) + 400
        y = size * (3**0.5 * (r + q/2)) + 300
        return int(x), int(y)

    def screen_to_hex(self, screen_pos):
        """Convert screen position to hex coordinates"""
        x, y = screen_pos
        x -= 400
        y -= 300

        size = 30
        q = (2/3 * x) / size
        r = (-1/3 * x + (3**0.5)/3 * y) / size

        # Round to nearest hex
        return round(q), round(r)

    def save_game(self):
        """Save the game state including trade goods"""
        save_data = self.world.save_json()
        save_data['trade_goods'] = self.trade_manager.save_json()

        with open('savegame_with_trade.json', 'w') as f:
            json.dump(save_data, f, indent=2)

        print("Game saved!")

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            self.render()
            self.clock.tick(30)  # 30 FPS

        pygame.quit()


# Entry point
if __name__ == "__main__":
    game = EnhancedGameEngine()

    # Initialize with existing world or create new
    try:
        game.initialize_world('savegame_with_trade.json')
        print("Loaded existing game")
    except Exception:
        game.initialize_world()
        print("Created new world")

    game.run()
