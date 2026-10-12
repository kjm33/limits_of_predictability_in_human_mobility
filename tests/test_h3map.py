import h3
import pytest

from mobility import config
from mobility.h3map import cell_area_km2, cell_at, cell_centroid


def test_cell_at_known_coord():
    # Beijing city center
    c8 = cell_at(39.9042, 116.4074, 8)
    assert h3.get_resolution(c8) == 8
    assert h3.is_valid_cell(c8)


def test_parent_chain():
    c9 = cell_at(39.9042, 116.4074, 9)
    assert h3.cell_to_parent(c9, 8) == cell_at(39.9042, 116.4074, 8)
    assert h3.cell_to_parent(c9, 7) == cell_at(39.9042, 116.4074, 7)
    assert h3.cell_to_parent(c9, 6) == cell_at(39.9042, 116.4074, 6)


def test_centroid_roundtrip():
    la, lo = 40.0, 116.5
    c = cell_at(la, lo, config.H3_PRIMARY_RES)
    cla, clo = cell_centroid(c)
    assert cell_at(cla, clo, config.H3_PRIMARY_RES) == c


def test_area_scales():
    a6 = cell_area_km2(cell_at(39.9, 116.4, 6))
    a8 = cell_area_km2(cell_at(39.9, 116.4, 8))
    assert 20 < a6 < 60  # ~36 km^2
    assert 0.3 < a8 < 1.5  # ~0.74 km^2
    assert a6 / a8 == pytest.approx(49, rel=0.2)  # 7 children per level


def test_neighbors_are_close():
    import numpy as np

    c = cell_at(39.9, 116.4, 8)
    la, lo = cell_centroid(c)
    nb = h3.grid_disk(c, 1)
    ds = []
    for n in nb:
        if n == c:
            continue
        nla, nlo = cell_centroid(n)
        ds.append(np.hypot(nla - la, nlo - lo))
    assert all(d < 0.02 for d in ds)  # r8 hexes ~ <2 km apart
