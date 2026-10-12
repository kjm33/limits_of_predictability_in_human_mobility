import h3
import numpy as np
import pandas as pd
import pytest

from mobility import config
from mobility.baselines import (
    FrequencyPredictor,
    MarkovPredictor,
    TimeConditionedPredictor,
    distance_error_km,
    evaluate_hourly,
    evaluate_trip_destination,
    temporal_split,
    topk_accuracy,
    trip_destination_accuracy,
)

UNK = config.UNKNOWN

BASE_CELL = h3.latlng_to_cell(39.9, 116.4, 8)
RING = sorted(set(h3.grid_disk(BASE_CELL, 2)) - set(h3.grid_disk(BASE_CELL, 1)))  # 12 ring-2 cells


def cycle_frame(spec: dict[str, list[int]], n_hours: int) -> pd.DataFrame:
    """Deterministic hourly sequences: each user cycles through their cells."""
    frames = []
    for user, cyc in spec.items():
        vals = [cyc[i % len(cyc)] for i in range(n_hours)]
        hours = pd.date_range("2020-01-01", periods=n_hours, freq="h")
        frames.append(pd.DataFrame({"user": user, "hour": hours, "h3": None, "cell_idx": vals}))
    return pd.concat(frames, ignore_index=True)


def cells_frame(mapping: dict[int, str], with_latlon: bool = True) -> pd.DataFrame:
    """Cells table (cell_idx, h3, lat, lon) from real h3 strings."""
    rows = []
    for idx, cell in sorted(mapping.items()):
        la, lo = h3.cell_to_latlng(cell)
        rows.append({"cell_idx": idx, "h3": cell, "lat": la, "lon": lo})
    df = pd.DataFrame(rows)
    if not with_latlon:
        df = df.drop(columns=["lat", "lon"])
    return df


def test_temporal_split_per_user_ordering_and_disjointness():
    hours = pd.date_range("2020-01-01", periods=10, freq="h")
    df = pd.concat(
        [
            pd.DataFrame({"user": "A", "hour": hours, "cell_idx": np.arange(10)}),
            pd.DataFrame(
                {
                    "user": "B",
                    "hour": hours + pd.Timedelta(hours=5),
                    "cell_idx": -10 - np.arange(10),
                }
            ),
        ],
        ignore_index=True,
    ).sample(frac=1.0, random_state=0)  # shuffle input order
    train, test = temporal_split(df, test_frac=0.2)
    assert len(train) + len(test) == len(df)
    assert train.equals(train.sort_values(["user", "hour"]))  # chronologically sorted
    for user in ("A", "B"):
        tr = train.loc[train["user"] == user]
        te = test.loc[test["user"] == user]
        assert len(tr) == 8 and len(te) == 2  # ceil(0.8 * 10)
        assert tr["hour"].max() < te["hour"].min()  # train strictly precedes test
        assert not set(tr["hour"]) & set(te["hour"])  # disjoint
    # ceil rounding: 3 rows * 0.8 -> all 3 train, empty test
    small = pd.DataFrame({"user": "C", "hour": hours[:3], "cell_idx": [1, 2, 3]})
    tr3, te3 = temporal_split(small, test_frac=0.2)
    assert len(tr3) == 3 and len(te3) == 0


def test_frequency_predictor_user_and_global_fallback():
    seq = cycle_frame({"A": [10, 20, 30], "B": [40, 50]}, 12)
    p = FrequencyPredictor().fit(seq)
    assert p.predict("B") == 40  # 40/50 tie -> lowest cell_idx
    assert p.predict("ZZZ") == 40  # unseen user -> global top (tie 40/50 -> 40)
    assert p.predict_ranked("A", 3) == (10, 20, 30)  # 3-way tie -> ascending
    q = FrequencyPredictor().fit(seq.iloc[0:0])  # empty train -> UNK, no crash
    assert q.predict("A") == UNK


def test_markov_individual_backoff():
    seq = cycle_frame({"A": [10, 20, 30]}, 30)
    train, _ = temporal_split(seq, 0.2)
    p = MarkovPredictor(order=2, individual=True).fit(train)
    assert p.predict((10, 20), "A") == 30
    assert p.predict((20, 30), "A") == 10
    assert p.predict((30, 10, 20), "A") == 30  # longer context -> last order cells
    # unseen context at order 2 -> backoff to order 1 (also unseen) -> frequency
    assert p.predict((999, 999), "A") in (10, 20, 30)
    r = p.predict_ranked((999, 999), "A", 3)
    assert r[0] in (10, 20, 30) and len(r) == 3
    # UNKNOWN sentinel in context -> straight to frequency fallback
    assert p.predict((10, UNK), "A") in (10, 20, 30)
    assert p.predict((UNK,), "A") in (10, 20, 30)
    # unknown user -> frequency fallback (global top)
    assert p.predict((10, 20), "NOPE") in (10, 20, 30)


def test_markov_collective_pools_transitions():
    seq = cycle_frame({"A": [10, 20, 30], "B": [40, 50]}, 30)
    train, _ = temporal_split(seq, 0.2)
    p = MarkovPredictor(order=1, individual=False).fit(train)
    # pooled chain learned transitions from BOTH users
    assert p.predict((40,), user=None) == 50
    assert p.predict((50,), user="B") == 40
    assert p.predict((10,), user=None) == 20
    assert p.predict((20,), user="A") == 30
    # individual chain cannot answer for a foreign user's cell -> frequency
    p_ind = MarkovPredictor(order=1, individual=True).fit(train)
    assert p_ind.predict((40,), user="A") in (10, 20, 30)


def test_evaluate_hourly_deterministic_cycles():
    seq = cycle_frame({"A": [10, 20, 30], "B": [40, 50]}, 30)
    cells = cells_frame({10: BASE_CELL, 20: RING[0], 30: RING[1], 40: RING[2], 50: RING[3]})
    res = evaluate_hourly(seq, cells)
    assert set(res["predictor"]) == {
        "freq",
        "time",
        "markov1",
        "markov2",
        "markov3",
        "markov1_col",
        "markov2_col",
        "markov3_col",
    }
    assert list(res.columns) == ["predictor", "user", "n_eval", "top1", "top3", "dist_km"]
    m1a = res.loc[(res["predictor"] == "markov1") & (res["user"] == "A")].iloc[0]
    assert m1a["n_eval"] == 6  # ceil(24) train of 30 -> 6 test hours
    assert m1a["top1"] == 1.0  # perfect cycle + warm-start across the boundary
    assert m1a["top3"] == 1.0
    fq_a = res.loc[(res["predictor"] == "freq") & (res["user"] == "A")].iloc[0]
    assert fq_a["top1"] == pytest.approx(1 / 3)  # tie -> always predicts 10
    col_b = res.loc[(res["predictor"] == "markov1_col") & (res["user"] == "B")].iloc[0]
    assert col_b["top1"] == 1.0
    assert (res["top1"] >= 0).all() and (res["dist_km"] >= 0).all()
    assert np.isfinite(res["dist_km"]).all()


def test_evaluate_hourly_time_conditioned_beats_frequency():
    # 15 days so every hour-of-week bucket in the test tail was seen in training
    hours = pd.date_range("2020-01-01", periods=360, freq="h")
    vals = [10 if ts.hour % 2 == 0 else 20 for ts in hours]
    seq = pd.DataFrame({"user": "C", "hour": hours, "h3": None, "cell_idx": vals})
    cells = cells_frame({10: BASE_CELL, 20: RING[0]})
    res = evaluate_hourly(seq, cells)
    t = res.loc[res["predictor"] == "time"].iloc[0]
    f = res.loc[res["predictor"] == "freq"].iloc[0]
    assert t["top1"] == 1.0  # hour parity determines the cell
    assert f["top1"] == pytest.approx(0.5)  # tie -> always predicts 10
    assert t["top1"] > f["top1"]
    # direct predictor checks on seen buckets
    p = TimeConditionedPredictor().fit(seq)
    assert p.predict("C", pd.Timestamp("2020-01-01 04:00")) == 10  # even hour
    assert p.predict("C", pd.Timestamp("2020-01-01 05:00")) == 20  # odd hour
    # unseen bucket (train = 3 Wed hours only) backs off to overall frequency
    p_small = TimeConditionedPredictor().fit(seq.iloc[:3])
    assert p_small.predict("C", pd.Timestamp("2020-01-06 00:00")) == 10


def test_evaluate_hourly_excludes_unknown_targets():
    hours = pd.date_range("2020-01-01", periods=30, freq="h")
    vals = [40 if ts.hour % 2 == 0 else 50 for ts in hours]
    vals[26] = UNK  # two UNKNOWN targets inside the 6-hour test tail
    vals[27] = UNK
    seq = pd.DataFrame({"user": "D", "hour": hours, "h3": None, "cell_idx": vals})
    cells = cells_frame({40: BASE_CELL, 50: RING[0]})
    res = evaluate_hourly(seq, cells)
    m1 = res.loc[res["predictor"] == "markov1"].iloc[0]
    assert m1["n_eval"] == 4  # 6 test hours - 2 UNKNOWN targets
    assert m1["top1"] == 1.0  # known pairs remain perfectly predictable


def test_topk_accuracy_hand_checked():
    y = np.array([10, 20, 30])
    ranked = np.array([[10, 20, 30], [30, 20, 10], [20, 30, 10]])
    assert topk_accuracy(y, ranked, 1) == pytest.approx(1 / 3)  # only row 0
    assert topk_accuracy(y, ranked, 2) == pytest.approx(1.0)  # rank-2 catches rows 1-2
    assert topk_accuracy(y, ranked, 3) == pytest.approx(1.0)
    d: dict[int, float] = topk_accuracy(y, ranked, [1, 3])  # type: ignore[assignment]
    assert d[1] == pytest.approx(1 / 3) and d[3] == pytest.approx(1.0)
    empty: float = topk_accuracy(  # type: ignore[assignment]
        np.array([]), np.empty((0, 3), dtype=int), 1
    )
    assert np.isnan(empty)


def test_trip_destination_accuracy_metric():
    pred = np.array([1, 2, 3])
    true = np.array([1, 2, 2])
    assert trip_destination_accuracy(pred, true) == pytest.approx(2 / 3)
    assert np.isnan(trip_destination_accuracy(np.array([]), np.array([])))


def test_distance_error_km_monotone():
    base = h3.latlng_to_cell(39.9, 116.4, 8)
    near = sorted(set(h3.grid_disk(base, 1)) - {base})[0]
    far = sorted(set(h3.grid_disk(base, 4)) - set(h3.grid_disk(base, 3)))[0]
    cells = cells_frame({0: base, 1: near, 2: far})
    d = distance_error_km(np.array([0, 0, 0]), np.array([0, 1, 2]), cells)
    assert d[0] == pytest.approx(0.0)  # same cell -> zero
    assert 0 < d[1] < d[2] < 10  # farther cells -> strictly larger error
    # same result when coordinates must come from h3.cell_to_latlng
    cells_no_ll = cells_frame({0: base, 1: near, 2: far}, with_latlon=False)
    d2 = distance_error_km(np.array([0, 0, 0]), np.array([0, 1, 2]), cells_no_ll)
    np.testing.assert_allclose(d, d2)


def test_evaluate_trip_destination():
    cells = cells_frame({0: BASE_CELL, 1: RING[0], 2: RING[1], 3: RING[2]})
    h = {0: BASE_CELL, 1: RING[0], 2: RING[1], 3: RING[2]}
    rows = []
    t0 = pd.Timestamp("2020-03-01 08:00")
    for user, (a, b) in {"A": (0, 1), "B": (2, 3)}.items():
        for k in range(20):
            o, d = (a, b) if k % 2 == 0 else (b, a)
            rows.append(
                {
                    "user": user,
                    "depart": t0 + pd.Timedelta(hours=k),
                    "arrive": t0 + pd.Timedelta(hours=k, minutes=30),
                    "o_lat": 39.9,
                    "o_lon": 116.4,
                    "d_lat": 39.9,
                    "d_lon": 116.4,
                    "o_h3_r8": h[o],
                    "d_h3_r8": h[d],
                    "travel_min": 30.0,
                    "dist_km": 1.0,
                }
            )
    trips = pd.DataFrame(rows)
    res = evaluate_trip_destination(trips, cells)
    assert set(res["predictor"]) == {"trip_freq", "trip_markov"}
    assert list(res.columns) == ["predictor", "user", "n_eval", "top1", "top3", "dist_km"]
    mk = res.loc[(res["predictor"] == "trip_markov") & (res["user"] == "A")].iloc[0]
    assert mk["n_eval"] == 4  # ceil(16) train of 20 -> 4 test trips
    assert mk["top1"] == 1.0  # origin determines destination
    fq = res.loc[(res["predictor"] == "trip_freq") & (res["user"] == "A")].iloc[0]
    assert fq["top1"] == pytest.approx(0.5)  # dest tie -> always predicts cell 0
    assert fq["top3"] == 1.0
    assert (res["dist_km"] >= 0).all()
    # unmappable destination cells are excluded from scoring (index 19 = A's last trip)
    bad = trips.copy()
    bad.loc[19, "d_h3_r8"] = "unknown-cell"
    res_bad = evaluate_trip_destination(bad, cells)
    mk_bad = res_bad.loc[(res_bad["predictor"] == "trip_markov") & (res_bad["user"] == "A")].iloc[0]
    assert mk_bad["n_eval"] == 3
    mk_b = res_bad.loc[(res_bad["predictor"] == "trip_markov") & (res_bad["user"] == "B")].iloc[0]
    assert mk_b["n_eval"] == 4
