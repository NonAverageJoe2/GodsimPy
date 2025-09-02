from engine import SimulationEngine


def test_weekly_steps_about_one_year():
    eng = SimulationEngine()
    for _ in range(52):
        eng.advance_turn()
    cal = eng.world.calendar
    assert cal.year == 0
    assert cal.month == 12
    assert cal.day >= 24
    eng.advance_turn()
    assert eng.world.calendar.year >= 1
