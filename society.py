"""Society type definitions and modifiers.

This module introduces a minimal *society* system which is used by the
tests in this kata.  The real game would wire these modifiers into the
economy, movement and military systems.  For the purposes of the tests we
only provide light‐weight helpers that apply the modifiers to numeric
values.  The design intentionally mirrors the specification provided in the
user instructions so that additional systems can easily plug into it in the
future.

The module automatically loads balance values from
``balance/society.json`` if the file exists.  When the file is missing the
hard coded defaults are used which keeps the original behaviour of the
simulation intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, Tuple
import json
import os


class SocietyType(Enum):
    """Enumeration of available society types."""

    HUNTER_GATHERER = auto()
    AGRARIAN = auto()
    NOMADIC = auto()


@dataclass(frozen=True)
class SocietyModifiers:
    """Collection of numeric modifiers for a given society type."""

    # economy / food / population
    food_capacity_mult: float
    pop_growth_mult: float
    settled_farm_yield_mult: float
    nomad_foraging_yield_mult: float
    # borders & movement
    static_borders: bool
    caravan_pop_capacity: int
    movement_speed_mult: float
    # military
    base_military_strength_mult: float
    cavalry_cost_mult: float
    cavalry_earliness_bonus: int


# ---------------------------------------------------------------------------
# Default registry
# ---------------------------------------------------------------------------


DEFAULT_SOCIETY: Dict[SocietyType, SocietyModifiers] = {
    SocietyType.HUNTER_GATHERER: SocietyModifiers(
        food_capacity_mult=1.0,
        pop_growth_mult=1.0,
        settled_farm_yield_mult=0.0,
        nomad_foraging_yield_mult=1.0,
        static_borders=False,
        caravan_pop_capacity=0,
        movement_speed_mult=1.0,
        base_military_strength_mult=1.0,
        cavalry_cost_mult=1.0,
        cavalry_earliness_bonus=0,
    ),
    SocietyType.AGRARIAN: SocietyModifiers(
        food_capacity_mult=1.3,
        pop_growth_mult=1.15,
        settled_farm_yield_mult=1.25,
        nomad_foraging_yield_mult=0.8,
        static_borders=True,
        caravan_pop_capacity=0,
        movement_speed_mult=0.95,
        base_military_strength_mult=0.95,
        cavalry_cost_mult=1.1,
        cavalry_earliness_bonus=0,
    ),
    SocietyType.NOMADIC: SocietyModifiers(
        food_capacity_mult=0.9,
        pop_growth_mult=0.9,
        settled_farm_yield_mult=0.0,
        nomad_foraging_yield_mult=1.25,
        static_borders=False,
        caravan_pop_capacity=2000,
        movement_speed_mult=1.15,
        base_military_strength_mult=1.1,
        cavalry_cost_mult=0.85,
        cavalry_earliness_bonus=-1,
    ),
}


def _balance_path(default_path: Optional[str] = None) -> str:
    """Return path to the society balance file."""

    if default_path is not None:
        return default_path
    return os.path.join(os.path.dirname(__file__), "balance", "society.json")


def load_balance(path: Optional[str] = None) -> None:
    """Load balance data from ``balance/society.json`` if available.

    The JSON file maps society type names to dictionaries of modifier
    values.  Missing or malformed entries are ignored.  The loaded values
    replace the corresponding entries in :data:`DEFAULT_SOCIETY`.
    """

    fn = _balance_path(path)
    try:
        with open(fn, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return

    for key, vals in data.items():
        try:
            st = SocietyType[key]
        except KeyError:
            continue
        try:
            DEFAULT_SOCIETY[st] = SocietyModifiers(**vals)
        except TypeError:
            # Skip malformed entries
            continue


# Load balance at import time so callers get configured defaults.
load_balance()


# ---------------------------------------------------------------------------
# Modifier application helpers
# ---------------------------------------------------------------------------


def apply_population_modifiers(mods: SocietyModifiers, food_capacity: float, pop_growth: float) -> Tuple[float, float]:
    """Apply population related modifiers.

    Parameters
    ----------
    mods:
        Modifier data for a society type.
    food_capacity:
        Base food storage capacity.
    pop_growth:
        Base population growth multiplier.
    """

    return (food_capacity * mods.food_capacity_mult,
            pop_growth * mods.pop_growth_mult)


def apply_yield_modifiers(mods: SocietyModifiers, farm_yield: float, forage_yield: float) -> Tuple[float, float]:
    """Apply yield modifiers for settled farms and mobile foraging."""

    farm = farm_yield * mods.settled_farm_yield_mult
    forage = forage_yield * mods.nomad_foraging_yield_mult
    return farm, forage


def apply_movement_modifier(mods: SocietyModifiers, move_cost: float) -> float:
    """Return movement cost after applying movement speed modifier."""

    if mods.movement_speed_mult == 0:
        return move_cost
    return move_cost / mods.movement_speed_mult


def apply_military_modifiers(
    mods: SocietyModifiers,
    strength: float,
    cavalry_cost: float,
    unlock_tier: int,
) -> Tuple[float, float, int]:
    """Apply military related modifiers."""

    strength = strength * mods.base_military_strength_mult
    cav_cost = cavalry_cost * mods.cavalry_cost_mult
    unlock = unlock_tier + mods.cavalry_earliness_bonus
    return strength, cav_cost, unlock


# ---------------------------------------------------------------------------
# AI helper
# ---------------------------------------------------------------------------


def choose_society(
    fertility_score: float,
    openness_score: float,
    *,
    weight_fertility: float = 1.0,
    weight_openness: float = 1.0,
) -> SocietyType:
    """Return the AI's preferred :class:`SocietyType` based on scores.

    The heuristic is intentionally simple and fully deterministic so that
    unit tests can exercise it directly.
    """

    if fertility_score * weight_fertility >= openness_score * weight_openness:
        return SocietyType.AGRARIAN
    return SocietyType.NOMADIC


__all__ = [
    "SocietyType",
    "SocietyModifiers",
    "DEFAULT_SOCIETY",
    "load_balance",
    "apply_population_modifiers",
    "apply_yield_modifiers",
    "apply_movement_modifier",
    "apply_military_modifiers",
    "choose_society",
]

