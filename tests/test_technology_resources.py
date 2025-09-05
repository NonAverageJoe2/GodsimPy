import pytest
from technology import TechnologySystem, Age


def test_age_advancement_does_not_require_metal_resources():
    ts = TechnologySystem()
    civ = ts.initialize_civ(1)

    # Meet tech requirement for Copper Age; no resources needed
    civ.researched_techs = {f"t{i}" for i in range(Age.COPPER.min_techs_required)}
    assert civ.can_advance_age(ts.tech_tree)
    assert civ.advance_age()
    assert civ.current_age == Age.COPPER

    # Set up for Bronze Age; still no resource requirement
    civ.researched_techs = {f"t{i}" for i in range(Age.BRONZE.min_techs_required)}
    assert civ.can_advance_age(ts.tech_tree)
    assert civ.advance_age()
    assert civ.current_age == Age.BRONZE
