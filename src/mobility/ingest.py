"""GeoLife ingestion: PLT parsing, labels join, QC, trajectory segmentation.

Produces a consolidated Parquet of GPS points:
    user, ts, lat, lon, alt_m, seg_id, mode
"""

from __future__ import annotations

import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

_PLT_COLUMNS = ["lat", "lon", "filler", "alt_ft", "days", "date", "time"]


def parse_plt(path: Path) -> pd.DataFrame:
    """Parse a single GeoLife .plt file (6 header lines, 7-field CSV rows).

    Data rows: lat,lon,<always 0>,alt_ft,days,date,time.
    """
    df = pd.read_csv(
        path,
        skiprows=6,
        header=None,
        names=_PLT_COLUMNS,
        usecols=[0, 1, 3, 5, 6],
        dtype={"lat": "f8", "lon": "f8", "alt_ft": "f8", "date": str, "time": str},
    )
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y-%m-%d %H:%M:%S")
    df["alt_m"] = df["alt_ft"] * 0.3048
    return df[["ts", "lat", "lon", "alt_m"]]


def load_labels(user_dir: Path) -> pd.DataFrame | None:
    """Load labels.txt transport-mode intervals for a user (start, end, mode)."""
    path = user_dir / "labels.txt"
    if not path.exists():
        return None
    df = pd.read_csv(path, sep="\t", skiprows=1, header=None, names=["start", "end", "mode"])
    df["start"] = pd.to_datetime(df["start"], format="%Y/%m/%d %H:%M:%S")
    df["end"] = pd.to_datetime(df["end"], format="%Y/%m/%d %H:%M:%S")
    return df.sort_values("start").reset_index(drop=True)


def assign_modes(ts: pd.Series, labels: pd.DataFrame | None) -> np.ndarray:
    """Assign transport mode to each point via interval search; None where unlabeled."""
    n = len(ts)
    if labels is None or n == 0:
        return np.full(n, None, dtype=object)
    starts = labels["start"].values.astype("datetime64[ns]")
    ends = labels["end"].values.astype("datetime64[ns]")
    modes = labels["mode"].values
    t = ts.values.astype("datetime64[ns]")
    idx = np.searchsorted(starts, t, side="right") - 1
    out: np.ndarray = np.full(n, None, dtype=object)
    inside = np.zeros(n, dtype=bool)
    ok = idx >= 0
    inside[ok] = t[ok] <= ends[idx[ok]]
    out[inside] = modes[idx[inside]]
    return out


def haversine_m(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Vectorized great-circle distance in meters."""
    r = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def qc_and_segment(df: pd.DataFrame) -> pd.DataFrame:
    """QC (valid coords, impossible-speed jitter) + gap segmentation.

    seg_id increments when the time gap to the previous point exceeds
    config.SEGMENT_GAP_MIN minutes or when coordinates are invalid/duplicated.
    """
    if df.empty:
        return df.assign(seg_id=pd.Series(dtype="i4"))

    df = df.sort_values("ts").reset_index(drop=True)
    valid = (
        df["lat"].between(-90, 90)
        & df["lon"].between(-180, 180)
        & ~((df["lat"].abs() < 1e-6) & (df["lon"].abs() < 1e-6))
    )
    df = df[valid].reset_index(drop=True)
    if df.empty:
        return df.assign(seg_id=pd.Series(dtype="i4"))

    dt = df["ts"].diff().dt.total_seconds().values
    dist = np.concatenate(
        [
            [0.0],
            haversine_m(
                df["lat"].values[:-1],
                df["lon"].values[:-1],
                df["lat"].values[1:],
                df["lon"].values[1:],
            ),
        ]
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.where(dt > 0, dist / np.maximum(dt, 1e-9), 0.0)

    # drop impossible-speed points (first point of a segment always kept)
    new_seg = dt > config.SEGMENT_GAP_MIN * 60
    bad = (speed > config.MAX_SPEED_MS) & ~new_seg & ~np.isnan(speed)
    df = df[~bad].reset_index(drop=True)

    dt = df["ts"].diff().dt.total_seconds().values
    seg_break = np.zeros(len(df), dtype=bool)
    seg_break[1:] = dt[1:] > config.SEGMENT_GAP_MIN * 60
    df["seg_id"] = np.cumsum(seg_break).astype("i4")
    return df


def ingest_user(user: str, raw_dir: Path = config.RAW_DIR) -> pd.DataFrame:
    """Parse + QC all trajectories of one user; returns long-format points frame."""
    user_dir = raw_dir / user
    plt_files = sorted((user_dir / "Trajectory").glob("*.plt"))
    if not plt_files:
        return pd.DataFrame(columns=["user", "ts", "lat", "lon", "alt_m", "seg_id", "mode"])
    parts = [parse_plt(p) for p in plt_files]
    df = pd.concat(parts, ignore_index=True)
    df = qc_and_segment(df)
    labels = load_labels(user_dir)
    df["mode"] = assign_modes(df["ts"], labels)
    df["user"] = user
    return df[["user", "ts", "lat", "lon", "alt_m", "seg_id", "mode"]]


def _ingest_user_tuple(args: tuple[str, Path]) -> pd.DataFrame:
    return ingest_user(*args)


def ingest_all(
    raw_dir: Path = config.RAW_DIR,
    workers: int | None = None,
) -> pd.DataFrame:
    """Ingest all users in parallel."""
    users = sorted(d.name for d in raw_dir.iterdir() if re.fullmatch(r"\d{3}", d.name))
    workers = workers or min(32, len(users))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(_ingest_user_tuple, [(u, raw_dir) for u in users], chunksize=1))
    df = pd.concat(parts, ignore_index=True)
    return df.sort_values(["user", "ts"]).reset_index(drop=True)


def run_ingest(out_path: Path | None = None) -> Path:
    """Full ingestion → points parquet + per-user QC stats."""
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = out_path or config.PROCESSED / "points.parquet"
    df = ingest_all()
    df.to_parquet(out_path, index=False, engine="pyarrow", compression="zstd")
    stats = (
        df.groupby("user")
        .agg(
            n_points=("ts", "size"),
            n_segments=("seg_id", "nunique"),
            start=("ts", "min"),
            end=("ts", "max"),
            labeled_frac=("mode", lambda s: s.notna().mean()),
        )
        .reset_index()
    )
    stats["n_days"] = (
        (stats["end"] - stats["start"]).dt.total_seconds() / 86400
    ).round(1)
    stats.to_parquet(config.PROCESSED / "ingest_stats.parquet", index=False)
    print(f"points: {len(df):,} users: {df['user'].nunique()} -> {out_path}")
    return out_path


if __name__ == "__main__":
    run_ingest()
