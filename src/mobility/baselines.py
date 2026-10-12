"""Next-cell prediction baselines on hourly location sequences + trip destinations.

Predictors are always fit on a temporal train split only:

- ``FrequencyPredictor``: the user's overall most-visited cell.
- ``TimeConditionedPredictor``: most-visited cell per hour-of-week bucket
  (168 buckets), backing off to the user's overall frequency for unseen
  buckets.
- ``MarkovPredictor``: order-k Markov chain over cell sequences with
  order-k -> order-(k-1) -> ... -> order-1 -> frequency backoff; either
  per-user chains or one collective chain pooled across users.

Cell identity is the integer ``cell_idx`` (UNKNOWN = ``config.UNKNOWN``).
``evaluate_hourly`` scores next-hour prediction on a per-user chronological
test split; ``evaluate_trip_destination`` scores destination-cell prediction
from the trip origin. ``run_baselines`` reads the processed parquets, saves
result tables to data/processed and prints a summary.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from . import config
from .ingest import haversine_m

UNK = config.UNKNOWN

_RESULT_COLUMNS = ["predictor", "user", "n_eval", "top1", "top3", "dist_km"]


def temporal_split(
    df: pd.DataFrame, test_frac: float = 0.2, time_col: str = "hour"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-user chronological split: train = first ceil((1-test_frac) * n) rows."""
    df = df.sort_values(["user", time_col], kind="stable")
    pos = df.groupby("user", sort=False).cumcount()
    n_tot = df.groupby("user", sort=False)[time_col].transform("size")
    n_train = np.ceil(n_tot * (1.0 - test_frac)).astype("int64")
    mask = pos.to_numpy() < n_train.to_numpy()
    return df.loc[mask].reset_index(drop=True), df.loc[~mask].reset_index(drop=True)


def _frequency_ranks(train: pd.DataFrame) -> tuple[dict[str, tuple[int, ...]], tuple[int, ...]]:
    """Per-user and global cell rankings by visit count (ties: lower cell_idx first)."""
    known = train.loc[train["cell_idx"] != UNK, ["user", "cell_idx"]]
    if known.empty:
        return {}, ()
    per_user = (
        known.groupby(["user", "cell_idx"])
        .size()
        .reset_index(name="n")
        .sort_values(["user", "n", "cell_idx"], ascending=[True, False, True])
    )
    user_rank = {
        u: tuple(int(c) for c in g["cell_idx"]) for u, g in per_user.groupby("user", sort=False)
    }
    overall = (
        known.groupby("cell_idx")
        .size()
        .reset_index(name="n")
        .sort_values(["n", "cell_idx"], ascending=[False, True])
    )
    return user_rank, tuple(int(c) for c in overall["cell_idx"])


def _user_sequences(train: pd.DataFrame) -> dict[str, np.ndarray]:
    """Per-user chronological cell sequences with UNKNOWN positions dropped."""
    cols = ["user", "hour", "cell_idx"] if "hour" in train.columns else ["user", "cell_idx"]
    known = train.loc[train["cell_idx"] != UNK, cols]
    if "hour" in cols:
        known = known.sort_values(["user", "hour"], kind="stable")
    return {u: g["cell_idx"].to_numpy(dtype=np.int64) for u, g in known.groupby("user", sort=False)}


def _pad(ranked: list[int] | tuple[int, ...], k: int) -> tuple[int, ...]:
    """Truncate/pad a ranking to exactly k entries (UNK never matches a true cell)."""
    out = list(ranked)[:k]
    return tuple(out + [UNK] * (k - len(out)))


class FrequencyPredictor:
    """Predict the user's overall most-visited cell; global frequency fallback."""

    def __init__(self) -> None:
        self._user_rank: dict[str, tuple[int, ...]] = {}
        self._global_rank: tuple[int, ...] = ()

    def fit(self, train: pd.DataFrame) -> FrequencyPredictor:
        self._user_rank, self._global_rank = _frequency_ranks(train)
        return self

    def predict_ranked(self, user: str, k: int = 3) -> tuple[int, ...]:
        user_rank = self._user_rank.get(user, ())
        seen = set(user_rank)
        ranked = list(user_rank) + [c for c in self._global_rank if c not in seen]
        return _pad(ranked, k)

    def predict(self, user: str) -> int:
        return self.predict_ranked(user, k=1)[0]


class TimeConditionedPredictor:
    """Most-visited cell per hour-of-week bucket (0..167) per user.

    A bucket never observed in training backs off to the user's overall
    frequency; an unknown user backs off to the global frequency.
    """

    def __init__(self) -> None:
        self._by_bucket: dict[str, dict[int, tuple[int, ...]]] = {}
        self._user_rank: dict[str, tuple[int, ...]] = {}
        self._global_rank: tuple[int, ...] = ()

    @staticmethod
    def _bucket(hour: pd.Timestamp | str) -> int:
        ts = pd.Timestamp(hour)
        return int(ts.dayofweek) * 24 + int(ts.hour)

    def fit(self, train: pd.DataFrame) -> TimeConditionedPredictor:
        self._user_rank, self._global_rank = _frequency_ranks(train)
        known = train.loc[train["cell_idx"] != UNK, ["user", "hour", "cell_idx"]]
        if known.empty:
            self._by_bucket = {}
            return self
        known = known.assign(bucket=known["hour"].map(self._bucket))
        ranked = (
            known.groupby(["user", "bucket", "cell_idx"])
            .size()
            .reset_index(name="n")
            .sort_values(["user", "bucket", "n", "cell_idx"], ascending=[True, True, False, True])
        )
        self._by_bucket = {
            u: {
                b: tuple(int(c) for c in g["cell_idx"])
                for b, g in gg.groupby("bucket", sort=False)
            }
            for u, gg in ranked.groupby("user", sort=False)
        }
        return self

    def predict_ranked(self, user: str, hour: pd.Timestamp | str, k: int = 3) -> tuple[int, ...]:
        bucket_ranks = self._by_bucket.get(user, {})
        ranked = list(bucket_ranks.get(self._bucket(hour), ()))
        user_rank = self._user_rank.get(user, ())
        seen = set(ranked)
        ranked += [c for c in (user_rank or self._global_rank) if c not in seen]
        return _pad(ranked, k)

    def predict(self, user: str, hour: pd.Timestamp | str) -> int:
        return self.predict_ranked(user, hour, k=1)[0]


class MarkovPredictor:
    """Order-k Markov chain over cell sequences with degenerate-order backoff.

    Chains are built from each user's known-cell subsequence (UNKNOWN positions
    dropped, so contexts are contiguous known history). Backoff: order-k ->
    order-(k-1) -> ... -> order-1 -> frequency ranking (user if known, else
    global). A context containing UNKNOWN, or unseen at every order, falls back
    to the frequency ranking directly. With ``individual=False`` a single chain
    is pooled across all users (shared cell space); contexts still come from the
    querying user's own history.
    """

    def __init__(self, order: int = 1, individual: bool = True) -> None:
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.individual = individual
        # user key -> [chain for order 1, ..., chain for order k]; pooled under None
        self._chains: dict[str | None, list[dict[tuple[int, ...], dict[int, int]]]] = {}
        self._user_rank: dict[str, tuple[int, ...]] = {}
        self._global_rank: tuple[int, ...] = ()

    def fit(self, train: pd.DataFrame) -> MarkovPredictor:
        self._user_rank, self._global_rank = _frequency_ranks(train)
        seqs = _user_sequences(train)
        if self.individual:
            items: list[tuple[str | None, np.ndarray]] = list(seqs.items())
        else:
            pooled = (
                np.concatenate(list(seqs.values())) if seqs else np.array([], dtype=np.int64)
            )
            items = [(None, pooled)]
        self._chains = {}
        for key, seq in items:
            chains: list[dict[tuple[int, ...], dict[int, int]]] = [{} for _ in range(self.order)]
            for i in range(len(seq)):
                nxt = int(seq[i])
                for k in range(1, min(self.order, i) + 1):
                    ctx = tuple(int(c) for c in seq[i - k : i])
                    counts = chains[k - 1].setdefault(ctx, {})
                    counts[nxt] = counts.get(nxt, 0) + 1
            self._chains[key] = chains
        return self

    def _chains_for(self, user: str | None) -> list[dict[tuple[int, ...], dict[int, int]]] | None:
        return self._chains.get(user if self.individual else None)

    def _fill(self, ranked: list[int], user: str | None, k: int) -> tuple[int, ...]:
        user_rank = self._user_rank.get(user, ()) if user is not None else ()
        seen = set(ranked)
        return _pad(ranked + [c for c in (user_rank or self._global_rank) if c not in seen], k)

    def predict_ranked(
        self, context: tuple[int, ...] | list[int], user: str | None = None, k: int = 3
    ) -> tuple[int, ...]:
        ctx = tuple(int(c) for c in context)
        if len(ctx) > self.order:
            ctx = ctx[-self.order :]
        if not ctx or UNK in ctx:
            return self._fill([], user, k)
        chains = self._chains_for(user)
        if chains is not None:
            for j in range(min(len(ctx), self.order), 0, -1):
                counts = chains[j - 1].get(ctx[-j:])
                if counts:
                    ranked = [c for c, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
                    return self._fill(ranked, user, k)
        return self._fill([], user, k)

    def predict(self, context: tuple[int, ...], user: str | None = None) -> int:
        return self.predict_ranked(context, user, k=1)[0]


def topk_accuracy(
    y_true: np.ndarray, y_pred: np.ndarray, ranks: int | np.ndarray | list[int] | tuple[int, ...]
) -> float | dict[int, float]:
    """Top-k accuracy of ranked predictions.

    ``y_true``: (n,) true cell indices; ``y_pred``: (n, m) ranked candidate
    cells per test point. ``ranks`` is a single k (returns float) or a
    collection of k values (returns {k: accuracy}).
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if y_pred.ndim == 1:
        y_pred = y_pred[:, None]
    scalar = isinstance(ranks, (int, np.integer))
    ks = [int(ranks)] if scalar else [int(k) for k in np.atleast_1d(ranks)]
    out: dict[int, float] = {}
    for k in ks:
        if y_true.size == 0:
            out[k] = float("nan")
            continue
        m = min(k, y_pred.shape[1])
        hits = (y_pred[:, :m] == y_true[:, None]).any(axis=1)
        out[k] = float(hits.mean())
    return out[ks[0]] if scalar else out


def _coords_lookup(cells: pd.DataFrame) -> dict[int, tuple[float, float]]:
    """cell_idx -> (lat, lon); falls back to h3.cell_to_latlng when lat/lon absent."""
    if {"lat", "lon"} <= set(cells.columns):
        return {
            int(i): (float(la), float(lo))
            for i, la, lo in zip(cells["cell_idx"], cells["lat"], cells["lon"], strict=False)
        }
    import h3

    out: dict[int, tuple[float, float]] = {}
    for i, cell in zip(cells["cell_idx"], cells["h3"], strict=False):
        la, lo = h3.cell_to_latlng(cell)
        out[int(i)] = (float(la), float(lo))
    return out


def distance_error_km(
    y_true: np.ndarray, y_pred: np.ndarray, cells: pd.DataFrame
) -> np.ndarray:
    """Per-point great-circle distance (km) between true and predicted cell centroids.

    Points whose true or predicted cell is missing from ``cells`` yield NaN.
    """
    coords = _coords_lookup(cells)

    def latlon(cs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pts = [coords.get(int(c)) for c in np.asarray(cs)]
        return (
            np.array([p[0] if p is not None else np.nan for p in pts]),
            np.array([p[1] if p is not None else np.nan for p in pts]),
        )

    lat1, lon1 = latlon(y_true)
    lat2, lon2 = latlon(y_pred)
    with np.errstate(invalid="ignore"):
        return haversine_m(lat1, lon1, lat2, lon2) / 1000.0


def trip_destination_accuracy(pred_cells: np.ndarray, true_cells: np.ndarray) -> float:
    """Top-1 destination-cell accuracy."""
    pred_cells = np.asarray(pred_cells)
    true_cells = np.asarray(true_cells)
    if true_cells.size == 0:
        return float("nan")
    return float((pred_cells == true_cells).mean())


def _result_row(
    predictor: str, user: str, y: np.ndarray, ranked: np.ndarray, cells: pd.DataFrame
) -> dict:
    """Score one (predictor, user) block: top-1/top-3 accuracy + mean distance km."""
    accs = cast(dict[int, float], topk_accuracy(y, ranked, (1, 3)))
    dist = distance_error_km(y, ranked[:, 0], cells)
    finite = dist[np.isfinite(dist)]
    return {
        "predictor": predictor,
        "user": user,
        "n_eval": int(y.size),
        "top1": accs[1],
        "top3": accs[3],
        "dist_km": float(finite.mean()) if finite.size else float("nan"),
    }


_AnyPredictor = FrequencyPredictor | TimeConditionedPredictor | MarkovPredictor


def _predict_ranked(
    pred: _AnyPredictor, history: list[int], user: str, hour: pd.Timestamp
) -> tuple:
    """Dispatch a ranked top-3 prediction for one test row."""
    if isinstance(pred, TimeConditionedPredictor):
        return pred.predict_ranked(user, hour, k=3)
    if isinstance(pred, MarkovPredictor):
        return pred.predict_ranked(tuple(history[-pred.order :]), user, k=3)
    return pred.predict_ranked(user, k=3)


def evaluate_hourly(
    seq: pd.DataFrame, cells: pd.DataFrame, test_frac: float = 0.2
) -> pd.DataFrame:
    """Next-hour cell prediction on the per-user chronological test split.

    For each test hour whose target cell is known, predictors rank candidates
    from the user's known-cell history. The context spans the train/test
    boundary: the last known train cells warm-start the Markov chains, and
    known test cells are appended to the history as evaluation proceeds.
    Targets equal to UNKNOWN are excluded from scoring and from the history.
    Returns a long frame: predictor, user, n_eval, top1, top3, dist_km.
    """
    train, test = temporal_split(seq, test_frac)
    predictors: dict[str, _AnyPredictor] = {
        "freq": FrequencyPredictor().fit(train),
        "time": TimeConditionedPredictor().fit(train),
    }
    for k in (1, 2, 3):
        predictors[f"markov{k}"] = MarkovPredictor(order=k, individual=True).fit(train)
        predictors[f"markov{k}_col"] = MarkovPredictor(order=k, individual=False).fit(train)
    train_seqs = _user_sequences(train)
    rows: list[dict] = []
    for user, g in test.groupby("user", sort=True):
        g = g.sort_values("hour", kind="stable")
        history: list[int] = list(train_seqs.get(user, ()))
        y: list[int] = []
        ranked: dict[str, list[tuple]] = {name: [] for name in predictors}
        for row in g.itertuples(index=False):
            target = int(row.cell_idx)
            if target == UNK:
                continue
            for name, pred in predictors.items():
                ranked[name].append(_predict_ranked(pred, history, user, row.hour))
            y.append(target)
            history.append(target)
        if not y:
            continue
        y_arr = np.asarray(y)
        for name, rk in ranked.items():
            rows.append(_result_row(name, user, y_arr, np.asarray(rk), cells))
    return pd.DataFrame(rows, columns=_RESULT_COLUMNS)


def evaluate_trip_destination(
    trips: pd.DataFrame, cells: pd.DataFrame, test_frac: float = 0.2
) -> pd.DataFrame:
    """Trip-destination prediction: frequency-of-destination vs origin->dest Markov.

    Trips are split per user by ``depart``. Destination h3_r8 strings are mapped
    to the shared cell vocabulary (unmappable -> UNKNOWN, excluded from
    scoring). Predictors: per-user destination frequency, and a pooled order-1
    chain over origin->destination transitions that backs off to the user's
    destination frequency, then the global one. Long frame like evaluate_hourly.
    """
    vocab = {h: int(i) for h, i in zip(cells["h3"], cells["cell_idx"], strict=False)}
    df = trips.assign(
        o_idx=trips["o_h3_r8"].map(vocab).fillna(float(UNK)).astype("int64"),
        d_idx=trips["d_h3_r8"].map(vocab).fillna(float(UNK)).astype("int64"),
    )
    train, test = temporal_split(df, test_frac, time_col="depart")
    user_rank, global_rank = _frequency_ranks(
        train.loc[train["d_idx"] != UNK].rename(columns={"d_idx": "cell_idx"})[
            ["user", "cell_idx"]
        ]
    )
    chain: dict[int, dict[int, int]] = {}
    t = train.loc[(train["o_idx"] != UNK) & (train["d_idx"] != UNK)]
    for o, d in zip(t["o_idx"].to_numpy(), t["d_idx"].to_numpy(), strict=False):
        counts = chain.setdefault(int(o), {})
        counts[int(d)] = counts.get(int(d), 0) + 1
    rows: list[dict] = []
    for user, g in test.groupby("user", sort=True):
        g = g.loc[g["d_idx"] != UNK].sort_values("depart", kind="stable")
        if g.empty:
            continue
        y = g["d_idx"].to_numpy()
        urank = user_rank.get(user, ())
        freq_ranked = _pad(list(urank) + [c for c in global_rank if c not in set(urank)], 3)
        rows.append(
            _result_row("trip_freq", user, y, np.tile(np.asarray(freq_ranked), (len(g), 1)), cells)
        )
        markov_ranked = []
        for o in g["o_idx"].to_numpy():
            counts = chain.get(int(o)) if o != UNK else None
            if counts is None:
                markov_ranked.append(freq_ranked)
                continue
            rk = [c for c, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
            seen = set(rk)
            markov_ranked.append(_pad(rk + [c for c in freq_ranked if c not in seen], 3))
        rows.append(_result_row("trip_markov", user, y, np.asarray(markov_ranked), cells))
    return pd.DataFrame(rows, columns=_RESULT_COLUMNS)


def run_baselines() -> None:
    """Read the processed parquets, evaluate all baselines, save + print summary."""
    seq = pd.read_parquet(config.PROCESSED / "seq_hourly.parquet")
    cells = pd.read_parquet(config.PROCESSED / "cells_r8.parquet")
    trips = pd.read_parquet(config.PROCESSED / "trips.parquet")
    hourly = evaluate_hourly(seq, cells)
    trip_res = evaluate_trip_destination(trips, cells)
    hourly.to_parquet(config.PROCESSED / "baseline_hourly_results.parquet", index=False)
    trip_res.to_parquet(config.PROCESSED / "baseline_trip_results.parquet", index=False)
    print("=== hourly next-cell baselines (per-user means) ===")
    print(
        hourly.groupby("predictor")[["n_eval", "top1", "top3", "dist_km"]]
        .mean()
        .round(4)
        .to_string()
    )
    print("\n=== trip destination baselines (per-user means) ===")
    print(
        trip_res.groupby("predictor")[["n_eval", "top1", "top3", "dist_km"]]
        .mean()
        .round(4)
        .to_string()
    )


if __name__ == "__main__":
    run_baselines()
