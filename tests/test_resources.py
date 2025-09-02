import pytest
from engine import TileHex
from resources import yields_for, FEATURE_MULTIPLIERS


def test_yields_for_biome_and_feature():
    t = TileHex(0, 0, biome="grass")
    f, p = yields_for(t)
    assert f == pytest.approx(1.0)
    assert p == pytest.approx(0.6)

    t.feature = "forest"
    mf, mp = FEATURE_MULTIPLIERS["forest"]
    f2, p2 = yields_for(t)
    assert f2 == pytest.approx(1.0 * mf)
    assert p2 == pytest.approx(0.6 * mp)
