"""Check-in ingestion tests (Foursquare TSMC, SNAP Gowalla/Brightkite; synthetic)."""

import numpy as np
import pandas as pd

from mobility.checkins import (
    parse_foursquare_tsmc,
    parse_snap_checkins,
    qc_and_segment_users,
    run_checkins,
)
from mobility.ingest import qc_and_segment

BASE = pd.Timestamp("2012-04-03 00:00:00")


def _frame(rows: list[tuple[int, str, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["user", "ts", "lat", "lon"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def test_parse_foursquare_local_time(tmp_path):
    path = tmp_path / "fsq.txt"
    path.write_text(
        "1\t4b5e2d1ab2e4\t4bf58dd8d48988116d941735\tHome\t40.7\t-74.0\t-240"
        "\tTue Apr 03 18:00:09 +0000 2012\n"
        "2\t3ce52c\t4bf58dd8d4898811e0951735\tOffice\t35.7\t139.7\t540"
        "\tTue Apr 03 18:00:09 +0000 2012\n"
    )
    points, meta = parse_foursquare_tsmc(path)
    assert points["ts"].tolist() == [
        BASE + pd.Timedelta(hours=14, seconds=9),  # UTC 18:00:09 - 4h
        BASE + pd.Timedelta(hours=27, seconds=9),  # UTC 18:00:09 + 9h -> next day 03:00:09
    ]
    assert points["lat"].tolist() == [40.7, 35.7]
    assert meta["venue_id"].tolist() == ["4b5e2d1ab2e4", "3ce52c"]
    assert meta["venue_cat_name"].tolist() == ["Home", "Office"]
    assert (meta["ts"] == points["ts"]).all()


def test_parse_snap_checkins_utc_and_coerce(tmp_path):
    path = tmp_path / "snap.txt"
    path.write_text(
        "0\t2010-10-17T01:15:04Z\t39.7\t-104.9\t10\n"
        "1\t2010-10-18T23:55:27Z\tjunk\t-0.1\tdeadbeef\n"
    )
    points, meta = parse_snap_checkins(path)
    assert points["ts"].tolist() == [pd.Timestamp("2010-10-17 01:15:04"),
                                     pd.Timestamp("2010-10-18 23:55:27")]
    assert np.isnan(points["lat"].iloc[1])
    assert meta["loc_id"].tolist() == ["10", "deadbeef"]


def test_qc_parity_with_ingest_single_user():
    df = _frame(
        [
            (1, "2020-01-01 00:00:00", 39.0, 116.0),
            (1, "2020-01-01 00:10:00", 39.001, 116.001),
            (1, "2020-01-01 00:20:01", 39.002, 116.002),  # gap > 20 min -> new seg
            (1, "2020-01-01 00:30:00", 0.0, 0.0),  # invalid -> dropped
        ]
    )
    a = qc_and_segment(df)
    b = qc_and_segment_users(df)
    pd.testing.assert_frame_equal(
        a[["user", "ts", "lat", "lon", "seg_id"]], b[["user", "ts", "lat", "lon", "seg_id"]]
    )


def test_qc_segments_never_span_users():
    # same timestamps, teleporting distance: must not drop user 2's first point
    df = _frame(
        [
            (1, "2020-01-01 00:00:00", 39.0, 116.0),
            (2, "2020-01-01 00:00:00", -33.9, 151.2),  # ~9000 km away, same instant
            (2, "2020-01-01 00:05:00", -33.9, 151.2),
        ]
    )
    out = qc_and_segment_users(df)
    assert len(out) == 3
    assert out["seg_id"].tolist() == [0, 1, 1]
    assert out["user"].tolist() == [1, 2, 2]


def test_qc_drops_impossible_speed_within_segment():
    df = _frame(
        [
            (1, "2020-01-01 00:00:00", 39.0, 116.0),
            (1, "2020-01-01 00:01:00", 40.5, 116.0),  # ~167 km in 60 s -> dropped
            (1, "2020-01-01 00:02:00", 40.501, 116.0),  # fine relative to prior point
        ]
    )
    out = qc_and_segment_users(df)
    assert len(out) == 2
    assert out["lat"].tolist() == [39.0, 40.501]


def test_run_checkins_end_to_end(tmp_path):
    path = tmp_path / "checkins.txt"
    path.write_text(
        "0\t2010-10-17T01:15:04Z\t39.7\t-104.9\t10\n"
        "0\t2010-10-17T02:15:04Z\tjunk\t-104.9\t11\n"  # junk lat -> dropped everywhere
        "0\t2010-10-18T09:00:00Z\t39.7\t-104.9\t12\n"
        "1\t2010-10-18T09:00:00Z\t40.7\t-74.0\t13\n"
    )
    pdir = tmp_path / "out"
    out = run_checkins(dataset="gowalla", raw_file=path, processed_dir=pdir)

    points = pd.read_parquet(pdir / "points.parquet")
    meta = pd.read_parquet(pdir / "checkins_meta.parquet")
    assert list(points.columns) == ["user", "ts", "lat", "lon", "alt_m", "seg_id", "mode"]
    assert points["user"].tolist() == ["0", "0", "1"]
    assert points["alt_m"].isna().all() and points["mode"].isna().all()
    assert points["seg_id"].tolist() == [0, 1, 2]  # gap break + user break
    assert meta["loc_id"].tolist() == ["10", "12", "13"]
    assert len(meta) == len(points)
    assert out == pdir / "points.parquet"
