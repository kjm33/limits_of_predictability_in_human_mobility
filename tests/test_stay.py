"""Unit tests for stay detection, trips, and stop-level H3 mapping (synthetic traces)."""

import h3
import numpy as np
import pandas as pd
import pytest

from mobility import config
from mobility.ingest import haversine_m
from mobility.stay import (
    build_trips,
    detect_stays,
    detect_stays_segment,
    stops_with_h3,
    time_bin,
)

STOP_COLS = ["user", "arrive", "depart", "lat", "lon", "dwell_min", "n_bins"]


def stationary_points(user, seg_id, start, n, lat, lon, step_s=60):
    ts = pd.date_range(start, periods=n, freq=pd.Timedelta(seconds=step_s))
    return pd.DataFrame({"user": user, "ts": ts, "lat": lat, "lon": lon, "seg_id": seg_id})


# ---------------------------------------------------------------- time_bin


def test_time_bin_median_bins():
    t0 = pd.Timestamp("2020-01-01 08:00:00")
    ts = pd.Series([t0 + pd.Timedelta(seconds=30 * k) for k in range(10)])  # 5 min @ 30 s
    lats = 39.90 + np.arange(10) * 0.0001
    lons = 116.40 + np.arange(10) * 0.0001
    pts = pd.DataFrame({"user": "000", "seg_id": 0, "ts": ts, "lat": lats, "lon": lons})

    out = time_bin(pts)
    assert len(out) == 5  # two points per one-minute bin
    assert list(out.columns) == ["user", "seg_id", "ts", "lat", "lon"]
    assert out["ts"].iloc[0] == t0
    assert out["ts"].iloc[-1] == t0 + pd.Timedelta(minutes=4)
    np.testing.assert_allclose(out["lat"].values, lats.reshape(5, 2).mean(axis=1), rtol=0)
    np.testing.assert_allclose(out["lon"].values, lons.reshape(5, 2).mean(axis=1), rtol=0)


def test_time_bin_separate_segments():
    a = stationary_points("000", 0, "2020-01-01 08:00:00", 3, 39.9, 116.4)
    b = stationary_points("000", 1, "2020-01-01 08:00:00", 2, 40.0, 116.5)
    out = time_bin(pd.concat([a, b], ignore_index=True))
    assert len(out) == 5  # same wall-clock bins kept separate per seg_id


# ------------------------------------------------- detect_stays_segment


def test_segment_stationary_15min_is_one_stay():
    ts = np.arange(16) * 60  # 16 one-minute bins -> 15 min span
    stays = detect_stays_segment(ts, np.full(16, 39.9), np.full(16, 116.4), 250.0, 10.0)
    assert len(stays) == 1
    s = stays[0]
    assert s["arrive"] == 0
    assert s["depart"] == 15 * 60
    assert s["n_bins"] == 16
    assert s["lat"] == pytest.approx(39.9)
    assert s["lon"] == pytest.approx(116.4)


def test_segment_5min_cluster_not_a_stay():
    ts = np.arange(6) * 60  # 5 min span < 10 min minimum
    stays = detect_stays_segment(ts, np.full(6, 39.9), np.full(6, 116.4), 250.0, 10.0)
    assert stays == []


def test_segment_two_clusters_2km_apart():
    # two 15-min stationary clusters ~2 km apart (0.018 deg lat), 10 min apart in time
    ts = np.concatenate([np.arange(16) * 60, 1500 + np.arange(16) * 60])
    lat = np.concatenate([np.full(16, 39.9), np.full(16, 39.918)])
    lon = np.full(32, 116.4)
    stays = detect_stays_segment(ts, lat, lon, 250.0, 10.0)
    assert len(stays) == 2
    assert stays[0]["arrive"] == 0 and stays[0]["depart"] == 900
    assert stays[1]["arrive"] == 1500 and stays[1]["depart"] == 2400
    assert stays[1]["lat"] == pytest.approx(39.918)


def test_segment_continuous_motion_no_stays():
    # walking ~120 m/min due north for an hour: never within-250m for >= 10 min
    ts = np.arange(60) * 60
    lat = 39.9 + np.arange(60) * (120.0 / 111_320.0)
    lon = np.full(60, 116.4)
    stays = detect_stays_segment(ts, lat, lon, 250.0, 10.0)
    assert stays == []


# --------------------------------------------------------- detect_stays


def test_detect_stays_two_blocks_two_stops():
    # stationary 20 min (seg 0) + 30 min gap + stationary 20 min 5 km away (seg 1)
    t0 = pd.Timestamp("2020-01-01 08:00:00")
    pts = pd.concat(
        [
            stationary_points("000", 0, t0, 21, 39.90, 116.40),
            stationary_points("000", 1, t0 + pd.Timedelta(minutes=50), 21, 39.95, 116.40),
        ],
        ignore_index=True,
    )
    stops = detect_stays(pts)
    assert list(stops.columns) == STOP_COLS
    assert len(stops) == 2
    assert stops["dwell_min"].tolist() == [20.0, 20.0]
    assert stops["n_bins"].tolist() == [21, 21]
    assert stops["arrive"].iloc[0] == t0
    assert stops["depart"].iloc[0] == t0 + pd.Timedelta(minutes=20)
    assert stops["arrive"].iloc[1] == t0 + pd.Timedelta(minutes=50)
    assert stops["depart"].iloc[1] == t0 + pd.Timedelta(minutes=70)
    assert stops["lat"].iloc[1] == pytest.approx(39.95)


def test_detect_stays_merges_consecutive_nearby():
    # two stays 100 m apart, 10 min apart (separate segments) -> merged into one stop
    t0 = pd.Timestamp("2020-01-01 08:00:00")
    pts = pd.concat(
        [
            stationary_points("000", 0, t0, 16, 39.90, 116.40),  # 08:00..08:15
            stationary_points("000", 1, t0 + pd.Timedelta(minutes=25), 16, 39.9009, 116.40),
        ],
        ignore_index=True,
    )
    stops = detect_stays(pts)
    assert len(stops) == 1
    assert stops["arrive"].iloc[0] == t0
    assert stops["depart"].iloc[0] == t0 + pd.Timedelta(minutes=40)
    assert stops["dwell_min"].iloc[0] == pytest.approx(40.0)
    # centroid of the merged stop stays at the first stay
    assert stops["lat"].iloc[0] == pytest.approx(39.90)


def test_detect_stays_does_not_merge_across_long_gaps():
    # same geometry as the merge test, but a 30-min gap (> SEGMENT_GAP_MIN) between
    # the two stays: the user may have left and returned, so no merge
    t0 = pd.Timestamp("2020-01-01 08:00:00")
    pts = pd.concat(
        [
            stationary_points("000", 0, t0, 16, 39.90, 116.40),  # departs 08:15
            stationary_points("000", 1, t0 + pd.Timedelta(minutes=45), 16, 39.9009, 116.40),
        ],
        ignore_index=True,
    )
    stops = detect_stays(pts)
    assert len(stops) == 2
    assert stops["dwell_min"].tolist() == [15.0, 15.0]


def test_detect_stays_keeps_users_separate():
    t0 = pd.Timestamp("2020-01-01 08:00:00")
    pts = pd.concat(
        [
            stationary_points("000", 0, t0, 21, 39.90, 116.40),
            stationary_points("001", 0, t0, 21, 39.9009, 116.40),  # 100 m from user 000
        ],
        ignore_index=True,
    )
    stops = detect_stays(pts)
    assert len(stops) == 2
    assert sorted(stops["user"].tolist()) == ["000", "001"]


def test_detect_stays_empty():
    pts = pd.DataFrame(columns=["user", "ts", "lat", "lon", "seg_id"])
    stops = detect_stays(pts)
    assert len(stops) == 0
    assert "dwell_min" in stops.columns


# ---------------------------------------------------------- build_trips


def test_build_trips_two_trips_three_stops():
    stops = pd.DataFrame(
        {
            "user": ["000", "000", "000", "001"],
            "arrive": pd.to_datetime(
                ["2020-01-01 08:00", "2020-01-01 08:30", "2020-01-01 09:00", "2020-01-01 08:10"]
            ),
            "depart": pd.to_datetime(
                ["2020-01-01 08:20", "2020-01-01 08:50", "2020-01-01 09:20", "2020-01-01 08:40"]
            ),
            "lat": [39.90, 39.91, 39.92, 30.00],
            "lon": [116.40, 116.40, 116.40, 110.00],
            "dwell_min": [20.0, 20.0, 20.0, 30.0],
        }
    )
    trips = build_trips(stops)
    assert list(trips.columns) == [
        "user",
        "depart",
        "arrive",
        "o_lat",
        "o_lon",
        "d_lat",
        "d_lon",
        "o_h3_r8",
        "d_h3_r8",
        "travel_min",
        "dist_km",
    ]
    assert len(trips) == 2  # 3 stops of user 000; user 001 never pairs across users
    t1, t2 = trips.iloc[0], trips.iloc[1]
    assert (trips["user"] == "000").all()
    assert t1["depart"] == pd.Timestamp("2020-01-01 08:20")
    assert t1["arrive"] == pd.Timestamp("2020-01-01 08:30")
    assert t1["travel_min"] == pytest.approx(10.0)
    assert t2["travel_min"] == pytest.approx(10.0)
    exp_km = (
        haversine_m(np.array([39.90]), np.array([116.40]), np.array([39.91]), np.array([116.40]))[0]
        / 1000
    )
    assert t1["dist_km"] == pytest.approx(exp_km)
    assert 1.0 < t1["dist_km"] < 1.3  # 0.01 deg lat ~ 1.11 km
    assert t1["o_lat"] == pytest.approx(39.90) and t1["d_lat"] == pytest.approx(39.91)
    assert t1["o_h3_r8"] is None and t1["d_h3_r8"] is None  # h3 not attached yet


def test_build_trips_uses_h3_when_attached():
    stops = pd.DataFrame(
        {
            "user": ["000", "000"],
            "arrive": pd.to_datetime(["2020-01-01 08:00", "2020-01-01 09:00"]),
            "depart": pd.to_datetime(["2020-01-01 08:20", "2020-01-01 09:20"]),
            "lat": [39.9042, 39.9500],
            "lon": [116.4074, 116.4074],
            "dwell_min": [20.0, 20.0],
        }
    )
    trips = build_trips(stops_with_h3(stops))
    assert len(trips) == 1
    assert trips["o_h3_r8"].iloc[0] == h3.latlng_to_cell(39.9042, 116.4074, 8)
    assert trips["d_h3_r8"].iloc[0] == h3.latlng_to_cell(39.95, 116.4074, 8)


# -------------------------------------------------------- stops_with_h3


def test_stops_with_h3_parent_chain():
    stops = pd.DataFrame(
        {
            "user": ["000"],
            "arrive": [pd.Timestamp("2020-01-01 08:00")],
            "depart": [pd.Timestamp("2020-01-01 08:20")],
            "lat": [39.9042],
            "lon": [116.4074],
            "dwell_min": [20.0],
            "n_bins": [21],
        }
    )
    out = stops_with_h3(stops)
    r9 = out["h3_r9"].iloc[0]
    r8, r7, r6 = out["h3_r8"].iloc[0], out["h3_r7"].iloc[0], out["h3_r6"].iloc[0]
    assert h3.get_resolution(r9) == config.H3_STOP_RES
    assert r8 == h3.latlng_to_cell(39.9042, 116.4074, config.H3_PRIMARY_RES)
    assert h3.cell_to_parent(r9, 8) == r8
    assert h3.cell_to_parent(r9, config.H3_CORRIDOR_RES) == r7
    assert h3.cell_to_parent(r9, config.H3_COARSE_RES) == r6
    assert h3.cell_to_parent(r8, 7) == r7 and h3.cell_to_parent(r7, 6) == r6


def test_stops_with_h3_empty():
    stops = pd.DataFrame(columns=STOP_COLS)
    out = stops_with_h3(stops)
    assert len(out) == 0
    assert {"h3_r9", "h3_r8", "h3_r7", "h3_r6"} <= set(out.columns)
