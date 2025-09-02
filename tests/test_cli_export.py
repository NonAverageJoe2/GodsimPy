import subprocess
from pathlib import Path

from engine import SimulationEngine


def test_cli_export_writes_images(tmp_path):
    world_path = tmp_path / "world.json"
    eng = SimulationEngine(width=10, height=6, seed=2)
    eng.seed_population_everywhere()
    eng.add_civ("A", (1, 1))
    eng.save_json(str(world_path))

    top_path = tmp_path / "top.png"
    iso_path = tmp_path / "iso.png"

    cmd = [
        "python",
        "cli.py",
        "export",
        "--world",
        str(world_path),
        "--topdown",
        str(top_path),
        "--isometric",
        str(iso_path),
    ]
    subprocess.run(cmd, check=True)

    assert top_path.exists()
    assert iso_path.exists()
