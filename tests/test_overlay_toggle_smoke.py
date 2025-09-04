import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from gui.main import GameGUI


def test_overlay_toggle_smoke():
    gui = GameGUI(show_overlay=False)
    assert not gui.show_overlay
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v)
    gui.handle_key(event)
    assert gui.show_overlay
    pygame.quit()
