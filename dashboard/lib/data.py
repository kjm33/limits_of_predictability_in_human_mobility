"""Curated loaders + pure aggregation helpers for the dashboard.

Loaders are thin wrappers so the resolved base dir is part of the cache key
(the env override must not be masked by a stale ``None`` key). Aggregation
helpers are plain pandas — unit-testable without streamlit.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import h3
import pandas as pd
from dashboard.lib import config

try:  # streamlit is only in the `demo` group; plain pytest must still work.
    import streamlit as st

    def _cache(func):
        return st.cache_data(show_spinner=False)(func)

except ImportError:  # pragma: no cover - exercised only without the demo group
    def _cache(func):
        return func

from mobility import config as mob_config  # checked-in pipeline constants

SEQ_COLS = [
    "user", "hour", "cell_idx", "h3", "weekday", "hour_of_day", "lat", "lon", "known",
]
CARD_COLS = [
    "user", "o_place", "d_place", "weekday", "bucket", "bucket_str", "n_trips",
    "support", "confidence", "stability", "first_seen", "last_seen", "o_h3_r8",
    "d_h3_r8", "o_lat", "o_lon", "d_lat", "d_lon", "o_label", "d_label",
]
PLACE_COLS = [
    "user", "place_id", "n_visits", "mean_lat", "mean_lon", "mean_dwell_min",
    "modal_h3_r8", "label", "top_venue_cat", "n_venue_checkins",
]

CORE_TABLES = ("dataset_summary", "pi_distributions", "leaderboards", "featured_users")


def _base(base_dir: str | Path | None) -> Path:
    return Path(base_dir).expanduser() if base_dir else config.package_dir()


# ---------------------------------------------------------------- loaders ----

def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def dataset_summary(base_dir: str | Path | None = None) -> pd.DataFrame:
    return _dataset_summary(str(_base(base_dir)))


@_cache
def _dataset_summary(base: str) -> pd.DataFrame:
    return pd.read_parquet(Path(base) / "dataset_summary.parquet")


def pi_distributions(base_dir: str | Path | None = None) -> pd.DataFrame:
    return _pi_distributions(str(_base(base_dir)))


@_cache
def _pi_distributions(base: str) -> pd.DataFrame:
    return pd.read_parquet(Path(base) / "pi_distributions.parquet")


def leaderboards(base_dir: str | Path | None = None) -> pd.DataFrame:
    return _leaderboards(str(_base(base_dir)))


@_cache
def _leaderboards(base: str) -> pd.DataFrame:
    return pd.read_parquet(Path(base) / "leaderboards.parquet")


def featured_users(base_dir: str | Path | None = None) -> pd.DataFrame:
    return _featured_users(str(_base(base_dir)))


@_cache
def _featured_users(base: str) -> pd.DataFrame:
    return pd.read_parquet(Path(base) / "featured_users.parquet")


def user_seq(dataset: str, user: str, base_dir: str | Path | None = None) -> pd.DataFrame:
    return _user_table("seq", dataset, user, str(_base(base_dir)))


def user_cards(dataset: str, user: str, base_dir: str | Path | None = None) -> pd.DataFrame:
    return _user_table("cards", dataset, user, str(_base(base_dir)))


def user_places(dataset: str, user: str, base_dir: str | Path | None = None) -> pd.DataFrame:
    return _user_table("places", dataset, user, str(_base(base_dir)))


@_cache
def _user_table(name: str, dataset: str, user: str, base: str) -> pd.DataFrame:
    path = Path(base) / "users" / dataset / str(user) / f"{name}.parquet"
    if not path.exists():
        return _empty(SEQ_COLS if name == "seq" else CARD_COLS if name == "cards" else PLACE_COLS)
    return pd.read_parquet(path)


def user_poi(dataset: str, user: str, base_dir: str | Path | None = None) -> pd.DataFrame:
    return _user_poi(dataset, user, str(_base(base_dir)))


@_cache
def _user_poi(dataset: str, user: str, base: str) -> pd.DataFrame:
    path = Path(base) / "users" / dataset / str(user) / "poi.parquet"
    if not path.exists():
        return _empty(["category", "count"])
    return pd.read_parquet(path)


def dataset_routines(dataset: str) -> pd.DataFrame:
    """Fallback routine cards from the dataset's processed dir (yjmob: none)."""
    return _dataset_routines(dataset, str(config.processed_dir(dataset)))


@_cache
def _dataset_routines(dataset: str, root: str) -> pd.DataFrame:
    path = Path(root) / "routines.parquet"
    if not path.exists():
        return _empty(CARD_COLS)
    return pd.read_parquet(path)


def dataset_places_summary(dataset: str) -> pd.DataFrame:
    """Fallback place summary from the dataset's processed dir."""
    return _dataset_places_summary(dataset, str(config.processed_dir(dataset)))


@_cache
def _dataset_places_summary(dataset: str, root: str) -> pd.DataFrame:
    path = Path(root) / "places_summary.parquet"
    if not path.exists():
        return _empty(PLACE_COLS)
    return pd.read_parquet(path)


def has_package(base_dir: str | Path | None = None) -> bool:
    base = _base(base_dir)
    return all((base / f"{name}.parquet").exists() for name in CORE_TABLES)


# ----------------------------------------------------- aggregation helpers ----

def fano_frac_table(pi: pd.DataFrame) -> pd.DataFrame:
    """Per-dataset share of users with Pi_actual >= Pi_unc (Fano compliance)."""
    rows = []
    for ds, g in pi.groupby("dataset", sort=True):
        rows.append(
            {
                "dataset": ds,
                "n_users": len(g),
                "fano_frac": float((g["Pi_actual"] >= g["Pi_unc"]).mean()),
            }
        )
    return pd.DataFrame(rows)


def pi_stats_table(pi: pd.DataFrame) -> pd.DataFrame:
    """Per-dataset Pi summary stats over ALL users (cohort size shown separately)."""
    return (
        pi.groupby("dataset", sort=True)
        .agg(
            n_users=("Pi_actual", "size"),
            pi_actual_median=("Pi_actual", "median"),
            pi_actual_mean=("Pi_actual", "mean"),
            pi_unc_median=("Pi_unc", "median"),
            pi_rand_median=("Pi_rand", "median"),
        )
        .reset_index()
    )


def entropy_medians(pi: pd.DataFrame) -> pd.DataFrame:
    """Per-dataset entropy-trio medians + whether S_rand >= S_unc >= S_actual holds."""
    med = (
        pi.groupby("dataset", sort=True)
        .agg(
            S_rand=("S_rand", "median"), S_unc=("S_unc", "median"), S_actual=("S_actual", "median")
        )
        .reset_index()
    )
    med["monotone"] = (med["S_rand"] >= med["S_unc"]) & (med["S_unc"] >= med["S_actual"])
    return med


def pi_vs_q(pi: pd.DataFrame, keys: list[str] | None = None, per_dataset: int = 4000,
            seed: int = 0) -> pd.DataFrame:
    """Optional per-dataset sample of (q, Pi_actual) for the scatter panel."""
    g = pi if keys is None else pi[pi["dataset"].isin(keys)]
    parts = [
        d.sample(n=min(per_dataset, len(d)), random_state=seed) for _, d in g.groupby("dataset")
    ]
    return pd.concat(parts, ignore_index=True) if parts else g


def leaderboard_for(lb: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """One dataset's leaderboard sorted by top1, with a badge column."""
    g = lb[lb["dataset"] == dataset].sort_values("top1", ascending=False).copy()
    g["source_badge"] = [config.SOURCE_BADGE.get(s, s) for s in g["source"]]
    return g.reset_index(drop=True)


def winner_table(summary: pd.DataFrame) -> pd.DataFrame:
    """Best baseline per dataset — the "winner flips by regime" panel data."""
    return (
        summary.sort_values("best_baseline_top1", ascending=False)[
            ["dataset", "best_baseline", "best_baseline_top1"]
        ]
        .reset_index(drop=True)
    )


def deep_vs_baseline(lb: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Best baseline vs deep models for one dataset (empty when no deep rows)."""
    g = lb[lb["dataset"] == dataset]
    base = g[g["source"] == "baseline"]
    deep = g[g["source"] == "deep"]
    if base.empty or deep.empty:
        return pd.DataFrame(columns=["dataset", "model", "source", "top1"])
    best_base = base.loc[base["top1"].idxmax()]
    rows = [
        {"dataset": dataset, "model": best_base["model"], "source": "baseline",
         "top1": float(best_base["top1"])},
        *[{"dataset": dataset, "model": r.model, "source": "deep", "top1": float(r.top1)}
          for r in deep.itertuples()],
    ]
    return pd.DataFrame(rows)


def weekday_hour_matrix(seq: pd.DataFrame) -> pd.DataFrame:
    """7x24 activity counts (weekday rows Mon..Sun, hour_of_day columns)."""
    known = seq[seq["known"]] if "known" in seq.columns else seq
    if known.empty:
        return pd.DataFrame(0, index=range(7), columns=range(24), dtype="int64")
    grid = (
        known.pivot_table(index="weekday", columns="hour_of_day", values="user", aggfunc="count")
        .reindex(index=range(7), columns=range(24), fill_value=0)
        .fillna(0)
        .astype("int64")
    )
    return grid


def poi_top(poi: pd.DataFrame, n: int = 12) -> pd.DataFrame:
    """Wide 1-row poi count frame -> top-n (category, count)."""
    if poi.empty or "category" not in poi.columns:
        return pd.DataFrame(columns=["category", "count"])
    return poi.sort_values("count", ascending=False).head(n).reset_index(drop=True)


# ------------------------------------------------------------ suggest glue ----

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def resolve_now(weekday: str, hh: int, mm: int, ref: datetime | None = None) -> pd.Timestamp:
    """'Mon' + 15:14 -> next such weekday strictly after ref (matches the CLI)."""
    ref = ref or datetime.now()
    wd = WEEKDAYS.index(weekday.title())
    day = ref + timedelta(days=1)
    while day.weekday() != wd:
        day += timedelta(days=1)
    return pd.Timestamp(day.replace(hour=hh, minute=mm, second=0, microsecond=0))


def origin_for(places: pd.DataFrame, user: str) -> tuple[float, float] | None:
    """Home place coords, else most-visited place (same rule as the CLI)."""
    g = places[(places["user"] == user) & (places["label"] == "home")]
    if g.empty:
        g = places[places["user"] == user]
    if g.empty:
        return None
    row = g.sort_values("n_visits", ascending=False).iloc[0]
    return float(row["mean_lat"]), float(row["mean_lon"])


def run_trigger(
    user: str,
    now: pd.Timestamp,
    origin: tuple[float, float],
    cards: pd.DataFrame,
    places: pd.DataFrame,
    threshold: float = 0.5,
    lookahead: int = 1,
) -> list[dict]:
    """Trigger rule on one user's cards — thin wrapper over routines.suggest_destination."""
    from mobility.routines import suggest_destination

    recent = [h3.latlng_to_cell(origin[0], origin[1], mob_config.H3_PRIMARY_RES)]
    return suggest_destination(
        user, now, recent, cards, places, threshold=threshold, lookahead_buckets=lookahead
    )


def suggest_frames(dataset: str, user: str, base_dir: str | Path | None = None) -> tuple[
    pd.DataFrame, pd.DataFrame, str
]:
    """(cards, places, source) for one user; falls back to dataset-level parquets."""
    cards = user_cards(dataset, user, base_dir)
    places = user_places(dataset, user, base_dir)
    if not cards.empty:
        return cards, places, "curated user package"
    cards = dataset_routines(dataset)
    cards = cards[cards["user"] == user] if "user" in cards.columns else cards
    if places.empty:
        places = dataset_places_summary(dataset)
    return cards, places, "dataset routines.parquet"
