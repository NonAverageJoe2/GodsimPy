import math
from hexgrid import axial_to_pixel, pixel_to_axial


def test_axial_pixel_roundtrip():
    size = 10.0
    for q in range(5):
        for r in range(5):
            x, y = axial_to_pixel(q, r, size)
            rq, rr = pixel_to_axial(x, y, size)
            assert (rq, rr) == (q, r)


def test_pixel_to_axial_nearest():
    size = 10.0
    # Point slightly offset from the center should still map to the same hex
    q, r = 2, 3
    x, y = axial_to_pixel(q, r, size)
    dx, dy = x + size * 0.1, y + size * 0.1  # inside the hex
    rq, rr = pixel_to_axial(dx, dy, size)
    assert (rq, rr) == (q, r)
