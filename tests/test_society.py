import pytest

from society import (
    SocietyType,
    DEFAULT_SOCIETY,
    apply_population_modifiers,
    apply_yield_modifiers,
    apply_movement_modifier,
    apply_military_modifiers,
    choose_society,
)
from sim.civilization import Civilization


def _make_civ() -> Civilization:
    return Civilization(id=0, name="Test", color=(0, 0, 0), rng_seed=1)


def test_agrarian_modifiers_application():
    civ = _make_civ()
    civ.set_society(SocietyType.AGRARIAN)
    mods = civ._society_mods

    cap, growth = apply_population_modifiers(mods, 100.0, 1.0)
    assert cap == pytest.approx(130.0)
    assert growth == pytest.approx(1.15)

    farm, forage = apply_yield_modifiers(mods, 10.0, 5.0)
    assert farm == pytest.approx(12.5)
    assert forage == pytest.approx(4.0)

    move = apply_movement_modifier(mods, 1.0)
    assert move == pytest.approx(1.0 / 0.95)

    strength, cav_cost, unlock = apply_military_modifiers(mods, 100.0, 50.0, 3)
    assert strength == pytest.approx(95.0)
    assert cav_cost == pytest.approx(55.0)
    assert unlock == 3


def test_nomadic_modifiers_application():
    civ = _make_civ()
    civ.set_society(SocietyType.NOMADIC)
    mods = civ._society_mods

    cap, growth = apply_population_modifiers(mods, 100.0, 1.0)
    assert cap == pytest.approx(90.0)
    assert growth == pytest.approx(0.9)

    farm, forage = apply_yield_modifiers(mods, 10.0, 5.0)
    assert farm == pytest.approx(0.0)
    assert forage == pytest.approx(6.25)

    move = apply_movement_modifier(mods, 1.0)
    assert move == pytest.approx(1.0 / 1.15)

    strength, cav_cost, unlock = apply_military_modifiers(mods, 100.0, 50.0, 3)
    assert strength == pytest.approx(110.0)
    assert cav_cost == pytest.approx(42.5)
    assert unlock == 2


def test_ai_society_choice_heuristic():
    # Favour fertility -> Agrarian
    assert choose_society(10.0, 5.0) is SocietyType.AGRARIAN
    # Favour openness -> Nomadic
    assert choose_society(4.0, 9.0) is SocietyType.NOMADIC


def test_proto_governance_research_and_serialization():
    from technology import TechnologySystem

    tech = TechnologySystem()
    assert "proto_governance" in tech.tech_tree.technologies

    civ_state = tech.initialize_civ(0)
    civ_state.researched_techs.update({"agriculture", "animal_husbandry"})
    civ_state.start_research("proto_governance")
    completed = civ_state.add_research_points(100.0, tech.tech_tree)
    assert completed

    civ = _make_civ()
    civ.set_society(SocietyType.NOMADIC)
    data = civ.to_dict()
    assert data["society_type"] == "NOMADIC"
    restored = Civilization.from_dict(data)
    assert restored.society_type is SocietyType.NOMADIC
    assert restored._society_mods == DEFAULT_SOCIETY[SocietyType.NOMADIC]

