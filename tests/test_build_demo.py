"""Unit tests for scripts/build_demo.py pure helpers — synthetic data only."""

import importlib.util
from pathlib import Path

import h3
import numpy as np
import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "build_demo", Path(__file__).resolve().parents[1] / "scripts" / "build_demo.py"
)
bd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bd)


def ts(minutes_since_epoch: int) -> pd.Timestamp:
    return pd.Timestamp("1970-01-01") + pd.Timedelta(minutes=minutes_since_epoch)


def test_abs_slots_buckets_by_resolution():
    stamps = pd.Series([ts(0), ts(14), ts(15), ts(150)])
    out = bd.abs_slots(stamps, 15).tolist()
    assert out == [0, 0, 1, 10]


def test_week_grid_maps_thursday_index_zero():
    # 1970-01-01 was a Thursday; a 15-min stop in the first bucket lands on
    # weekday index 3 (Mon=0), bucket 0.
    arr = pd.Series([ts(0)])
    dep = pd.Series([ts(15)])
    grid = bd.week_grid(arr, dep, pd.Series([5]), 15)
    assert grid["nb"] == 96
    assert grid["cells"][3 * 96] == 5
    assert grid["support"][3 * 96] == 1


def test_week_grid_stop_spans_midnight():
    # Monday 1970-01-05 23:50 -> Tuesday 00:20 touches Mon bucket 95 and
    # Tue buckets 0-1 of the 15-min grid.
    mon = pd.Timestamp("1970-01-05 23:50")
    tue = pd.Timestamp("1970-01-06 00:20")
    grid = bd.week_grid(pd.Series([mon]), pd.Series([tue]), pd.Series([2]), 15)
    for wslot in (95, 96, 97):
        assert grid["cells"][wslot] == 2, wslot
    assert sum(c != -1 for c in grid["cells"]) == 3


def test_week_grid_modal_cell_and_week_support():
    # Same weekly slot in two different weeks -> modal cell + support 2.
    week_a = pd.Timestamp("1970-01-05 10:00")  # Monday
    week_b = week_a + pd.Timedelta(days=14)
    grid = bd.week_grid(
        pd.Series([week_a, week_b, week_b]),
        pd.Series([week_a + pd.Timedelta(minutes=15),
                   week_b + pd.Timedelta(minutes=15),
                   week_b + pd.Timedelta(minutes=15)]),
        pd.Series([2, 2, 3]),
        15,
    )
    wslot = 40  # Monday 10:00
    assert grid["cells"][wslot] == 2
    assert grid["support"][wslot] == 2


def test_week_grid_skips_unknown_cells():
    grid = bd.week_grid(
        pd.Series([ts(0)]), pd.Series([ts(15)]), pd.Series([-1]), 15
    )
    assert all(c == -1 for c in grid["cells"])


def test_hexes_geojson_closed_rings_lnglat():
    cell = h3.latlng_to_cell(39.9, 116.3, 9)
    fc = bd.hexes_geojson([cell])
    assert fc["type"] == "FeatureCollection"
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]  # closed
    lng, lat = ring[0]
    assert 115 < lng < 117 and 39 < lat < 40  # lng/lat order around Beijing


def test_diary_song_song_quantities():
    out = bd.diary_song(["home", "home", "work", "work"])
    assert out["N"] == 2
    assert out["S_unc"] == 1.0
    assert 0.0 <= out["Pi_actual"] <= 1.0
    assert len(out["diary"]) == 4


def test_toy_diaries_regular_is_more_predictable():
    toys = bd.toy_diaries()
    assert toys["regular"]["Pi_actual"] > toys["wanderer"]["Pi_actual"]
    assert toys["regular"]["S_actual"] < toys["wanderer"]["S_actual"]


def test_abs_slots_parquet_ms_units_safe():
    # datetime64[ms] (parquet round-trip dtype) must not be assumed ns.
    stamps = pd.Series(
        np.array(["2010-01-04T10:00"], dtype="datetime64[ms]").astype("datetime64[us]")
    )
    out = bd.abs_slots(stamps, 15)
    assert out.iloc[0] == out.iloc[0]  # finite int
    assert out.iloc[0] > 1_000_000  # ~40 years of 15-min slots
