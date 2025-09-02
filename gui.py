import sys
import pygame
from engine import SimulationEngine

TILE = 16  # pixels

class GameGUI:
    def __init__(self, world_path: str):
        pygame.init()
        self.clock = pygame.time.Clock()
        self.eng = SimulationEngine()
        self.eng.load_json(world_path)
        w, h = self.eng.world.width, self.eng.world.height
        self.zoom = 1.0
        self.camera_x = 0
        self.camera_y = 0
        self.screen = pygame.display.set_mode((min(1280, w*TILE), min(800, h*TILE)))
        pygame.display.set_caption("Sim GUI")
        self.font = pygame.font.SysFont("consolas", 16)

    def world_to_screen(self, x, y):
        sx = int((x * TILE - self.camera_x) * self.zoom)
        sy = int((y * TILE - self.camera_y) * self.zoom)
        return sx, sy

    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    elif ev.key == pygame.K_SPACE:
                        self.eng.advance_turn()
                    elif ev.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                        self.eng.save_json("autosave.json")
                    elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS):
                        self.zoom = min(4.0, self.zoom * 1.2)
                    elif ev.key == pygame.K_MINUS:
                        self.zoom = max(0.25, self.zoom / 1.2)

            keys = pygame.key.get_pressed()
            pan = 10 / self.zoom
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.camera_x = max(0, self.camera_x - pan)
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.camera_x = min(self.eng.world.width * TILE, self.camera_x + pan)
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.camera_y = max(0, self.camera_y - pan)
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.camera_y = min(self.eng.world.height * TILE, self.camera_y + pan)

            self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()
        sys.exit(0)

    def draw(self):
        scr = self.screen
        scr.fill((8, 8, 12))
        w = self.eng.world
        size = int(TILE * self.zoom)

        for t in w.tiles:
            sx, sy = self.world_to_screen(t.x, t.y)
            if sx + size < 0 or sy + size < 0 or sx > scr.get_width() or sy > scr.get_height():
                continue
            if t.owner is None:
                base = (60, 60, 60)
            else:
                ci = (t.owner * 97) % 255
                base = (40 + ci//2, 80, 120)
            b = min(200, 40 + (t.pop // 2))
            color = (min(255, base[0] + b//6), min(255, base[1] + b//6), min(255, base[2] + b//6))
            pygame.draw.rect(scr, color, (sx, sy, size-1, size-1))

        summary = self.eng.summary()
        text = f"Turn {summary['turn']} | Tiles owned: {summary['owned_tiles']} | Total pop: {summary['total_pop']}"
        hud = self.font.render(text, True, (240, 240, 240))
        scr.blit(hud, (8, 8))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gui.py path/to/world.json")
        sys.exit(1)
    GameGUI(sys.argv[1]).run()
