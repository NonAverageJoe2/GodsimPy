from systems.path_network import PathNetwork
import pytest


def test_path_building_and_travel_time():
    net = PathNetwork()
    net.add_settlement("A", 0, 0)
    net.add_settlement("B", 3, 0)

    base = net.travel_time("A", "B")
    assert base == pytest.approx(3.0)

    net.start_path("A", "B", workers=1, build_time=10)
    net.advance(5)
    # Halfway built, no effect yet
    assert net.travel_time("A", "B") == pytest.approx(base)

    net.force_complete_path("A", "B")
    assert net.travel_time("A", "B") == pytest.approx(base * 0.5)

    info = net.debug_info("A", "B")
    assert info["path_exists"]
    assert info["travel_time"] == pytest.approx(base * 0.5)
    assert info["efficiency"] == pytest.approx(2.0)

