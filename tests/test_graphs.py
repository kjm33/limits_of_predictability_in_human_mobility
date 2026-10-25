"""Synthetic-data tests for mobility.graphs (no real parquet reads)."""

from collections import Counter

import h3
import networkx as nx
import pandas as pd
import pytest

from mobility import config
from mobility.graphs import (
    RW_COLUMNS,
    RandomWalkPredictor,
    build_all_graphs,
    build_global_graph,
    build_user_graph,
    evaluate_random_walk,
    graph_analytics,
    infer_home_work,
)

A = h3.latlng_to_cell(39.9847, 116.3184, config.H3_PRIMARY_RES)
B = h3.latlng_to_cell(40.0000, 116.5000, config.H3_PRIMARY_RES)
C = h3.latlng_to_cell(39.9000, 116.3000, config.H3_PRIMARY_RES)
D = h3.latlng_to_cell(39.5000, 116.0000, config.H3_PRIMARY_RES)


def _stop(user: str, lat: float, lon: float, arrive: str, depart: str) -> dict:
    t0, t1 = pd.Timestamp(arrive), pd.Timestamp(depart)
    cell = h3.latlng_to_cell(lat, lon, config.H3_PRIMARY_RES)
    return {
        "user": user,
        "arrive": t0,
        "depart": t1,
        "lat": lat,
        "lon": lon,
        "dwell_min": (t1 - t0).total_seconds() / 60,
        "n_bins": int((t1 - t0).total_seconds() // 60),
        "h3_r9": h3.latlng_to_cell(lat, lon, config.H3_STOP_RES),
        "h3_r8": cell,
        "h3_r7": h3.cell_to_parent(cell, config.H3_CORRIDOR_RES),
        "h3_r6": h3.cell_to_parent(cell, config.H3_COARSE_RES),
    }


def _trip(user: str, o: str, d: str, depart: str, travel_min: float = 10.0) -> dict:
    depart = pd.Timestamp(depart)
    return {
        "user": user,
        "depart": depart,
        "arrive": depart + pd.Timedelta(minutes=30),
        "o_h3_r8": o,
        "d_h3_r8": d,
        "travel_min": travel_min,
    }


def _u1_stops() -> pd.DataFrame:
    return pd.DataFrame([
        _stop("u1", 39.9847, 116.3184, "2020-01-06 01:00", "2020-01-06 07:00"),  # Mon night @ A
        _stop("u1", 40.0000, 116.5000, "2020-01-08 09:00", "2020-01-08 17:00"),  # Wed 9-17 @ B
        _stop("u1", 39.9000, 116.3000, "2020-01-11 12:00", "2020-01-11 13:00"),  # Sat noon @ C
    ])


def _u1_trips() -> pd.DataFrame:
    return pd.DataFrame([
        _trip("u1", A, B, "2020-01-06 08:00", 20.0),
        _trip("u1", A, B, "2020-01-07 09:00", 22.0),
        _trip("u1", A, B, "2020-01-08 10:00", 24.0),
        _trip("u1", B, C, "2020-01-08 17:30", 15.0),
        _trip("u1", B, C, "2020-01-09 18:00", 25.0),
        _trip("u1", C, A, "2020-01-10 20:00", 30.0),
    ])


def _seq_frame(per_user_seq: dict[str, list[str | None]]) -> pd.DataFrame:
    """seq_hourly frame; None entries are UNKNOWN hours (cell_idx = -1)."""
    known = sorted({c for seq in per_user_seq.values() for c in seq if c is not None})
    idx = {c: i for i, c in enumerate(known)}
    rows = []
    for user, seq in per_user_seq.items():
        for k, c in enumerate(seq):
            rows.append({
                "user": user,
                "hour": pd.Timestamp("2020-01-06 00:00") + pd.Timedelta(hours=k),
                "h3": c,
                "cell_idx": config.UNKNOWN if c is None else idx[c],
            })
    return pd.DataFrame(rows)


def test_build_user_graph_structure():
    g = build_user_graph(_u1_stops(), _u1_trips(), "u1")
    assert set(g.nodes) == {A, B, C}
    assert g[A][B]["count"] == 3
    assert g[B][C]["count"] == 2
    assert g[C][A]["count"] == 1
    assert g[A][B]["travel_min_mean"] == pytest.approx(22.0)
    assert g[B][C]["travel_min_mean"] == pytest.approx(20.0)
    assert g[C][A]["travel_min_mean"] == pytest.approx(30.0)


def test_build_user_graph_hour_hist():
    g = build_user_graph(_u1_stops(), _u1_trips(), "u1")
    hist_ab = [int(x) for x in g[A][B]["hour_hist"].split(",")]
    assert len(hist_ab) == 24
    assert sum(hist_ab) == 3
    assert hist_ab[8] == 1 and hist_ab[9] == 1 and hist_ab[10] == 1
    for _u, _v, d in g.edges(data=True):
        assert sum(int(x) for x in d["hour_hist"].split(",")) == d["count"]
    assert [int(x) for x in g[B][C]["hour_hist"].split(",")][17:19] == [1, 1]


def test_build_user_graph_dwell_attrs():
    g = build_user_graph(_u1_stops(), _u1_trips(), "u1")
    na, nb, nc = g.nodes[A], g.nodes[B], g.nodes[C]
    assert na["n_stops"] == 1 and nb["n_stops"] == 1 and nc["n_stops"] == 1
    assert na["total_dwell_min"] == pytest.approx(360.0)
    assert na["mean_arrive_hour"] == pytest.approx(1.0)
    assert na["night_dwell_min"] == pytest.approx(360.0)
    assert na["work_dwell_min"] == pytest.approx(0.0)
    assert nb["mean_arrive_hour"] == pytest.approx(9.0)
    assert nb["work_dwell_min"] == pytest.approx(480.0)
    assert nb["night_dwell_min"] == pytest.approx(0.0)
    assert nc["mean_arrive_hour"] == pytest.approx(12.0)
    assert nc["work_dwell_min"] == pytest.approx(0.0)
    # trip-only cell: centroid attrs, zero dwell, -1 sentinel arrive hour
    x = h3.latlng_to_cell(39.5000, 116.0000, config.H3_PRIMARY_RES)
    stops = pd.DataFrame([_stop("u1", 39.9847, 116.3184, "2020-01-06 01:00", "2020-01-06 02:00")])
    trips = pd.DataFrame([_trip("u1", x, A, "2020-01-06 08:00")])
    g2 = build_user_graph(stops, trips, "u1")
    assert x in g2.nodes and g2.nodes[x]["n_stops"] == 0
    assert g2.nodes[x]["mean_arrive_hour"] == -1.0
    assert g2[x][A]["count"] == 1


def test_infer_home_work():
    hw = infer_home_work(build_user_graph(_u1_stops(), _u1_trips(), "u1"))
    assert hw["home"] == A  # big night dwell
    assert hw["work"] == B  # weekday 9-17 dwell
    # no positive evidence -> None
    g2 = nx.DiGraph()
    g2.add_node(A, night_dwell_min=0.0, work_dwell_min=0.0)
    assert infer_home_work(g2) == {"home": None, "work": None}
    assert infer_home_work(nx.DiGraph()) == {"home": None, "work": None}


def test_graph_analytics():
    a = graph_analytics(build_user_graph(_u1_stops(), _u1_trips(), "u1"))
    assert a["n_nodes"] == 3 and a["n_edges"] == 3
    assert a["density"] == pytest.approx(0.5)
    assert a["top_pagerank"] in {A, B, C}
    assert a["top_betweenness"] in {A, B, C}
    assert 1 <= a["n_communities"] <= 3
    assert 0.0 <= a["mean_clustering"] <= 1.0
    empty = graph_analytics(nx.DiGraph())
    assert empty["n_nodes"] == 0 and empty["density"] == 0.0 and empty["n_communities"] == 0


def test_build_all_graphs_and_global(tmp_path):
    stops = pd.concat([
        _u1_stops(),
        pd.DataFrame([_stop("u2", 39.9000, 116.3000, "2020-01-12 10:00", "2020-01-12 11:00")]),
    ])
    trips = pd.concat([_u1_trips(), pd.DataFrame([_trip("u2", C, A, "2020-01-12 12:00")])])
    graphs = build_all_graphs(stops, trips)
    assert set(graphs) == {"u1", "u2"}
    graphs = build_all_graphs(stops, trips, out_dir=tmp_path)
    assert (tmp_path / "u1.graphml").exists()
    assert (tmp_path / "u2.graphml").exists()
    g = build_global_graph(trips)
    assert set(g.nodes) == {A, B, C}
    assert g[A][B]["count"] == 3  # pooled across users
    assert g[C][A]["count"] == 2
    assert build_global_graph(trips.iloc[0:0]).number_of_nodes() == 0


def test_random_walk_predictor_chain():
    trips = pd.DataFrame([
        _trip("u1", A, B, "2020-01-06 08:00"),
        _trip("u1", B, C, "2020-01-06 09:00"),
        _trip("u1", C, A, "2020-01-06 10:00"),
    ])
    pred = RandomWalkPredictor.fit(trips)
    pp = pred.predict_proba("u1", A)
    # mixture: (1 - t) * 1 + t * (1/3)
    assert pp[B] == pytest.approx(1 - 0.15 + 0.15 / 3)
    assert sum(pp.values()) == pytest.approx(1.0)
    assert pred.predict("u1", A) == B
    assert pred.predict("u1", B) == C
    assert pred.predict("u1", C) == A
    top3 = sorted(pp, key=lambda c: (-pp[c], c))[:3]
    assert B in top3


def test_random_walk_predictor_fallbacks():
    pred = RandomWalkPredictor(
        transitions={"u1": {A: Counter({B: 3})}},
        user_freq={"u1": Counter({A: 1, B: 5, C: 2})},
    )
    # unseen current cell -> user marginal (B dominates)
    assert pred.predict("u1", "not-a-cell") == B
    # unseen user -> global marginal (same single-user counter here)
    assert pred.predict("ghost", A) == B
    # mixture probabilities: P(B|A) = 0.85 * 1 + 0.15 * 5/8
    pp = pred.predict_proba("u1", A)
    assert pp[B] == pytest.approx(0.85 + 0.15 * 5 / 8)
    # exclude removes the dominant option
    assert pred.predict("u1", A, exclude={B}) in {A, C}
    # nothing known at all
    assert RandomWalkPredictor({}, {}).predict("u1", A) is None
    assert RandomWalkPredictor({}, {}).predict_proba("u1", A) == {}


def test_graphml_roundtrip(tmp_path):
    g = build_user_graph(_u1_stops(), _u1_trips(), "u1")
    path = tmp_path / "u1.graphml"
    nx.write_graphml(g, path)
    g2 = nx.read_graphml(path)
    assert set(g2.nodes) == {A, B, C}
    assert g2[A][B]["hour_hist"] == g[A][B]["hour_hist"]
    for u, v, d in g.edges(data=True):
        assert int(g2[u][v]["count"]) == d["count"]  # cast back after roundtrip
        assert g2[u][v]["travel_min_mean"] == pytest.approx(d["travel_min_mean"])
    assert int(g2.nodes[A]["n_stops"]) == 1
    assert g2.nodes[A]["total_dwell_min"] == pytest.approx(360.0)
    assert float(g2.nodes[B]["work_dwell_min"]) == pytest.approx(480.0)


def test_evaluate_random_walk():
    t0 = pd.Timestamp("2020-01-06 08:00")
    rows = [_trip("u1", o, d, t0 + pd.Timedelta(hours=k)) for k, (o, d) in
            enumerate([(A, B), (B, A), (A, B), (B, A), (A, B)])]
    rows += [_trip("u2", o, d, t0 + pd.Timedelta(hours=k)) for k, (o, d) in
             enumerate([(A, B), (A, B), (A, B), (A, B), (A, B), (C, D)])]
    trips = pd.DataFrame(rows)
    seq = _seq_frame({"u1": [A, B, A, B, A], "u2": [A, B, None, A, B]})
    df = evaluate_random_walk(trips, seq, cells=None, test_frac=0.2)
    assert set(df["method"]) == {"rw_trip_dest", "rw_hourly_seq"}

    def _row(user, method):
        return df[(df["user"] == user) & (df["method"] == method)].iloc[0]

    # u1: 5 trips -> train 4 (A->B, B->A x2), test A->B predicted from A: hit, dist 0
    r = _row("u1", "rw_trip_dest")
    assert r["n_eval"] == 1
    assert r["top1_acc"] == pytest.approx(1.0) and r["top3_acc"] == pytest.approx(1.0)
    assert r["dist_err_km"] == pytest.approx(0.0, abs=1e-9)
    # u1 hourly tail: known [A,B,A,B,A], held-out pair (B, A); B->A seen x2: hit
    r = _row("u1", "rw_hourly_seq")
    assert r["n_eval"] == 1 and r["top1_acc"] == pytest.approx(1.0)
    assert r["dist_err_km"] == pytest.approx(0.0, abs=1e-9)
    # u2: 6 trips -> train 4 (A->B x4), test A->B (hit) + C->D (origin unseen ->
    # marginal B, miss); hourly tail drops UNKNOWN -> known [A,B,A,B], pair (A, B): hit
    r = _row("u2", "rw_trip_dest")
    assert r["n_eval"] == 2
    assert r["top1_acc"] == pytest.approx(0.5) and r["top3_acc"] == pytest.approx(0.5)
    assert r["dist_err_km"] > 0.0
    r = _row("u2", "rw_hourly_seq")
    assert r["n_eval"] == 1 and r["top1_acc"] == pytest.approx(1.0)
    assert (df["top3_acc"] >= df["top1_acc"]).all()

    # candidate restriction keeps the same hand-computed outcome
    df2 = evaluate_random_walk(trips, seq, cells=[A, B], test_frac=0.2)
    r2 = df2[(df2["user"] == "u2") & (df2["method"] == "rw_trip_dest")].iloc[0]
    assert r2["n_eval"] == 2 and r2["top1_acc"] == pytest.approx(0.5)


def test_evaluate_random_walk_empty():
    out = evaluate_random_walk(pd.DataFrame(columns=["user", "depart", "o_h3_r8", "d_h3_r8"]),
                               _seq_frame({"u1": [A, B]}))
    assert out.empty
    assert list(out.columns) == ["user", "method", "n_eval", "top1_acc", "top3_acc", "dist_err_km"]


def test_evaluate_random_walk_skips_seq_only_users():
    t0 = pd.Timestamp("2020-01-06 08:00")
    trips = pd.DataFrame([
        _trip("u1", A, B, t0),
        _trip("u1", A, B, t0 + pd.Timedelta(hours=1)),
        _trip("u2", A, B, t0),
        _trip("u2", B, A, t0 + pd.Timedelta(hours=1)),
        _trip("u2", A, B, t0 + pd.Timedelta(hours=2)),
    ])
    # seq-only users on both sides of the sort order exercise the merge-join advance
    seq = _seq_frame({"a0": [A, B], "u2": [A, B, A, B], "u9": [A, B]})
    df = evaluate_random_walk(trips, seq, test_frac=0.2)
    assert list(df.columns) == RW_COLUMNS
    assert set(df["user"]) == {"u1", "u2"}  # seq-only a0 / u9 absent from output
    assert df.equals(df.sort_values(["user", "method"]).reset_index(drop=True))
    # trips-only user: rw_trip_dest only, no hourly-seq row
    assert set(df[df["user"] == "u1"]["method"]) == {"rw_trip_dest"}
    assert set(df[df["user"] == "u2"]["method"]) == {"rw_trip_dest", "rw_hourly_seq"}


def test_evaluate_random_walk_per_user_independent():
    t0 = pd.Timestamp("2020-01-06 08:00")
    u1_trips = pd.DataFrame([
        _trip("u1", A, B, t0),
        _trip("u1", A, B, t0 + pd.Timedelta(hours=1)),
        _trip("u1", B, A, t0 + pd.Timedelta(hours=2)),
        _trip("u1", A, B, t0 + pd.Timedelta(hours=3)),
    ])
    u2_trips = pd.DataFrame([
        _trip("u2", B, C, t0),
        _trip("u2", B, C, t0 + pd.Timedelta(hours=1)),
        _trip("u2", C, B, t0 + pd.Timedelta(hours=2)),
    ])
    u1_seq = _seq_frame({"u1": [A, B, A, B]})
    u2_seq = _seq_frame({"u2": [B, C, B, C, B]})
    # u2 frames concatenated before u1: results must not depend on iteration order
    both = evaluate_random_walk(
        pd.concat([u2_trips, u1_trips]), pd.concat([u2_seq, u1_seq]), test_frac=0.2
    )
    only_u1 = evaluate_random_walk(u1_trips, u1_seq, test_frac=0.2)
    only_u2 = evaluate_random_walk(u2_trips, u2_seq, test_frac=0.2)

    def _user_rows(df: pd.DataFrame, user: str) -> pd.DataFrame:
        return df[df["user"] == user].sort_values("method").reset_index(drop=True)

    pd.testing.assert_frame_equal(_user_rows(both, "u1"), _user_rows(only_u1, "u1"))
    pd.testing.assert_frame_equal(_user_rows(both, "u2"), _user_rows(only_u2, "u2"))
    assert set(_user_rows(both, "u1")["method"]) == {"rw_trip_dest", "rw_hourly_seq"}
    assert set(_user_rows(both, "u2")["method"]) == {"rw_trip_dest", "rw_hourly_seq"}
