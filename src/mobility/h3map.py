"""Multi-resolution H3 mapping helpers, per-user coverage stats, cohort selection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def cell_at(lat: float, lon: float, res: int = config.H3_PRIMARY_RES) -> str:
    import h3

    return h3.latlng_to_cell(lat, lon, res)


def cell_centroid(cell: str) -> tuple[float, float]:
    """(lat, lon) of an H3 cell centroid."""
    import h3

    lat, lon = h3.cell_to_latlng(cell)
    return lat, lon


def cell_area_km2(cell: str) -> float:
    import h3

    return h3.cell_area(cell, unit="km^2")


def coverage_stats(stops: pd.DataFrame, points: pd.DataFrame) -> pd.DataFrame:
    """Per-user coverage: activity, spatial diversity, logging density."""
    p_stats = points.groupby("user").agg(
        n_points=("ts", "size"),
        first_ts=("ts", "min"),
        last_ts=("ts", "max"),
    )
    p_stats["active_days"] = (
        points.assign(day=points["ts"].dt.floor("D")).groupby("user")["day"].nunique()
    )
    p_stats["logged_hours"] = points.groupby("user").apply(
        lambda g: g["ts"].dt.floor("h").nunique(), include_groups=False
    )

    s_stats = stops.groupby("user").agg(
        n_stops=("user", "size"),
        n_r9=("h3_r9", "nunique"),
        n_r8=("h3_r8", "nunique"),
        n_r7=("h3_r7", "nunique"),
        n_r6=("h3_r6", "nunique"),
        total_dwell_h=("dwell_min", lambda s: s.sum() / 60),
    )
    df = p_stats.join(s_stats, how="outer").fillna(
        {"n_stops": 0, "n_r9": 0, "n_r8": 0, "n_r7": 0, "n_r6": 0, "total_dwell_h": 0}
    )
    span_days = (df["last_ts"] - df["first_ts"]).dt.total_seconds() / 86400
    df["span_days"] = span_days
    df["logging_intensity"] = df["logged_hours"] / span_days.clip(lower=1)
    return df.reset_index()


def select_cohort(
    stats: pd.DataFrame,
    min_active_days: int = config.MIN_ACTIVE_DAYS,
    min_distinct_r8: int = config.MIN_DISTINCT_R8,
) -> pd.DataFrame:
    """Modeling cohort: enough active days and enough distinct r8 locations."""
    mask = (stats["active_days"] >= min_active_days) & (stats["n_r8"] >= min_distinct_r8)
    return stats[mask].reset_index(drop=True)


def run_coverage(processed_dir: Path | None = None) -> pd.DataFrame:
    pdir = processed_dir or config.PROCESSED
    stops = pd.read_parquet(pdir / "stops.parquet")
    points = pd.read_parquet(pdir / "points.parquet", columns=["user", "ts"])
    stats = coverage_stats(stops, points)
    stats.to_parquet(pdir / "coverage_stats.parquet", index=False)
    cohort = select_cohort(stats)
    cohort[["user"]].to_parquet(pdir / "cohort.parquet", index=False)
    print(f"users: {len(stats)} cohort: {len(cohort)}")
    return stats


if __name__ == "__main__":
    run_coverage()
