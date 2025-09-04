# GodsimPy

Hex-grid strategy simulation with a simple Pygame viewer.

## Running tests

```bash
python -m pytest -q
```

## GUI demo

```bash
python -m gui.main --spawn-demo-armies 3
```

Controls:

- Arrow keys / WASD: move selection cursor
- `A`: spawn army for the civ owning the selected hex
- `Shift` + Arrow/WASD: give one-step move order to the selected army
- Right click: set move orders to the clicked hex
- `V`: toggle viewer overlay
- `Esc`: quit
