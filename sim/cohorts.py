from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from numpy.typing import NDArray

Float = np.float32
FMap = NDArray[np.float32]


FEMALE_FRAC: Float = Float(0.5)
FERTILITY_PER_FEMALE_PER_YEAR: Float = Float(0.12)
MORTALITY_PER_YEAR: Dict[str, Float] = {
    "c0_4": Float(0.020),
    "c5_14": Float(0.002),
    "c15_39": Float(0.004),
    "c40_64": Float(0.010),
    "c65p": Float(0.060),
}
BIN_WIDTHS_YEARS: Dict[str, int] = {
    "c0_4": 5,
    "c5_14": 10,
    "c15_39": 25,
    "c40_64": 25,
    "c65p": 999,
}


def _nan_guard(a: FMap) -> FMap:
    return np.nan_to_num(np.ascontiguousarray(a, dtype=np.float32), copy=False)


def _nonneg(a: FMap) -> FMap:
    return np.maximum(a, 0.0, dtype=np.float32)


COHORT_KEYS = ("c0_4", "c5_14", "c15_39", "c40_64", "c65p")


def init_from_total(total: FMap, *, proportions: Dict[str, float] | None = None) -> Dict[str, FMap]:
    """Initialize cohort arrays from total population map."""
    t = np.asarray(total, dtype=np.float32)
    if t.ndim != 2:
        raise ValueError("total must be 2D")
    if not np.isfinite(t).all():
        raise ValueError("total contains non-finite values")
    t = _nonneg(_nan_guard(t))

    props = proportions or {
        "c0_4": 0.10,
        "c5_14": 0.16,
        "c15_39": 0.32,
        "c40_64": 0.28,
        "c65p": 0.14,
    }
    for k in COHORT_KEYS:
        if k not in props:
            raise ValueError(f"missing proportion for {k}")
    pvals = np.array([float(props[k]) for k in COHORT_KEYS], dtype=np.float32)
    s = pvals.sum()
    if s <= 0.0:
        raise ValueError("proportions must sum to >0")
    pvals = pvals / s

    return {k: _nonneg(_nan_guard(t * p)) for k, p in zip(COHORT_KEYS, pvals)}


def totals_from_cohorts(coh: Dict[str, FMap]) -> FMap:
    """Return total population from cohort arrays."""
    total = sum(coh[k] for k in COHORT_KEYS)
    return _nonneg(_nan_guard(total))


def workforce_from_cohorts(coh: Dict[str, FMap]) -> FMap:
    """Return workforce population (ages 15-64)."""
    total = coh["c15_39"] + coh["c40_64"]
    return _nonneg(_nan_guard(total))


def fertile_females_from_cohorts(
    coh: Dict[str, FMap], *, female_frac: float = float(FEMALE_FRAC)
) -> FMap:
    """Return number of fertile females from cohort data."""
    frac = np.float32(female_frac)
    ff = coh["c15_39"] * frac
    return _nonneg(_nan_guard(ff))


def births_from_cohorts(
    coh: Dict[str, FMap], *,
    births_per_female_per_year: float = float(FERTILITY_PER_FEMALE_PER_YEAR),
    dt_years: float,
) -> FMap:
    """Compute births over ``dt_years`` from cohort data."""
    ff = fertile_females_from_cohorts(coh)
    births = ff * np.float32(births_per_female_per_year) * np.float32(dt_years)
    return _nonneg(_nan_guard(births))


def deaths_per_bin(
    coh: Dict[str, FMap], *,
    mortality_per_year: Dict[str, float] | None = None,
    dt_years: float = 1.0,
) -> Dict[str, FMap]:
    """Compute deaths per cohort over ``dt_years``."""
    rates = {k: Float(MORTALITY_PER_YEAR[k]) for k in COHORT_KEYS}
    if mortality_per_year:
        for k, v in mortality_per_year.items():
            rates[k] = Float(v)
    dt = np.float32(dt_years)
    deaths: Dict[str, FMap] = {}
    for k in COHORT_KEYS:
        d = coh[k] * rates[k] * dt
        d = np.minimum(np.maximum(d, 0.0, dtype=np.float32), coh[k])
        deaths[k] = _nonneg(_nan_guard(d))
    return deaths


def aging_fluxes(coh: Dict[str, FMap], *, dt_years: float) -> Dict[str, FMap]:
    """Compute aging outflows for each cohort."""
    dt = np.float32(dt_years)
    flux: Dict[str, FMap] = {}
    for k in ("c0_4", "c5_14", "c15_39", "c40_64"):
        width = np.float32(BIN_WIDTHS_YEARS[k])
        frac = np.clip(dt / width, 0.0, 1.0)
        out = coh[k] * frac
        flux[k] = _nonneg(_nan_guard(out))
    flux["c65p"] = np.zeros_like(coh["c65p"], dtype=np.float32)
    return flux


def step_cohorts(
    coh: Dict[str, FMap], *,
    dt_years: float,
    births_per_female_per_year: float = float(FERTILITY_PER_FEMALE_PER_YEAR),
    mortality_per_year: Dict[str, float] | None = None,
) -> Dict[str, FMap]:
    """Advance cohorts forward by ``dt_years``."""
    births = births_from_cohorts(
        coh,
        births_per_female_per_year=births_per_female_per_year,
        dt_years=dt_years,
    )
    deaths = deaths_per_bin(coh, mortality_per_year=mortality_per_year, dt_years=dt_years)
    aging = aging_fluxes(coh, dt_years=dt_years)

    new: Dict[str, FMap] = {}
    new["c0_4"] = coh["c0_4"] + births - deaths["c0_4"] - aging["c0_4"]
    new["c5_14"] = coh["c5_14"] + aging["c0_4"] - deaths["c5_14"] - aging["c5_14"]
    new["c15_39"] = coh["c15_39"] + aging["c5_14"] - deaths["c15_39"] - aging["c15_39"]
    new["c40_64"] = coh["c40_64"] + aging["c15_39"] - deaths["c40_64"] - aging["c40_64"]
    new["c65p"] = coh["c65p"] + aging["c40_64"] - deaths["c65p"]

    for k in COHORT_KEYS:
        new[k] = _nonneg(_nan_guard(new[k]))
    return new


def step_with_capacity(
    coh: Dict[str, FMap],
    K: FMap,
    *,
    dt_years: float,
    births_per_female_per_year: float = float(FERTILITY_PER_FEMALE_PER_YEAR),
    mortality_per_year: Dict[str, float] | None = None,
) -> Dict[str, FMap]:
    """Advance cohorts and apply capacity constraint ``K``."""
    stepped = step_cohorts(
        coh,
        dt_years=dt_years,
        births_per_female_per_year=births_per_female_per_year,
        mortality_per_year=mortality_per_year,
    )
    total = totals_from_cohorts(stepped)
    K_arr = np.asarray(K, dtype=np.float32)
    if K_arr.shape != total.shape:
        raise ValueError("K shape must match cohort maps")
    K_arr = _nonneg(_nan_guard(K_arr))
    scale = np.minimum(np.float32(1.0), K_arr / (total + np.float32(1e-6)))
    scale = _nonneg(_nan_guard(scale))
    new = {k: _nonneg(_nan_guard(stepped[k] * scale)) for k in COHORT_KEYS}
    return new
