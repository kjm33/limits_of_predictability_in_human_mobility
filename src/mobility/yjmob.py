"""YJMob100K adapter (Yabe et al., Sci Data 11:397, 2024; Zenodo 10.5281/zenodo.10836269).

Pre-discretized city-scale mobility: 500 m grid (200x200, x/y in 1..200),
48 half-hour timeslots per day, ~75 days per user, no raw GPS. This module
maps the grid onto the pipeline's hourly-sequence contract directly,
bypassing ingest/stay/h3map (there is nothing to stay-detect):

- ``seq_hourly.parquet``: most-frequent cell per (user, hour); a full
  75-day hourly index is materialized per user (``full_span=True``), so
  missingness q is honest. Timestamps are synthetic (dataset dates are
  masked): day 0 = Monday 2023-01-02, so hour-of-week features stay aligned.
- ``cells_r8.parquet``: grid vocabulary. The filename is kept for pipeline
  compatibility; tokens are ``x_y`` grid ids, and centroids live on a
  synthetic equator-anchored lattice with ~500 m spacing, so distance
  metrics (dist_km) approximate grid steps rather than real geography.
- ``seq_q.parquet`` / ``cohort.parquet``: same contracts as GeoLife.
- ``poi.parquet``: 85-dim POI-category count vector per grid cell
  (pivoted from the long-format cell_POIcat.csv.gz), keyed by token.

Not applicable: routing/suggest/folium (masked geography), stays/trips,
transport modes. Dataset2 note: day 27 is the natural-disaster day
(authors advise dropping it); days 60-74 are the emergency period.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .sequences import cohort_from_seq, user_q

_COLUMNS = ["user", "day", "timeslot", "x", "y"]
EPOCH = pd.Timestamp("2023-01-02 00:00:00")  # Monday; dataset dates are masked
GRID_M = 500.0
DEG_PER_CELL = GRID_M / 111_320.0  # equator-anchored lattice, ~500 m both axes
GRID_SIDE = 256  # x/y in 1..200; int packing base for cell codes (max 51,399)
_KEY_CELL = 2**17  # > GRID_SIDE * 201
_KEY_HOUR = 10**6  # > 75 * 24

_FILES = {
    "yjmob1": "yjmob100k-dataset1.csv.gz",
    "yjmob2": "yjmob100k-dataset2.csv.gz",
}


def load_records(path: Path) -> pd.DataFrame:
    """Load a YJMob100K csv(.gz), tolerating an optional header row."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as f:  # noqa: SIM115 (scoped reader)
        first = f.readline()
    has_header = not first.split(",")[0].strip().lstrip("-").isdigit()
    df = pd.read_csv(
        path,
        skiprows=int(has_header),
        header=None,
        names=_COLUMNS,
        dtype={"user": "int64", "day": "int32", "timeslot": "int32", "x": "int32", "y": "int32"},
    )
    return df.dropna().astype(
        {"user": "int64", "day": "int32", "timeslot": "int32", "x": "int32", "y": "int32"}
    )


def _hour_index(day: pd.Series, timeslot: pd.Series) -> np.ndarray:
    """Absolute hour index from day + 0/1-based timeslot (base auto-detected)."""
    base = int(timeslot.min()) % 2
    return (day.to_numpy() * 24 + (timeslot.to_numpy() - base) // 2).astype("int64")


def hourly_grid_sequences(rec: pd.DataFrame, full_span: bool = True) -> pd.DataFrame:
    """Most-frequent grid cell per (user, hour) -> seq_hourly-schema frame.

    Ties within an hour are broken by the cell of the last timeslot observed
    (mirrors sequences.hourly_sequences). With ``full_span`` every user gets
    the complete day-0..max-day hourly index; otherwise only first-to-last
    observed hours (GeoLife-style spans). Cell codes stay packed ints
    (``x * GRID_SIDE + y``); ``grid_vocab`` re-encodes to contiguous ids.
    """
    hour_idx = _hour_index(rec["day"], rec["timeslot"])
    cell_code = (rec["x"].to_numpy() * GRID_SIDE + rec["y"].to_numpy()).astype("int64")
    key = (rec["user"].to_numpy() * _KEY_HOUR + hour_idx) * _KEY_CELL + cell_code

    agg = pd.DataFrame(
        {
            "key": key,
            "n": np.ones(len(rec), dtype="int64"),
            "last_slot": rec["timeslot"].to_numpy(),
        }
    )
    grouped = (
        agg.groupby("key", sort=True)
        .agg(n=("n", "sum"), last_slot=("last_slot", "max"))
        .reset_index()
    )
    # winner per (user, hour): most records, ties -> cell of the later timeslot
    grouped["hour_key"] = grouped["key"] // _KEY_CELL
    winners = (
        grouped.sort_values(["n", "last_slot"], kind="stable")
        .drop_duplicates("hour_key", keep="last")
        .sort_values("key")
        .reset_index(drop=True)
    )

    w_key = winners["key"].to_numpy()
    w_user = w_key // (_KEY_CELL * _KEY_HOUR)
    w_hour = (w_key // _KEY_CELL) % _KEY_HOUR
    w_cell = w_key % _KEY_CELL

    n_hours = (int(rec["day"].max()) + 1) * 24
    users = np.unique(w_user)
    starts = np.searchsorted(w_user, users)

    user_out: list[np.ndarray] = []
    hour_out: list[np.ndarray] = []
    cell_out: list[np.ndarray] = []
    for i, u in enumerate(users):
        lo = starts[i]
        hi = starts[i + 1] if i + 1 < len(users) else len(w_user)
        hours_u = w_hour[lo:hi]
        cells_u = w_cell[lo:hi]
        if full_span:
            hu = np.arange(n_hours, dtype="int64")
        else:
            hu = np.arange(hours_u[0], hours_u[-1] + 1, dtype="int64")
        cu = np.full(len(hu), config.UNKNOWN, dtype="int64")
        cu[hours_u - hours_u[0]] = cells_u
        user_out.append(np.full(len(hu), u, dtype="int64"))
        hour_out.append(hu)
        cell_out.append(cu)

    encoded = pd.DataFrame(
        {
            "user": np.concatenate(user_out),
            "hour_idx": np.concatenate(hour_out),
            "cell_idx": np.concatenate(cell_out),
        }
    )
    encoded["hour"] = EPOCH + pd.to_timedelta(encoded.pop("hour_idx"), unit="h")
    encoded["user"] = encoded["user"].astype(str)
    return encoded[["user", "hour", "cell_idx"]]


def grid_vocab(encoded: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Re-encode packed cell codes to contiguous ids; build the vocabulary.

    Returns ``(vocab, encoded)`` where vocab is the cells_r8-schema frame
    (cell_idx, h3, lat, lon) with synthetic ~500 m lattice centroids and
    encoded carries ``cell_idx`` re-encoded plus the string token column
    ``h3`` (null for unknown hours).
    """
    codes = encoded["cell_idx"].to_numpy(copy=True)
    cells = np.unique(codes[codes != config.UNKNOWN])
    xs, ys = np.divmod(cells, GRID_SIDE)
    vocab = pd.DataFrame(
        {
            "cell_idx": np.arange(len(cells), dtype="int64"),
            "h3": [f"{int(x)}_{int(y)}" for x, y in zip(xs, ys, strict=True)],
            "lat": (xs - 0.5) * DEG_PER_CELL,
            "lon": (ys - 0.5) * DEG_PER_CELL,
        }
    )
    remap = np.full(int(cells.max()) + 1, config.UNKNOWN, dtype="int64")
    remap[cells] = vocab["cell_idx"].to_numpy()
    mask = codes != config.UNKNOWN
    codes[mask] = remap[codes[mask]]

    tokens = vocab["h3"].tolist()
    token_col = np.full(len(codes), None, dtype=object)
    token_col[mask] = [tokens[c] for c in codes[mask]]
    out = encoded.copy()
    out["cell_idx"] = codes
    out["h3"] = pd.Series(token_col, dtype="string")
    return vocab, out


def load_poi(poi_path: Path, categories_path: Path | None = None) -> pd.DataFrame:
    """Pivot long-format cell_POIcat (x, y, POIcategory, POI_count) to per-cell vectors."""
    long = pd.read_csv(poi_path)
    wide = long.pivot_table(
        index=["x", "y"], columns="POIcategory", values="POI_count", aggfunc="sum", fill_value=0
    )
    names = None
    if categories_path is not None and categories_path.exists():
        names = pd.read_csv(categories_path, header=None, encoding="utf-8-sig")[0].tolist()
    if names is not None and len(names) == wide.shape[1]:
        wide.columns = [f"poi_{c}" for c in names]
    else:
        wide.columns = [f"poi_cat_{c}" for c in wide.columns]
    wide = wide.reset_index()
    wide["h3"] = [f"{int(x)}_{int(y)}" for x, y in zip(wide["x"], wide["y"], strict=True)]
    return wide.drop(columns=["x", "y"])


def run_yjmob(
    dataset: str = "yjmob1",
    raw_file: Path | None = None,
    processed_dir: Path | None = None,
    full_span: bool = True,
) -> None:
    """Raw YJMob100K csv.gz -> seq_hourly/cells_r8/seq_q/cohort/poi parquets."""
    if dataset not in _FILES:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(_FILES)}")
    pdir = processed_dir or config.processed_dir(dataset)
    pdir.mkdir(parents=True, exist_ok=True)
    if raw_file is not None:
        path = Path(raw_file)
    else:
        path = Path(config.RAW_DIRS[dataset]) / _FILES[dataset]
    raw_dir = path.parent  # POI files are looked up next to the records file

    rec = load_records(path)
    encoded = hourly_grid_sequences(rec, full_span=full_span)
    vocab, encoded = grid_vocab(encoded)
    encoded = encoded[["user", "hour", "h3", "cell_idx"]]
    encoded.to_parquet(pdir / "seq_hourly.parquet", index=False, compression="zstd")
    vocab.to_parquet(pdir / "cells_r8.parquet", index=False)

    q = user_q(encoded)
    q.to_parquet(pdir / "seq_q.parquet", index=False)
    cohort = cohort_from_seq(encoded)
    cohort.to_parquet(pdir / "cohort.parquet", index=False)

    poi_path = raw_dir / "cell_POIcat.csv.gz"
    if poi_path.exists():
        poi = load_poi(poi_path, raw_dir / "POI_datacategories.csv")
        poi.to_parquet(pdir / "poi.parquet", index=False)
    else:
        poi = pd.DataFrame()

    print(
        f"users: {len(q)}  hours: {len(encoded):,}  cells: {len(vocab)}  "
        f"mean q: {q['q'].mean():.3f}  cohort: {len(cohort)}  poi cells: {len(poi)}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(_FILES), default="yjmob1")
    parser.add_argument("--span", choices=["full", "observed"], default="full")
    args = parser.parse_args()
    run_yjmob(dataset=args.dataset, full_span=args.span == "full")
