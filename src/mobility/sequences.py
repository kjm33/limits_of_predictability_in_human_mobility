"""Hourly H3 location sequences per user, cell vocabulary, and integer encoding.

Inputs are the consolidated GPS points (user, ts, lat, lon, ...) produced by
ingestion; outputs are per-user hourly location sequences ready for entropy
analysis (Song et al. 2010).
"""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pandas as pd

from . import config


def hourly_sequences(points: pd.DataFrame, res: int = config.H3_PRIMARY_RES) -> pd.DataFrame:
    """Most frequent H3 cell at ``res`` for each (user, hour) between first/last hour.

    The full hourly index is materialized per user, so hours without points get
    a null cell. Ties on frequency are broken by the cell of the last point
    logged in that hour (exact: per-cell max timestamp compared within the hour).

    Returns a long frame (user, hour, h3) sorted by user, hour.
    """
    pts = points[["user", "ts", "lat", "lon"]].copy()
    pts["hour"] = pts["ts"].dt.floor("h")
    pts["cell"] = [
        h3.latlng_to_cell(la, lo, res)
        for la, lo in zip(pts["lat"].to_numpy(), pts["lon"].to_numpy(), strict=True)
    ]

    agg = pts.groupby(["user", "hour", "cell"], sort=False).agg(
        n=("cell", "size"), last_ts=("ts", "max")
    )
    winners = (
        agg.reset_index()
        .sort_values(["user", "hour", "n", "last_ts"], kind="stable")
        .groupby(["user", "hour"], sort=False)
        .tail(1)[["user", "hour", "cell"]]
    )

    spans = pts.groupby("user")["hour"].agg(["min", "max"])
    full = (
        pd.Series(
            [
                pd.date_range(a, b, freq="h")
                for a, b in zip(spans["min"], spans["max"], strict=True)
            ],
            index=spans.index,
            name="hour",
        )
        .explode()
        .reset_index()
    )

    hourly = full.merge(winners, on=["user", "hour"], how="left").rename(columns={"cell": "h3"})
    hourly["h3"] = hourly["h3"].astype("string")
    return hourly.sort_values(["user", "hour"], kind="stable").reset_index(drop=True)


def cell_vocab(h3_cells: pd.Series) -> pd.DataFrame:
    """Deterministic vocabulary: alphabetically sorted cells -> contiguous cell_idx."""
    cells = sorted(pd.unique(pd.Series(h3_cells).dropna().astype(str)))
    latlng = [h3.cell_to_latlng(c) for c in cells]
    return pd.DataFrame(
        {
            "cell_idx": np.arange(len(cells), dtype="int64"),
            "h3": cells,
            "lat": [la for la, _ in latlng],
            "lon": [lo for _, lo in latlng],
        }
    )


def encode_sequences(hourly: pd.DataFrame, vocab: pd.DataFrame) -> pd.DataFrame:
    """Add integer ``cell_idx`` column; config.UNKNOWN (-1) for unknown hours."""
    out = hourly.copy()
    mapping = pd.Series(vocab["cell_idx"].to_numpy(), index=pd.Index(vocab["h3"]))
    out["cell_idx"] = out["h3"].map(mapping).fillna(float(config.UNKNOWN)).astype("int64")
    return out


def user_q(encoded: pd.DataFrame) -> pd.DataFrame:
    """Per-user fraction of unknown hours: user, n_hours, n_known, q, first_hour, last_hour."""
    known = encoded["cell_idx"] != config.UNKNOWN
    q = (
        encoded.assign(_known=known)
        .groupby("user")
        .agg(
            n_hours=("_known", "size"),
            n_known=("_known", "sum"),
            first_hour=("hour", "min"),
            last_hour=("hour", "max"),
        )
    )
    q["n_known"] = q["n_known"].astype("int64")
    q["q"] = 1.0 - q["n_known"] / q["n_hours"]
    return q[["n_hours", "n_known", "q", "first_hour", "last_hour"]].reset_index()


def cohort_from_seq(encoded: pd.DataFrame) -> pd.DataFrame:
    """Cohort from hourly sequences when no stops table exists (grid datasets).

    Mirrors h3map.select_cohort thresholds, but active days and distinct
    cells are measured over known hours only.
    """
    known = encoded[encoded["cell_idx"] != config.UNKNOWN].copy()
    known["_day"] = known["hour"].dt.normalize()
    stats = known.groupby("user").agg(
        active_days=("_day", "nunique"),
        n_cells=("cell_idx", "nunique"),
    )
    mask = (stats["active_days"] >= config.MIN_ACTIVE_DAYS) & (
        stats["n_cells"] >= config.MIN_DISTINCT_R8
    )
    return stats[mask].reset_index()[["user"]]


def build_sequences(
    points_path: str | Path | None = None,
    out_prefix: str = "seq",
    res: int = config.H3_PRIMARY_RES,
    processed_dir: Path | None = None,
    min_points_per_user: int | None = None,
) -> None:
    """Read points.parquet and write hourly sequences, vocabulary, and q stats.

    ``min_points_per_user`` drops users below a raw-observation count before
    the hourly panel is built. Long-span sparse check-in datasets (e.g.
    Brightkite) otherwise materialize a mostly-UNKNOWN panel of
    users x enrollment-hours that can exceed available memory; the filter
    bounds the panel and matches next-location benchmark practice.
    """
    pdir = processed_dir or config.PROCESSED
    path = Path(points_path) if points_path is not None else pdir / "points.parquet"
    points = pd.read_parquet(path, columns=["user", "ts", "lat", "lon"])

    if min_points_per_user is not None:
        counts = points["user"].value_counts()
        keep = counts[counts >= min_points_per_user].index
        points = points[points["user"].isin(keep)]
        print(
            f"min_points_per_user={min_points_per_user}: keeping {len(keep)} of "
            f"{counts.size} users ({len(points):,} of {counts.sum():,} points)"
        )

    hourly = hourly_sequences(points, res=res)
    vocab = cell_vocab(hourly["h3"].dropna())
    encoded = encode_sequences(hourly, vocab)

    encoded.to_parquet(pdir / f"{out_prefix}_hourly.parquet", index=False)
    vocab.to_parquet(pdir / f"cells_r{res}.parquet", index=False)
    q = user_q(encoded)
    q.to_parquet(pdir / f"{out_prefix}_q.parquet", index=False)
    print(
        f"users: {len(q)}  hours: {len(encoded):,}  cells: {len(vocab)}  "
        f"mean q: {q['q'].mean():.3f}"
    )


if __name__ == "__main__":
    build_sequences()
