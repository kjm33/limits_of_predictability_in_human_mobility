"""Stay-point (stop) detection — Zheng et al. WWW 2009, params ~250 m / >= 10 min.

Pipeline: per (user, segment) -> 1-minute median bins -> sliding stay detection.
Outputs stops timeline (user, h3 cells, centroid, arrive, depart, dwell) and
trips (origin stop -> destination stop).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .ingest import haversine_m


def time_bin(points: pd.DataFrame, bin_s: int = config.TIME_BIN_S) -> pd.DataFrame:
    """Median position per time bin within each (user, seg_id)."""
    if points.empty:
        return points.iloc[0:0][["user", "seg_id", "ts", "lat", "lon"]]
    return (
        points.assign(bin=points["ts"].dt.floor(f"{bin_s}s"))
        .groupby(["user", "seg_id", "bin"], sort=True)[["lat", "lon"]]
        .median()
        .reset_index()
        .rename(columns={"bin": "ts"})
    )


def detect_stays_segment(
    ts: np.ndarray, lat: np.ndarray, lon: np.ndarray, radius_m: float, min_minutes: float
) -> list[dict]:
    """Sliding-window stay detection on one segment (arrays time-ordered).

    From anchor i, extend while points stay within `radius_m` of the running
    centroid; if the covered duration >= min_minutes, emit a stay and jump past
    it, otherwise advance the anchor by one point.
    """
    n = len(ts)
    stays: list[dict] = []
    i = 0
    while i < n - 1:
        j = i + 1
        c_lat, c_lon = lat[i], lon[i]
        while j < n:
            d = float(
                haversine_m(np.array([c_lat]), np.array([c_lon]), lat[j : j + 1], lon[j : j + 1])[0]
            )
            if d > radius_m:
                break
            c_lat = float(np.mean(lat[i : j + 1]))
            c_lon = float(np.mean(lon[i : j + 1]))
            j += 1
        if (ts[j - 1] - ts[i]) >= min_minutes * 60:
            stays.append(
                {
                    "arrive": int(ts[i]),
                    "depart": int(ts[j - 1]),
                    "lat": float(np.median(lat[i:j])),
                    "lon": float(np.median(lon[i:j])),
                    "n_bins": int(j - i),
                }
            )
            i = j
        else:
            i += 1
    return stays


def detect_stays(
    points: pd.DataFrame,
    radius_m: float = config.STAY_RADIUS_M,
    min_minutes: float = config.STAY_MIN_MINUTES,
    merge_gap_m: float = config.STAY_RADIUS_M,
) -> pd.DataFrame:
    """Stops for all users from raw points (user, ts, lat, lon, seg_id).

    Consecutive stays of a user within `merge_gap_m` are merged into one stop,
    but only when the gap between them is at most SEGMENT_GAP_MIN — beyond that
    the user may have left and returned, so the stops stay separate.
    """
    binned = time_bin(points)
    records: list[dict] = []
    for (user, _seg), g in binned.groupby(["user", "seg_id"], sort=True):
        # resolution-safe epoch seconds (ts may be datetime64[s/us/ns] under pandas 3)
        ts = g["ts"].to_numpy().astype("datetime64[s]").astype(np.int64)
        for s in detect_stays_segment(ts, g["lat"].values, g["lon"].values, radius_m, min_minutes):
            records.append(
                {
                    "user": user,
                    "arrive": pd.Timestamp(s["arrive"], unit="s"),
                    "depart": pd.Timestamp(s["depart"], unit="s"),
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "n_bins": s["n_bins"],
                }
            )
    if not records:
        return pd.DataFrame(columns=["user", "arrive", "depart", "lat", "lon", "dwell_min"])

    stops = pd.DataFrame.from_records(records).sort_values(["user", "arrive"])
    stops = stops.reset_index(drop=True)
    lat = stops["lat"].values
    lon = stops["lon"].values
    user = stops["user"].values
    arr = stops["arrive"].to_numpy()
    dep = stops["depart"].to_numpy(copy=True)  # writable (CoW views are read-only)
    max_gap = np.timedelta64(int(config.SEGMENT_GAP_MIN * 60), "s")

    keep = [0]
    for k in range(1, len(stops)):
        p = keep[-1]
        same_user = user[k] == user[p]
        near = (
            float(
                haversine_m(
                    np.array([lat[p]]), np.array([lon[p]]), np.array([lat[k]]), np.array([lon[k]])
                )[0]
            )
            <= merge_gap_m
        )
        contiguous = (arr[k] - dep[p]) <= max_gap
        if same_user and near and contiguous:
            dep[p] = max(dep[p], dep[k])
        else:
            keep.append(k)
    stops = stops.iloc[keep].copy()
    stops["depart"] = pd.to_datetime(dep[keep])
    stops["dwell_min"] = (stops["depart"] - stops["arrive"]).dt.total_seconds() / 60
    return (
        stops[["user", "arrive", "depart", "lat", "lon", "dwell_min", "n_bins"]]
        .reset_index(drop=True)
    )


def stops_with_h3(stops: pd.DataFrame) -> pd.DataFrame:
    """Attach multi-resolution H3 cells to stop centroids."""
    import h3

    if stops.empty:
        for r in ("h3_r9", "h3_r8", "h3_r7", "h3_r6"):
            stops[r] = pd.Series(dtype="object")
        return stops
    lat = stops["lat"].values
    lon = stops["lon"].values
    stops = stops.copy()
    stops["h3_r9"] = [
        h3.latlng_to_cell(la, lo, config.H3_STOP_RES) for la, lo in zip(lat, lon, strict=True)
    ]
    # derive parents from r9 (H3 does not nest perfectly: latlng_to_cell at a coarser
    # resolution can differ from cell_to_parent near boundaries — keep the chain exact)
    stops["h3_r8"] = [h3.cell_to_parent(c, config.H3_PRIMARY_RES) for c in stops["h3_r9"]]
    stops["h3_r7"] = [h3.cell_to_parent(c, config.H3_CORRIDOR_RES) for c in stops["h3_r9"]]
    stops["h3_r6"] = [h3.cell_to_parent(c, config.H3_COARSE_RES) for c in stops["h3_r9"]]
    return stops


def build_trips(stops: pd.DataFrame) -> pd.DataFrame:
    """Trips = consecutive stops per user (origin -> destination)."""
    rows = []
    for user, g in stops.sort_values(["user", "arrive"]).groupby("user"):
        g = g.reset_index(drop=True)
        for k in range(len(g) - 1):
            o, d = g.iloc[k], g.iloc[k + 1]
            dist = float(
                haversine_m(
                    np.array([o["lat"]]),
                    np.array([o["lon"]]),
                    np.array([d["lat"]]),
                    np.array([d["lon"]]),
                )[0]
            )
            rows.append(
                {
                    "user": user,
                    "depart": o["depart"],
                    "arrive": d["arrive"],
                    "o_lat": o["lat"],
                    "o_lon": o["lon"],
                    "d_lat": d["lat"],
                    "d_lon": d["lon"],
                    "o_h3_r8": o.get("h3_r8"),
                    "d_h3_r8": d.get("h3_r8"),
                    "travel_min": (d["arrive"] - o["depart"]).total_seconds() / 60,
                    "dist_km": dist / 1000,
                }
            )
    return pd.DataFrame(rows)


def run_stays(points_path=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """points parquet -> stops.parquet + trips.parquet."""
    points = pd.read_parquet(points_path or config.PROCESSED / "points.parquet")
    stops = stops_with_h3(detect_stays(points))
    trips = build_trips(stops)
    stops.to_parquet(config.PROCESSED / "stops.parquet", index=False)
    trips.to_parquet(config.PROCESSED / "trips.parquet", index=False)
    print(f"stops: {len(stops):,} trips: {len(trips):,}")
    return stops, trips


if __name__ == "__main__":
    run_stays()
