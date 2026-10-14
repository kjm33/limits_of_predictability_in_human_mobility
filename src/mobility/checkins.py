"""Check-in dataset ingestion: Foursquare NYC/Tokyo (TSMC'15), Gowalla, Brightkite.

Parses raw check-in files into the shared ``points.parquet`` schema
(user, ts, lat, lon, alt_m, seg_id, mode) so the GeoLife pipeline
(sequences/entropy/baselines/deep, optionally stay/routines/graphs) runs
unchanged. Venue/location ids and Foursquare venue categories are kept in
``checkins_meta.parquet`` for future POI-aware features.

Differences vs GeoLife worth remembering:

- Check-ins are user-initiated events (inter-check-in gaps are typically
  hours), so stay detection (250 m / 10 min) finds few stops and the
  trips/routines stages are mostly degenerate; sequences/entropy/baselines/
  deep are the meaningful stages.
- Foursquare timestamps are UTC + a per-check-in timezone offset -> local
  wall time (matching GeoLife's local-time convention). Gowalla/Brightkite
  timestamps are UTC-only (no offset available in the data).
- Users are integers, cast to str for schema parity; alt_m is NaN and mode
  is null (check-ins carry neither altitude nor transport mode).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .ingest import haversine_m

_FSQ_COLUMNS = [
    "user",
    "venue_id",
    "venue_cat_id",
    "venue_cat_name",
    "lat",
    "lon",
    "tz_off",
    "utc_time",
]
_SNAP_COLUMNS = ["user", "time", "lat", "lon", "loc_id"]

_FILES = {
    "fsq_nyc": "dataset_tsmc2014/dataset_TSMC2014_NYC.txt",
    "fsq_tky": "dataset_tsmc2014/dataset_TSMC2014_TKY.txt",
    "gowalla": "loc-gowalla_totalCheckins.txt.gz",
    "brightkite": "loc-brightkite_totalCheckins.txt.gz",
}


def parse_foursquare_tsmc(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Foursquare TSMC2014 TSV -> (points, meta) with local wall-clock ts."""
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=_FSQ_COLUMNS,
        dtype={
            "user": "int64",
            "venue_id": str,
            "venue_cat_id": str,
            "venue_cat_name": str,
            "lat": "float64",
            "lon": "float64",
            "tz_off": "int64",
            "utc_time": str,
        },
        encoding="latin-1",
        on_bad_lines="warn",
    )
    utc = pd.to_datetime(df["utc_time"], format="%a %b %d %H:%M:%S %z %Y", utc=True)
    local = (utc + pd.to_timedelta(df["tz_off"], unit="m")).dt.tz_localize(None)
    points = pd.DataFrame(
        {"user": df["user"], "ts": local, "lat": df["lat"], "lon": df["lon"]}
    )
    meta = pd.DataFrame(
        {
            "user": df["user"],
            "ts": local,
            "venue_id": df["venue_id"],
            "venue_cat_id": df["venue_cat_id"],
            "venue_cat_name": df["venue_cat_name"],
        }
    )
    return points, meta


def parse_snap_checkins(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gowalla/Brightkite check-ins (tab-separated, UTC Z times) -> (points, meta)."""
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=_SNAP_COLUMNS,
        dtype={"user": "int64", "time": str, "lat": str, "lon": str, "loc_id": str},
        on_bad_lines="warn",
    )
    ts = pd.to_datetime(df["time"], format="ISO8601", utc=True).dt.tz_localize(None)
    points = pd.DataFrame(
        {
            "user": df["user"],
            "ts": ts,
            "lat": pd.to_numeric(df["lat"], errors="coerce"),
            "lon": pd.to_numeric(df["lon"], errors="coerce"),
        }
    )
    meta = pd.DataFrame({"user": df["user"], "ts": ts, "loc_id": df["loc_id"]})
    return points, meta


def qc_and_segment_users(df: pd.DataFrame) -> pd.DataFrame:
    """User-aware variant of ingest.qc_and_segment for interleaved users.

    Same rules (drop invalid coords, drop impossible speeds within a
    segment, break segments on > SEGMENT_GAP_MIN gaps) plus: segments never
    span users, even when timestamps coincide at a user boundary.
    """
    df = df.sort_values(["user", "ts"], kind="stable").reset_index(drop=True)
    valid = (
        df["lat"].between(-90, 90)
        & df["lon"].between(-180, 180)
        & ~((df["lat"].abs() < 1e-6) & (df["lon"].abs() < 1e-6))
    )
    df = df[valid.fillna(False)].reset_index(drop=True)
    if df.empty:
        return df.assign(seg_id=pd.Series(dtype="i4"))

    dt = df["ts"].diff().dt.total_seconds().to_numpy()
    new_user = df["user"].ne(df["user"].shift()).to_numpy()
    dist = np.concatenate(
        [
            [0.0],
            haversine_m(
                df["lat"].to_numpy()[:-1],
                df["lon"].to_numpy()[:-1],
                df["lat"].to_numpy()[1:],
                df["lon"].to_numpy()[1:],
            ),
        ]
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.where(dt > 0, dist / np.maximum(dt, 1e-9), 0.0)
    new_seg = new_user | (dt > config.SEGMENT_GAP_MIN * 60)
    bad = (speed > config.MAX_SPEED_MS) & ~new_seg & ~np.isnan(speed)
    df = df[~bad].reset_index(drop=True)

    dt = df["ts"].diff().dt.total_seconds().to_numpy()
    new_user = df["user"].ne(df["user"].shift()).to_numpy()
    seg_break = new_user.copy()
    seg_break[0] = True
    seg_break[1:] |= dt[1:] > config.SEGMENT_GAP_MIN * 60
    df["seg_id"] = np.cumsum(seg_break).astype("i4") - 1  # ids start at 0 (ingest parity)
    return df


def run_checkins(
    dataset: str,
    raw_file: Path | None = None,
    processed_dir: Path | None = None,
) -> Path:
    """Raw check-in file -> points.parquet + checkins_meta.parquet (shared schema)."""
    if dataset not in _FILES:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(_FILES)}")
    pdir = processed_dir or config.processed_dir(dataset)
    pdir.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(config.RAW_DIRS[dataset])
    path = Path(raw_file) if raw_file is not None else raw_dir / _FILES[dataset]

    if dataset.startswith("fsq_"):
        points, meta = parse_foursquare_tsmc(path)
    else:
        points, meta = parse_snap_checkins(path)
    points = points.reset_index(names="_row")  # row-aligns meta to pre-QC points
    points = qc_and_segment_users(points)
    keep = points.pop("_row").to_numpy()
    points["user"] = points["user"].astype(str)
    points["alt_m"] = np.nan
    points["mode"] = None
    points = points[["user", "ts", "lat", "lon", "alt_m", "seg_id", "mode"]]

    meta = meta.iloc[keep].reset_index(drop=True)
    meta["user"] = meta["user"].astype(str)

    out = pdir / "points.parquet"
    points.to_parquet(out, index=False, compression="zstd")
    meta.to_parquet(pdir / "checkins_meta.parquet", index=False, compression="zstd")
    print(
        f"{dataset}: points: {len(points):,} users: {points['user'].nunique()} "
        f"checkins_meta: {len(meta):,} -> {out}"
    )
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(_FILES), required=True)
    args = parser.parse_args()
    run_checkins(dataset=args.dataset)
