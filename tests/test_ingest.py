import numpy as np
import pandas as pd

from mobility.ingest import assign_modes, haversine_m, parse_plt, qc_and_segment

PLT_BODY = """Geolife trajectory
WGS 84
Altitude is in Feet
Reserved 3
0,2,255,My Track,0,0,2,8421376
0
39.984702,116.318417,0,492,39744.1201851852,2008-10-23,02:53:04
39.984683,116.318450,0,492,39744.1202546296,2008-10-23,02:53:10
39.984686,116.318417,0,492,39744.1203125,2008-10-23,02:53:15
"""


def test_parse_plt(tmp_path):
    p = tmp_path / "20081023025304.plt"
    p.write_text(PLT_BODY)
    df = parse_plt(p)
    assert len(df) == 3
    assert list(df.columns) == ["ts", "lat", "lon", "alt_m"]
    assert df["ts"].iloc[0] == pd.Timestamp("2008-10-23 02:53:04")
    assert abs(df["alt_m"].iloc[0] - 492 * 0.3048) < 1e-6
    assert abs(df["lat"].iloc[0] - 39.984702) < 1e-9


def test_haversine():
    # Beijing (39.9, 116.4) to Beijing center ~ 11.3 km east-west
    d = haversine_m(np.array([39.9]), np.array([116.4]), np.array([39.9]), np.array([116.5]))
    assert 8_000 < d[0] < 10_000
    # zero distance
    d0 = haversine_m(np.array([39.9]), np.array([116.4]), np.array([39.9]), np.array([116.4]))
    assert d0[0] == 0.0


def test_assign_modes():
    ts = pd.Series(pd.to_datetime(["2020-01-01 00:00", "2020-01-01 01:00", "2020-01-03 05:00"]))
    labels = pd.DataFrame(
        {
            "start": pd.to_datetime(["2020-01-01 00:30", "2020-01-03 00:00"]),
            "end": pd.to_datetime(["2020-01-01 02:00", "2020-01-03 10:00"]),
            "mode": ["walk", "taxi"],
        }
    )
    out = assign_modes(ts, labels)
    assert out[0] is None
    assert out[1] == "walk"
    assert out[2] == "taxi"
    assert (assign_modes(ts, None) == None).all()  # noqa: E711


def test_qc_segmentation_speed_drop():
    rows = []
    # 20-min gap -> segment split; then a teleport (impossible speed) -> dropped
    base = pd.Timestamp("2020-01-01 00:00")
    for k in range(3):
        rows.append((base + pd.Timedelta(seconds=5 * k), 39.9, 116.4, 10.0))
    for k in range(3):
        t = base + pd.Timedelta(minutes=25) + pd.Timedelta(seconds=5 * k)
        rows.append((t, 39.9, 116.4, 10.0))
    # teleport within segment 2
    rows.append((base + pd.Timedelta(minutes=25, seconds=20), 45.0, 130.0, 10.0))
    df = pd.DataFrame(rows, columns=["ts", "lat", "lon", "alt_m"])
    out = qc_and_segment(df)
    assert len(out) == 6  # teleport dropped
    assert out["seg_id"].nunique() == 2
    assert out["seg_id"].tolist() == [0, 0, 0, 1, 1, 1]


def test_qc_invalid_coords():
    rows = [
        (pd.Timestamp("2020-01-01 00:00"), 0.0, 0.0, 0.0),  # null island
        (pd.Timestamp("2020-01-01 00:05"), 39.9, 116.4, 0.0),
        (pd.Timestamp("2020-01-01 00:10"), 120.0, 116.4, 0.0),  # invalid lat
    ]
    df = pd.DataFrame(rows, columns=["ts", "lat", "lon", "alt_m"])
    out = qc_and_segment(df)
    assert len(out) == 1
    assert out["lat"].iloc[0] == 39.9
