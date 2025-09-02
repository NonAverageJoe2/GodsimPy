# GodsimPy GUI

## Overview
The GodsimPy GUI provides an interactive interface for the civilization simulation game. It features a hexagonal map display, real-time simulation, and detailed information panels.

## Installation

1. Ensure you have Python 3.8+ installed
2. Install required dependencies:
```bash
pip install pygame numpy Pillow noise
```

3. Run the GUI:
```bash
# From the repository root:
python run_gui.py

# Or directly:
python gui/main.py

# With custom parameters:
python gui/main.py --width 80 --height 60 --civs 7 --seed 42
```

## Features

### 🗺️ Interactive Hex Map
- **Hexagonal grid rendering** with smooth zoom and pan
- **Multiple view modes:**
  - Political: Shows civilization territories
  - Terrain: Displays biomes and terrain features
  - Population: Visualizes population density
  - Resources: Shows food yield distribution
- **Tile selection** with visual feedback
- **Hover highlighting** for easy navigation

### 📊 Information Panels

#### Right Info Panel
- **World Statistics:**
  - Current date and turn counter
  - Time scale (week/month/year)
  - Total world population
  - Number of owned tiles
  
- **Civilization List:**
  - Color-coded civilization names
  - Population count per civilization
  - Territory size (tile count)
  
- **Selected Tile Info:**
  - Coordinates and biome type
  - Terrain features
  - Owner civilization
  - Current population
  - Resource yields (food & production)

#### Hex Information Popup
Click on any hex tile to see detailed information:
- **Terrain details** with elevation data
- **Ownership history** and control duration
- **Population metrics** with carrying capacity
- **Resource yields** with visual bars
- **Strategic value** calculation
- **Neighboring civilizations** list

### 🎮 Control Panel
Located at the bottom of the screen:
- **Pause/Play button** for simulation control
- **Speed controls** (1x, 2x, 3x simulation speed)
- **View mode selector** (Political, Terrain, Population, Resources)
- **Keyboard shortcuts** display

## Controls

### Mouse Controls
| Action | Description |
|--------|-------------|
| Left Click | Select hex tile / Show hex popup |
| Left Drag | Pan the camera across the map |
| Scroll Wheel | Zoom in/out |
| Right Click | (Reserved for future context menu) |

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Space | Pause/Resume simulation |
| 1 | Normal speed (1x) |
| 2 | Fast speed (2x) |
| 3 | Very fast speed (3x) |
| Q | Political view mode |
| W | Terrain view mode |
| E | Population view mode |
| R | Resources view mode |
| Ctrl+S | Quick save current game |
| Escape | (Reserved for menu) |

## View Modes Explained

### Political View 🏛️
- Civilizations shown in distinct colors
- Unowned territories appear darker
- Clear borders between civilizations
- Best for tracking territorial expansion

### Terrain View 🏔️
- Shows underlying biomes:
  - Green: Grassland
  - Tan: Coast/Desert
  - Gray: Mountains
  - Blue: Ocean
- Civilization borders shown as colored outlines
- Terrain features visible

### Population View 👥
- Heat map of population density
- Brighter areas = higher population
- Dark areas = uninhabited
- Useful for identifying growth centers

### Resources View 🌾
- Green intensity shows food yield
- Brighter = more productive land
- Helps identify prime settlement locations

## Game Mechanics

### Simulation
- **Time progression:** Weeks, months, or years per turn
- **Population growth:** Logistic growth based on food availability
- **Territorial expansion:** Civilizations expand every 4 turns
- **Resource management:** Food determines carrying capacity

### Civilizations
- Start with initial population of 100
- Expand to adjacent tiles based on food value
- Population grows according to available resources
- Each civilization has a unique color identifier

## Command Line Options

```bash
python gui/main.py [options]

Options:
  --load PATH      Load existing world from NPZ file
  --width N        World width in hexes (default: 64)
  --height N       World height in hexes (default: 48)
  --seed N         Random seed for world generation
  --civs N         Number of civilizations (default: 5)
```

## Saving and Loading

### Quick Save
Press `Ctrl+S` during gameplay to save the current world state to `quicksave.npz`

### Loading a Save
```bash
python gui/main.py --load quicksave.npz
```

### Save File Format
Saves are stored in NumPy's NPZ format containing:
- World dimensions and seed
- Height map and biome data
- Civilization territories
- Population distribution
- Current date and turn

## Performance Tips

1. **Reduce world size** for better performance on slower systems
2. **Lower simulation speed** if experiencing lag during fast forward
3. **Close hex popup** when not needed to improve rendering
4. **Collapse info panel** for more map viewing area

## Troubleshooting

### GUI Won't Start
- Ensure pygame is installed: `pip install pygame`
- Check Python version (3.8+ required)
- Verify all files are in correct directories

### Low FPS
- Reduce world size
- Close unnecessary popups
- Update pygame to latest version

### Civilizations Not Expanding
- Check simulation is not paused
- Verify civilizations have sufficient population (60+)
- Ensure there are unowned adjacent tiles

## Future Features (Planned)
- 🏗️ Building placement system
- ⚔️ Combat and unit movement
- 🔬 Technology tree
- 📊 Graphs and statistics
- 🎵 Sound effects and music
- 💾 Multiple save slots
- 🏆 Victory conditions
- 🤝 Diplomacy system

## Development

### File Structure
```
gui/
├── main.py          # Main GUI application
├── hex_popup.py     # Detailed hex information popup
└── README.md        # This documentation
```

### Extending the GUI
The GUI is designed to be modular. To add new features:

1. **New view modes:** Add to `ViewMode` enum and implement in `HexRenderer.get_hex_color()`
2. **New panels:** Create a new class following the `InfoPanel` pattern
3. **New controls:** Add to `ControlPanel` and handle in `handle_events()`

## Credits
GodsimPy GUI built with:
- Pygame for rendering and input
- NumPy for data processing
- Python 3 for core logic

---
*For more information about the simulation engine, see the main README.md*