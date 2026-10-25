import h3
import numpy as np
import pandas as pd

from mobility.routines import (
    attach_venue_context,
    cluster_places,
    evaluate_trigger,
    mine_routines,
    suggest_destination,
)

A = (39.9800, 116.3100)  # origin place
B = (39.9900, 116.3500)  # routine destination
C = (39.9700, 116.2900)  # monday destination
EPOCH = pd.Timestamp("2023-01-01")  # a Sunday


def _stop(user, ts, hh, mm, lat, lon, dwell=30.0):
    arrive = pd.Timestamp(f"{ts.date()} {hh:02d}:{mm:02d}:00")
    return {
        "user": user,
        "arrive": arrive,
        "depart": arrive + pd.Timedelta(minutes=dwell),
        "lat": lat,
        "lon": lon,
        "dwell_min": dwell,
        "n_bins": int(dwell),
        "h3_r9": h3.latlng_to_cell(lat, lon, 9),
        "h3_r8": h3.latlng_to_cell(lat, lon, 8),
        "h3_r7": h3.latlng_to_cell(lat, lon, 7),
        "h3_r6": h3.latlng_to_cell(lat, lon, 6),
    }


def _trip(user, depart, o, d, travel=25.0):
    return {
        "user": user,
        "depart": depart,
        "arrive": depart + pd.Timedelta(minutes=travel),
        "o_lat": o[0],
        "o_lon": o[1],
        "d_lat": d[0],
        "d_lon": d[1],
        "o_h3_r8": h3.latlng_to_cell(o[0], o[1], 8),
        "d_h3_r8": h3.latlng_to_cell(d[0], d[1], 8),
        "travel_min": travel,
        "dist_km": 3.0,
    }


def _thursdays_2023():
    # 2023-01-01 was a Sunday: Thursdays are Jan 5, 12, 19, 26, Feb 2, 9
    return [4, 11, 18, 25, 32, 39]  # day offsets from EPOCH


def _synthetic_world():
    stops, trips = [], []
    # user u1: Thursday 15:16 A->B routine (6 weeks), Monday noise A->C
    for day in _thursdays_2023():
        d = EPOCH + pd.Timedelta(days=day)
        stops.append(_stop("u1", d, 15, 16, *A, dwell=5))
        stops.append(_stop("u1", d, 15, 50, *B, dwell=120))
        trips.append(_trip("u1", d + pd.Timedelta(hours=15, minutes=16), A, B))
    for day in [2, 9, 16, 23, 30, 37]:  # Mondays
        d = EPOCH + pd.Timedelta(days=day)
        minute = int(np.random.default_rng(day).integers(0, 480))
        trips.append(_trip("u1", d + pd.Timedelta(hours=11, minutes=minute), A, C))
        stops.append(_stop("u1", d, 11, 0, *A, dwell=10))
    # user u2: flaky routine 3 of 8 weeks (support=3 -> filtered at min_support_weeks=4)
    for wk, day in enumerate([4, 11, 18, 25, 32, 39, 46, 53]):
        if wk in (1, 4, 6):  # only 3 occurrences
            d = EPOCH + pd.Timedelta(days=day)
            trips.append(_trip("u2", d + pd.Timedelta(hours=9, minutes=5), A, B))
            stops.append(_stop("u2", d, 9, 5, *A, dwell=10))
            stops.append(_stop("u2", d, 9, 40, *B, dwell=60))
    return pd.DataFrame(stops), pd.DataFrame(trips)


def _near(r, lat, lon, tol=1e-3):
    return abs(r["lat"] - lat) < tol and abs(r["lon"] - lon) < tol


def test_cluster_places_groups_and_outlier():
    stops, _ = _synthetic_world()
    u1 = stops[stops["user"] == "u1"].copy()
    far_lat, far_lon = A[0] + 0.018, A[1] + 0.018  # ~2.5 km away
    outlier = pd.DataFrame(
        [_stop("u1", pd.Timestamp("2023-01-10"), 20, 0, far_lat, far_lon, dwell=60)]
    )
    u1 = pd.concat([u1, outlier], ignore_index=True)
    with_places, all_places = cluster_places(u1)
    places_u1 = all_places[all_places["user"] == "u1"]
    a_place = with_places[with_places.apply(lambda r: _near(r, *A), axis=1)]["place_id"]
    assert a_place.nunique() == 1  # all A stops -> one place
    assert len(places_u1) >= 1


def test_mine_routines_finds_thursday_card():
    stops, trips = _synthetic_world()
    stops_p, places = cluster_places(stops)
    cards = mine_routines(stops_p, places, trips, min_support_weeks=4, min_confidence=0.5)
    u1 = cards[cards["user"] == "u1"]
    assert len(u1) >= 1
    card = u1.iloc[0]
    assert card["weekday"] == 3  # Thursday
    assert card["bucket_str"] == "15:15-15:30"
    assert card["support"] == 6
    assert card["confidence"] > 0.9
    assert 0.5 < card["stability"] <= 1.0
    assert (cards["user"] == "u2").sum() == 0  # flaky routine filtered


def test_mine_routines_labels_home():
    stops, trips = _synthetic_world()
    # give B long night dwells for u1 -> home label
    extra = pd.DataFrame(
        [
            _stop("u1", EPOCH + pd.Timedelta(days=day), 2, 0, *B, dwell=400)
            for day in [6, 13, 20, 27, 34]
        ]
    )
    stops = pd.concat([stops, extra], ignore_index=True)
    _stops_p, places = cluster_places(stops)
    b_place = places[(places["user"] == "u1") & (places["label"] == "home")]
    assert len(b_place) == 1
    assert abs(b_place.iloc[0]["mean_lat"] - B[0]) < 1e-6


def test_suggest_destination_trigger():
    stops, trips = _synthetic_world()
    stops_p, places = cluster_places(stops)
    cards = mine_routines(stops_p, places, trips, min_support_weeks=4)
    now = pd.Timestamp("2023-03-09 15:14:00")  # a Thursday, 1 min before the card window
    assert now.weekday() == 3
    recent = [h3.latlng_to_cell(A[0], A[1], 8)]
    out = suggest_destination("u1", now, recent, cards, places, threshold=0.5, lookahead_buckets=1)
    assert len(out) >= 1
    top = out[0]
    assert top["d_h3_r8"] == h3.latlng_to_cell(B[0], B[1], 8)
    assert top["score"] >= 0.5
    assert top["evidence"]["support_weeks"] == 6
    # wrong day
    wed = pd.Timestamp("2023-03-08 15:14:00")
    assert suggest_destination("u1", wed, recent, cards, places) == []
    # wrong time of day
    late = pd.Timestamp("2023-03-09 20:00:00")
    assert suggest_destination("u1", late, recent, cards, places) == []


def test_evaluate_trigger_synthetic():
    stops, trips = _synthetic_world()
    stops_p, places = cluster_places(stops)
    cards = mine_routines(stops_p, places, trips, min_support_weeks=3)
    ev = evaluate_trigger(cards, stops_p, trips, places)
    u1 = ev[ev["user"] == "u1"].iloc[0]
    assert u1["n_eligible"] >= 1
    assert u1["precision"] == 1.0
    assert u1["recall"] == 1.0


def _write_checkin_io(tmp_path, points, meta):
    points.to_parquet(tmp_path / "points.parquet", index=False)
    meta.to_parquet(tmp_path / "checkins_meta.parquet", index=False)


def test_attach_venue_context(tmp_path):
    ts0 = pd.Timestamp("2023-01-05 15:20:00")
    ts1 = pd.Timestamp("2023-01-06 09:10:00")
    ts2 = pd.Timestamp("2023-01-07 21:00:00")
    lat_u1, lon_u1 = 39.9800, 116.3100
    lat_u2, lon_u2 = 39.9900, 116.3500
    points = pd.DataFrame({
        "user": ["u1", "u1", "u1", "u2", "u2"],
        "ts": [ts0, ts1, ts2, ts1, ts2],
        "lat": [lat_u1, lat_u1, 39.5000, lat_u2, lat_u2],
        "lon": [lon_u1, lon_u1, 116.0000, lon_u2, lon_u2],
        "alt_m": [np.nan] * 5,
        "seg_id": [0, 0, 0, 1, 1],
        "mode": [None] * 5,
    })
    meta = pd.DataFrame({
        "user": ["u1", "u1", "u1", "u2", "u2"],
        "ts": [ts0, ts1, ts2, ts1, ts2],
        "venue_id": ["v1", "v1", "v3", "v4", "v5"],
        "venue_cat_id": ["c1", "c1", "c3", "c4", "c5"],
        "venue_cat_name": ["Bar", "Bar", "Park", "Cafe", "Bar"],
    })
    _write_checkin_io(tmp_path, points, meta)
    stops_p = pd.DataFrame([
        {"user": "u1", "h3_r9": h3.latlng_to_cell(lat_u1, lon_u1, 9), "place_id": 0},
        {"user": "u1", "h3_r9": h3.latlng_to_cell(39.9700, 116.2900, 9), "place_id": 1},
        {"user": "u2", "h3_r9": h3.latlng_to_cell(lat_u2, lon_u2, 9), "place_id": 0},
    ])
    places = pd.DataFrame({
        "user": ["u1", "u1", "u2"],
        "place_id": [0, 1, 0],
        "label": ["home", "", "work"],
    })
    out = attach_venue_context(places, stops_p, tmp_path)
    assert list(out.columns) == [
        "user", "place_id", "label", "top_venue_cat", "n_venue_checkins",
    ]
    # (user, place_id) order preserved; new columns appended at the end
    assert out[["user", "place_id"]].values.tolist() == [["u1", 0], ["u1", 1], ["u2", 0]]
    # u1 place 0: Bar x2 at the stop cell -> modal Bar, n=2; the Park check-in
    # sits outside any stop cell -> contributes nowhere
    r = out[(out["user"] == "u1") & (out["place_id"] == 0)].iloc[0]
    assert r["top_venue_cat"] == "Bar" and r["n_venue_checkins"] == 2
    # unmatched place keeps NA / 0
    r = out[(out["user"] == "u1") & (out["place_id"] == 1)].iloc[0]
    assert pd.isna(r["top_venue_cat"]) and r["n_venue_checkins"] == 0
    # u2 place 0: Cafe x1 + Bar x1 -> tie broken by mode order (Bar < Cafe)
    r = out[out["user"] == "u2"].iloc[0]
    assert r["top_venue_cat"] == "Bar" and r["n_venue_checkins"] == 2


def test_attach_venue_context_noop_snap_style(tmp_path):
    # SNAP-style checkins_meta: no venue_cat_name -> columns appended, zeroed
    ts0 = pd.Timestamp("2023-01-05 15:20:00")
    points = pd.DataFrame({"user": ["u1"], "ts": [ts0], "lat": [39.98], "lon": [116.31]})
    meta = pd.DataFrame({"user": ["u1"], "ts": [ts0], "loc_id": ["42"]})
    _write_checkin_io(tmp_path, points, meta)
    stops_p = pd.DataFrame([
        {"user": "u1", "h3_r9": h3.latlng_to_cell(39.98, 116.31, 9), "place_id": 0},
    ])
    places = pd.DataFrame({"user": ["u1", "u1"], "place_id": [0, 1], "n_visits": [5, 2]})
    out = attach_venue_context(places, stops_p, tmp_path)
    assert len(out) == 2
    assert list(out.columns) == [
        "user", "place_id", "n_visits", "top_venue_cat", "n_venue_checkins",
    ]
    assert out["top_venue_cat"].isna().all()
    assert (out["n_venue_checkins"] == 0).all()
    assert out["n_visits"].tolist() == [5, 2]
    # neither parquet present -> same no-op
    empty_dir = tmp_path / "missing"
    empty_dir.mkdir()
    out2 = attach_venue_context(places, stops_p, empty_dir)
    assert list(out2.columns) == list(out.columns)
    assert out2["top_venue_cat"].isna().all() and (out2["n_venue_checkins"] == 0).all()
