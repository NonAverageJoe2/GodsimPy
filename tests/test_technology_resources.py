import pytest
from technology import TechnologySystem, Age


def test_age_resource_requirements_enforced():
    ts = TechnologySystem()
    civ = ts.initialize_civ(1)

    # meet tech requirement for Copper Age
    civ.researched_techs = {f"t{i}" for i in range(Age.COPPER.min_techs_required)}
    assert not civ.can_advance_age(ts.tech_tree)
    ts.update_civ_resources(1, {"copper_ore"})
    assert civ.can_advance_age(ts.tech_tree)
    assert civ.advance_age()
    assert civ.current_age == Age.COPPER

    # set up for Bronze Age
    civ.researched_techs = {f"t{i}" for i in range(Age.BRONZE.min_techs_required)}
    ts.update_civ_resources(1, {"copper_ore"})
    assert not civ.can_advance_age(ts.tech_tree)
    ts.update_civ_resources(1, {"copper_ore", "tin_ore"})
    assert civ.can_advance_age(ts.tech_tree)
