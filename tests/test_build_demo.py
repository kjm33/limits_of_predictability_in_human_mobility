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


def test_lz_phrases_cut_at_novel_blocks():
    # ABAB: "A" new, "B" new, then "AB" was seen -> phrase runs to the end.
    assert bd.lz_phrases([0, 1, 0, 1]) == [[0], [1], [2, 3]]
    # parse is a partition of the sequence
    seq = [3, 3, 1, 3, 3, 2, 5]
    flat = [i for phrase in bd.lz_phrases(seq) for i in phrase]
    assert flat == list(range(len(seq)))
    # the first block of anything is length 1 (empty prefix)
    assert bd.lz_phrases([5, 5, 5])[0] == [0]


def test_lz_toy_trio_orders_routine_drum_free():
    trio = bd.lz_toy_trio()
    names = [t["name"] for t in trio]
    assert names == ["the routine", "the drum beat", "the free rein"]
    routine, drum, free = trio
    assert routine["S_actual"] == 0.0
    assert free["S_actual"] == 2.0  # log2(4): nothing ever repeats
    assert routine["S_actual"] < drum["S_actual"] < free["S_actual"]
    assert all(len(t["diary"]) == 4 for t in trio)


def test_fano_curve_endpoints_and_monotone():
    import math

    pts = bd.fano_curve(121)
    assert pts[0][1] >= 0.999  # S=0 -> perfectly guessable
    assert abs(pts[-1][0] - math.log2(121)) < 0.01  # S tops out at log2(N)
    assert pts[-1][1] < 1 / 121 + 0.01  # max S -> uniform chance 1/N
    pis = [p[1] for p in pts]
    assert all(a >= b - 1e-9 for a, b in zip(pis[:-1], pis[1:], strict=True))


def test_markov_table_perfect_alternation():
    cells = [0, 1] * 50
    known = [1] * 100
    m = bd.markov_table(cells, known, top=2)
    assert m["rows"][0][1] == 1.0  # from 0 -> always 1
    assert m["rows"][1][0] == 1.0
    assert m["acc"] == 1.0
    assert m["n_pairs"] == 99


def test_markov_table_skips_unseen_origins():
    # train pairs all start at 0; the test slice is (0,5) + 8x(5,5). Origin 5
    # was never seen in training -> those 8 are skipped, only (0,5) evaluated
    # (and missed: the table predicts 0).
    cells = [0] * 36 + [5] * 9
    known = [1] * 45
    m = bd.markov_table(cells, known, top=1)
    assert m["top"] == [0]
    assert m["n_eval"] == 1
    assert m["acc"] == 0.0


def test_markov_table_unknown_hours_dropped():
    # unknown hours break the chain: no pair may span a known/unknown edge
    cells = [0, 1] * 15
    known = [1, 0] + [1] * 28
    m = bd.markov_table(cells, known, top=2)
    # pairs only exist where BOTH hours are known: i=2..27 -> 26... minus none
    assert m["n_pairs"] == sum(
        1 for i in range(29) if known[i] and known[i + 1]
    )
    assert m["n_pairs"] < 29  # the two unknown hours really removed pairs


def test_abs_slots_parquet_ms_units_safe():
    # datetime64[ms] (parquet round-trip dtype) must not be assumed ns.
    stamps = pd.Series(
        np.array(["2010-01-04T10:00"], dtype="datetime64[ms]").astype("datetime64[us]")
    )
    out = bd.abs_slots(stamps, 15)
    assert out.iloc[0] == out.iloc[0]  # finite int
    assert out.iloc[0] > 1_000_000  # ~40 years of 15-min slots
