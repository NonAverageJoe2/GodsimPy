import subprocess

from engine import SimulationEngine


def test_cli_set_timescale(tmp_path):
    world_path = tmp_path / "world.json"
    eng = SimulationEngine()
    eng.save_json(str(world_path))
    subprocess.run([
        "python",
        "cli.py",
        "set-timescale",
        str(world_path),
        "month",
    ], check=True)
    eng2 = SimulationEngine()
    eng2.load_json(str(world_path))
    assert eng2.world.time_scale == "month"


def test_cli_set_date_clamps(tmp_path):
    world_path = tmp_path / "world.json"
    eng = SimulationEngine()
    eng.save_json(str(world_path))
    subprocess.run([
        "python",
        "cli.py",
        "set-date",
        str(world_path),
        "--year",
        "1",
        "--month",
        "13",
        "--day",
        "40",
    ], check=True)
    eng2 = SimulationEngine()
    eng2.load_json(str(world_path))
    assert eng2.world.calendar.year == 1
    assert eng2.world.calendar.month == 12
    assert eng2.world.calendar.day == 31
