#!/usr/bin/env python3
"""
GodsimPy GUI Launcher

Quick launcher script for the GodsimPy GUI application.
Run this file to start the game with default settings or specify custom parameters.
"""

import os
import sys

# Ensure the gui module can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for required dependencies
try:
    import pygame
    import numpy as np
except ImportError as e:
    print(f"Error: Missing required dependency - {e}")
    print("\nPlease install required packages:")
    print("  pip install pygame numpy Pillow noise")
    sys.exit(1)

# Import and run the GUI
try:
    from gui.main import main
except ImportError:
    print("Error: Could not import GUI module.")
    print("Make sure the 'gui' folder exists with 'main.py'")
    sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print(" GodsimPy - Civilization Simulation Game")
    print("=" * 60)
    print()
    print("Starting GUI...")
    print()
    print("Controls:")
    print("  - Mouse: Left drag to pan, scroll to zoom")
    print("  - Click: Select hex tile for information")
    print("  - Space: Pause/Resume simulation")
    print("  - 1-3: Change simulation speed")
    print("  - Q/W/E/R: Change view mode")
    print("  - Ctrl+S: Quick save")
    print()
    print("=" * 60)
    
    try:
        main()
    except Exception as e:
        print(f"\nError running GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)