from engine import SimulationEngine

def run(world_path: str, weeks: int = 52, save_path: str | None = None) -> dict:
    eng = SimulationEngine()
    eng.load_json(world_path)
    for _ in range(weeks):
        eng.advance_turn()
    if save_path:
        eng.save_json(save_path)
    return eng.summary()
