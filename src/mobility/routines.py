"""Routine mining — the "Thursday 15:15" detector.

Per-user place clustering (DBSCAN over stop centroids) → weekly origin→destination
routine cards (weekday × 15-min bucket) → trigger rule for proactive suggestion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from . import config
from .ingest import haversine_m

EARTH_R = 6_371_000.0


def cluster_places(
    stops: pd.DataFrame, eps_m: float = 300.0, min_samples: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-user DBSCAN over stop centroids -> place_id + places summary.

    Noise stops (-1) are re-assigned to the nearest non-noise place of the user
    when one exists.
    """
    stops = stops.copy()
    stops["place_id"] = -1
    place_rows: list[dict] = []
    for user, g in stops.groupby("user", sort=True):
        coords = np.radians(g[["lat", "lon"]].values)
        labels = DBSCAN(
            eps=eps_m / EARTH_R, min_samples=min_samples, metric="haversine"
        ).fit_predict(coords)
        if (labels >= 0).any():
            cents = np.array(
                [g.loc[labels == pid, ["lat", "lon"]].mean().values for pid in range(labels.max() + 1)]  # noqa: E501
            )
            for k in np.where(labels == -1)[0]:
                d = haversine_m(
                    np.full(len(cents), g["lat"].values[k]),
                    np.full(len(cents), g["lon"].values[k]),
                    cents[:, 0],
                    cents[:, 1],
                )
                labels[k] = int(np.argmin(d))
        else:
            labels = np.zeros(len(g), dtype=int)  # single fuzzy place
        stops.loc[g.index, "place_id"] = labels
        for pid, sub in g.assign(place_id=labels).groupby("place_id"):
            modal = sub["h3_r8"].mode()
            place_rows.append(
                {
                    "user": user,
                    "place_id": pid,
                    "n_visits": len(sub),
                    "mean_lat": sub["lat"].mean(),
                    "mean_lon": sub["lon"].mean(),
                    "mean_dwell_min": sub["dwell_min"].mean(),
                    "modal_h3_r8": modal.iloc[0] if len(modal) else None,
                }
            )
    places = pd.DataFrame(place_rows)
    places = _attach_labels(places, stops)
    return stops, places


def summarize_places(stops_with_places: pd.DataFrame) -> pd.DataFrame:
    """Places summary frame from stops+place_id (inverse of cluster_places output[0])."""
    rows = []
    for (user, pid), sub in stops_with_places.groupby(["user", "place_id"]):
        modal = sub["h3_r8"].mode()
        rows.append(
            {
                "user": user,
                "place_id": pid,
                "n_visits": len(sub),
                "mean_lat": sub["lat"].mean(),
                "mean_lon": sub["lon"].mean(),
                "mean_dwell_min": sub["dwell_min"].mean(),
                "modal_h3_r8": modal.iloc[0] if len(modal) else None,
            }
        )
    return _attach_labels(pd.DataFrame(rows), stops_with_places)


def _attach_labels(places: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    """Label each user's dominant night (0-6h) place 'home' and weekday 9-17 place 'work'."""
    stops = stops.copy()
    arr_hour = stops["arrive"].dt.hour
    stops["night_w"] = np.where(arr_hour < 6, stops["dwell_min"], 0.0)
    stops["work_w"] = np.where(
        (stops["arrive"].dt.weekday < 5) & (arr_hour >= 9) & (arr_hour < 17),
        stops["dwell_min"],
        0.0,
    )
    agg = stops.groupby(["user", "place_id"])[["night_w", "work_w"]].sum().reset_index()
    labels = {}
    for user, g in agg.groupby("user"):
        home = g.loc[g["night_w"].idxmax()]
        work = g.loc[g["work_w"].idxmax()]
        if home["night_w"] > 0:
            labels[(user, home["place_id"])] = "home"
        if work["work_w"] > 0 and (user, work["place_id"]) not in labels:
            labels[(user, work["place_id"])] = "work"
    places = places.copy()
    places["label"] = [labels.get((r.user, r.place_id), "") for r in places.itertuples()]
    return places


def _nearest_place(places: pd.DataFrame, user: str, lat: float, lon: float) -> int | None:
    g = places[places["user"] == user]
    if g.empty:
        return None
    d = haversine_m(
        np.full(len(g), lat), np.full(len(g), lon), g["mean_lat"].values, g["mean_lon"].values
    )
    return int(g["place_id"].values[np.argmin(d)])


def _attach_trip_places(trips: pd.DataFrame, places: pd.DataFrame) -> pd.DataFrame:
    trips = trips.copy()
    o_place, d_place = [], []
    for t in trips.itertuples():
        o_place.append(_nearest_place(places, t.user, t.o_lat, t.o_lon))
        d_place.append(_nearest_place(places, t.user, t.d_lat, t.d_lon))
    trips["o_place"] = o_place
    trips["d_place"] = d_place
    return trips


def _bucket_str(bucket: int, bucket_min: int) -> str:
    m = bucket * bucket_min
    return f"{m // 60:02d}:{m % 60:02d}-{(m + bucket_min) // 60:02d}:{(m + bucket_min) % 60:02d}"


def mine_routines(
    stops_with_places: pd.DataFrame,
    places: pd.DataFrame,
    trips: pd.DataFrame,
    bucket_min: int = 15,
    min_support_weeks: int = 3,
    min_confidence: float = 0.5,
) -> pd.DataFrame:
    """Routine cards: (user, o_place, d_place, weekday, bucket) -> support/confidence/stability."""
    trips = _attach_trip_places(trips, places)
    trips = trips.dropna(subset=["o_place", "d_place"])
    dep = trips["depart"]
    trips["weekday"] = dep.dt.weekday
    trips["bucket"] = (dep.dt.hour * 60 + dep.dt.minute) // bucket_min
    trips["week_key"] = dep.dt.strftime("%G-%V")

    cards = []
    pmap = places.set_index(["user", "place_id"])
    for (user, weekday, bucket, o_place, d_place), g in trips.groupby(
        ["user", "weekday", "bucket", "o_place", "d_place"], sort=True
    ):
        slot = trips[
            (trips["user"] == user)
            & (trips["weekday"] == weekday)
            & (trips["bucket"] == bucket)
            & (trips["o_place"] == o_place)
        ]
        support = g["week_key"].nunique()
        confidence = len(g) / len(slot)
        span_weeks = slot["week_key"].nunique()
        stability = min(support / span_weeks, 1.0) if span_weeks else 0.0
        if support < min_support_weeks or confidence < min_confidence:
            continue
        op, dp = pmap.loc[(user, o_place)], pmap.loc[(user, d_place)]
        cards.append(
            {
                "user": user,
                "o_place": o_place,
                "d_place": d_place,
                "weekday": weekday,
                "bucket": bucket,
                "bucket_str": _bucket_str(bucket, bucket_min),
                "n_trips": len(g),
                "support": support,
                "confidence": confidence,
                "stability": stability,
                "first_seen": g["depart"].min(),
                "last_seen": g["depart"].max(),
                "o_h3_r8": op["modal_h3_r8"],
                "d_h3_r8": dp["modal_h3_r8"],
                "o_lat": op["mean_lat"],
                "o_lon": op["mean_lon"],
                "d_lat": dp["mean_lat"],
                "d_lon": dp["mean_lon"],
                "o_label": op["label"],
                "d_label": dp["label"],
            }
        )
    return pd.DataFrame(cards).sort_values(
        ["user", "support", "confidence"], ascending=[True, False, False]
    ).reset_index(drop=True)


def suggest_destination(
    user: str,
    now: pd.Timestamp,
    recent_h3: list[str] | None,
    routines: pd.DataFrame,
    places: pd.DataFrame,
    threshold: float = 0.5,
    lookahead_buckets: int = 1,
) -> list[dict]:
    """Trigger rule: cards matching (user, weekday, now..+lookahead buckets, origin).

    Origin place comes from the last recent cell (nearest user place); when no
    recent context is given, any origin matches. Ranked by confidence x stability.
    """
    import h3

    nb = (now.hour * 60 + now.minute) // 15
    cands = routines[
        (routines["user"] == user)
        & (routines["weekday"] == now.weekday())
        & (routines["bucket"] >= nb)
        & (routines["bucket"] < nb + lookahead_buckets + 1)
    ]
    if recent_h3:
        lat, lon = h3.cell_to_latlng(recent_h3[-1])
        o_place = _nearest_place(places, user, lat, lon)
        if o_place is not None:
            cands = cands[cands["o_place"] == o_place]
    out = []
    for r in cands.itertuples():
        score = r.confidence * r.stability
        if score < threshold:
            continue
        out.append(
            {
                "d_place": r.d_place,
                "d_h3_r8": r.d_h3_r8,
                "d_lat": r.d_lat,
                "d_lon": r.d_lon,
                "score": score,
                "evidence": {
                    "user": r.user,
                    "o_place": r.o_place,
                    "d_place": r.d_place,
                    "weekday": r.weekday,
                    "bucket_str": r.bucket_str,
                    "n_trips": r.n_trips,
                    "support_weeks": r.support,
                    "confidence": r.confidence,
                    "stability": r.stability,
                    "o_label": r.o_label,
                    "d_label": r.d_label,
                    "first_seen": str(r.first_seen),
                    "last_seen": str(r.last_seen),
                    "o_lat": r.o_lat,
                    "o_lon": r.o_lon,
                },
            }
        )
    return sorted(out, key=lambda d: -d["score"])


def evaluate_trigger(
    routines: pd.DataFrame,
    stops_with_places: pd.DataFrame,
    trips: pd.DataFrame,
    places: pd.DataFrame,
    threshold: float = 0.5,
    lookahead_buckets: int = 1,
    test_frac: float = 0.2,
) -> pd.DataFrame:
    """Replay evaluation on the last `test_frac` of each user's trips (chronological).

    A trigger fires when a card matches (weekday, bucket within lookahead, origin
    place of the true trip); a hit when the top card's d_place equals the true
    destination place. recall = hits / eligible (test trips whose context had a card).
    """
    rows = []
    for user, g in trips.groupby("user"):
        g = g.sort_values("depart")
        n_test = max(1, int(len(g) * test_frac))
        test = g.iloc[-n_test:]
        n_eligible = n_fired = n_hits = 0
        for t in test.itertuples():
            o_place = _nearest_place(places, user, t.o_lat, t.o_lon)
            tb = (t.depart.hour * 60 + t.depart.minute) // 15
            cands = routines[
                (routines["user"] == user)
                & (routines["weekday"] == t.depart.weekday())
                & (routines["bucket"] >= tb)
                & (routines["bucket"] < tb + lookahead_buckets + 1)
            ]
            if o_place is not None:
                cands = cands[cands["o_place"] == o_place]
            if cands.empty:
                continue
            n_eligible += 1
            d_place = _nearest_place(places, user, t.d_lat, t.d_lon)
            scored = cands.assign(score=cands["confidence"] * cands["stability"])
            scored = scored[scored["score"] >= threshold]
            if scored.empty:
                continue
            n_fired += 1
            if int(scored.sort_values("score", ascending=False).iloc[0]["d_place"]) == d_place:
                n_hits += 1
        rows.append(
            {
                "user": user,
                "n_test": len(test),
                "n_eligible": n_eligible,
                "n_fired": n_fired,
                "n_hits": n_hits,
                "precision": n_hits / n_fired if n_fired else np.nan,
                "recall": n_hits / n_eligible if n_eligible else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run_routines(
    bucket_min: int = 15,
    min_support_weeks: int = 3,
    min_confidence: float = 0.5,
    processed_dir: Path | None = None,
) -> pd.DataFrame:
    pdir = processed_dir or config.PROCESSED
    stops = pd.read_parquet(pdir / "stops.parquet")
    trips = pd.read_parquet(pdir / "trips.parquet")
    stops_p, places = cluster_places(stops)
    routines = mine_routines(stops_p, places, trips, bucket_min, min_support_weeks, min_confidence)
    eval_df = evaluate_trigger(routines, stops_p, trips, places)
    stops_p.to_parquet(pdir / "places.parquet", index=False)
    places.to_parquet(pdir / "places_summary.parquet", index=False)
    routines.to_parquet(pdir / "routines.parquet", index=False)
    eval_df.to_parquet(pdir / "trigger_eval.parquet", index=False)
    fired = eval_df["n_fired"].sum()
    hits = eval_df["n_hits"].sum()
    n_users = routines["user"].nunique() if len(routines) else 0
    print(f"places: {len(places)} users_with_cards: {n_users} cards: {len(routines)}")
    print(f"trigger: fired {fired} hits {hits}")
    return routines


if __name__ == "__main__":
    run_routines()
