"""YJMob100K adapter tests (synthetic grid data only)."""

import numpy as np
import pandas as pd

from mobility import config
from mobility.ingest import haversine_m
from mobility.yjmob import (
    _hour_index,
    grid_vocab,
    hourly_grid_sequences,
    load_poi,
    load_records,
    run_yjmob,
)

EPOCH = pd.Timestamp("2023-01-02 00:00:00")


def _records(rows: list[tuple[int, int, int, int, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["user", "day", "timeslot", "x", "y"]).astype("int64")


def test_load_records_header_sniffing(tmp_path):
    body = "7,0,3,10,20\n7,0,5,10,20\n"
    no_header = tmp_path / "no_header.csv"
    no_header.write_text(body)
    with_header = tmp_path / "with_header.csv"
    with_header.write_text("uid,d,t,x,y\n" + body)
    a = load_records(no_header)
    b = load_records(with_header)
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == ["user", "day", "timeslot", "x", "y"]
    assert a["user"].dtype == np.dtype("int64")


def test_hour_index_detects_timeslot_base():
    one_based = _records([(1, 0, t, 2, 2) for t in (1, 3, 48)])
    zero_based = _records([(1, 0, t, 2, 2) for t in (0, 2, 47)])
    h1 = _hour_index(one_based["day"], one_based["timeslot"])
    h0 = _hour_index(zero_based["day"], zero_based["timeslot"])
    assert list(h1) == [0, 1, 23]
    assert list(h1) == list(h0)
    assert list(_hour_index(pd.Series([2]), pd.Series([3]))) == [49]  # day 2, slot 3 -> hour 49


def test_hourly_majority_and_last_slot_tie():
    # 1-based slots: 1-2 -> hour 0, 3-4 -> hour 1.
    # hour 0: cell (2,2) x2 beats (3,3) x1; hour 1: 1-1 tie, (3,3) logged in the later slot.
    rec = _records(
        [
            (1, 0, 1, 2, 2),
            (1, 0, 1, 2, 2),
            (1, 0, 2, 3, 3),
            (1, 0, 3, 2, 2),
            (1, 0, 4, 3, 3),
        ]
    )
    enc = hourly_grid_sequences(rec, full_span=False)
    assert list(enc["hour"]) == [EPOCH, EPOCH + pd.Timedelta(hours=1)]
    assert enc["cell_idx"].tolist() == [2 * 256 + 2, 3 * 256 + 3]
    assert list(enc.columns) == ["user", "hour", "cell_idx"]
    assert enc["user"].tolist() == ["1", "1"]


def test_full_span_fills_unknown_hours():
    rec = _records([(1, 0, 1, 2, 2), (1, 1, 5, 4, 4), (2, 0, 3, 9, 9)])
    enc = hourly_grid_sequences(rec, full_span=True)
    u1 = enc[enc["user"] == "1"]
    u2 = enc[enc["user"] == "2"]
    # panel semantics: every user spans the global observation window (max day + 1)
    assert len(u1) == 2 * 24 and len(u2) == 2 * 24
    assert (u1["cell_idx"] == config.UNKNOWN).sum() == 2 * 24 - 2
    assert (u2["cell_idx"] == config.UNKNOWN).sum() == 2 * 24 - 1
    assert u1.iloc[0]["hour"] == EPOCH
    assert u2.iloc[-1]["hour"] == EPOCH + pd.Timedelta(hours=47)


def test_grid_vocab_contiguous_ids_and_tokens():
    rec = _records([(1, 0, 1, 2, 2), (1, 0, 3, 2, 3), (1, 1, 1, 10, 10)])
    enc = hourly_grid_sequences(rec, full_span=True)
    vocab, enc2 = grid_vocab(enc)
    assert list(vocab.columns) == ["cell_idx", "h3", "lat", "lon"]
    assert vocab["cell_idx"].tolist() == [0, 1, 2]
    assert vocab["h3"].tolist() == ["2_2", "2_3", "10_10"]  # sorted by packed code
    known = enc2[enc2["cell_idx"] != config.UNKNOWN]
    assert known["h3"].notna().all()
    unk = enc2[enc2["cell_idx"] == config.UNKNOWN]
    assert unk["h3"].isna().all()


def test_grid_vocab_centroid_spacing_is_500m():
    rec = _records([(1, 0, 1, 1, 1), (1, 0, 3, 1, 2), (1, 1, 1, 2, 1)])
    vocab, _ = grid_vocab(hourly_grid_sequences(rec, full_span=False))
    by_token = vocab.set_index("h3")
    d_lon = haversine_m(
        by_token.loc["1_1", "lat"],
        by_token.loc["1_1", "lon"],
        by_token.loc["1_2", "lat"],
        by_token.loc["1_2", "lon"],
    )
    d_lat = haversine_m(
        by_token.loc["1_1", "lat"],
        by_token.loc["1_1", "lon"],
        by_token.loc["2_1", "lat"],
        by_token.loc["2_1", "lon"],
    )
    assert abs(d_lon - 500) < 5
    assert abs(d_lat - 500) < 5


def test_load_poi_pivot_and_bom_categories(tmp_path):
    poi = tmp_path / "cell_POIcat.csv"
    poi.write_text("x,y,POIcategory,POI_count\n2,2,0,3\n2,2,1,1\n2,3,1,4\n")
    cats = tmp_path / "POI_datacategories.csv"
    cats.write_text("﻿restaurant\nshop\n")  # one BOM-prefixed name per line
    wide = load_poi(poi, cats)
    assert wide["h3"].tolist() == ["2_2", "2_3"]
    assert set(wide.columns) == {"h3", "poi_restaurant", "poi_shop"}
    row = wide.set_index("h3").loc["2_2"]
    assert row["poi_restaurant"] == 3 and row["poi_shop"] == 1


def test_load_poi_fallback_when_name_count_mismatches(tmp_path):
    poi = tmp_path / "cell_POIcat.csv"
    poi.write_text("x,y,POIcategory,POI_count\n2,2,0,3\n2,2,1,1\n")
    cats = tmp_path / "POI_datacategories.csv"
    cats.write_text("only_one\n")
    wide = load_poi(poi, cats)
    assert set(wide.columns) == {"h3", "poi_cat_0", "poi_cat_1"}


def test_run_yjmob_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MIN_ACTIVE_DAYS", 3)
    monkeypatch.setattr(config, "MIN_DISTINCT_R8", 2)
    rows = []
    for day in range(4):  # user 11: 4 active days, 3 distinct cells -> in cohort
        for slot, (x, y) in zip((1, 5, 9), ((2, 2), (3, 3), (4, 4)), strict=True):
            rows.append((11, day, slot, x, y))
    for day in range(2):  # user 12: 2 days, 1 cell -> out
        rows.append((12, day, 1, 5, 5))
    raw = tmp_path / "ds.csv"
    raw.write_text("uid,d,t,x,y\n" + "\n".join(",".join(map(str, r)) for r in rows) + "\n")

    pdir = tmp_path / "out"
    run_yjmob(dataset="yjmob1", raw_file=raw, processed_dir=pdir)

    seq = pd.read_parquet(pdir / "seq_hourly.parquet")
    cells_df = pd.read_parquet(pdir / "cells_r8.parquet")
    q = pd.read_parquet(pdir / "seq_q.parquet")
    cohort = pd.read_parquet(pdir / "cohort.parquet")
    assert list(seq.columns) == ["user", "hour", "h3", "cell_idx"]
    assert seq["hour"].iloc[0] == EPOCH
    assert cohort["user"].tolist() == ["11"]
    assert set(q.columns) >= {"user", "n_hours", "n_known", "q"}
    assert len(cells_df) == 4  # (2,2), (3,3), (4,4), (5,5)
    assert not (pdir / "poi.parquet").exists()  # no POI file next to the synthetic csv
