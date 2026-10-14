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
result tables to data/processed and prints a summary. For datasets whose
hourly panel exceeds memory (100k+ users), ``evaluate_hourly_sharded`` /
``run_baselines(shards=N)`` compute the identical result in two passes:
streaming accumulation of the pooled collective state, then per-user-shard
evaluation -- bit-exact with the monolithic path.
"""

from __future__ import annotations

from pathlib import Path
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


def _fill_ranked(
    ranked: list[int],
    user: str | None,
    user_rank: dict[str, tuple[int, ...]],
    global_rank: tuple[int, ...],
    k: int,
) -> tuple[int, ...]:
    """Pad a partial ranking with the user's (or global) frequency ranking."""
    ur = user_rank.get(user, ()) if user is not None else ()
    seen = set(ranked)
    return _pad(ranked + [c for c in (ur or global_rank) if c not in seen], k)


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
        return _fill_ranked(ranked, user, self._user_rank, self._global_rank, k)

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


class PooledMarkovPredictor:
    """Collective order-k Markov over pooled state accumulated by streaming.

    Same prediction semantics as ``MarkovPredictor(individual=False)``:
    degenerate-order backoff, then user/global frequency fill. The pooled
    transition tables are sorted numpy arrays (ctx key -> next cells ordered
    by count desc / cell asc) instead of Python dicts, so state collected
    across millions of users stays compact. Contexts are big-endian base-V
    integer codes over the user's last ``order`` known cells (V = vocab size).
    """

    def __init__(
        self,
        order: int,
        vocab: int,
        table: pd.DataFrame,
        user_rank: dict[str, tuple[int, ...]],
        global_rank: tuple[int, ...],
    ) -> None:
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.vocab = vocab
        self._keys = table["ctx"].to_numpy(dtype=np.int64)
        self._nxt = table["nxt"].to_numpy(dtype=np.int64)
        self._user_rank = user_rank
        self._global_rank = global_rank

    def _key(self, ctx: tuple[int, ...]) -> int:
        key = 0
        for c in ctx:
            key = key * self.vocab + c
        return key

    def predict_ranked(
        self, context: tuple[int, ...] | list[int], user: str | None = None, k: int = 3
    ) -> tuple[int, ...]:
        ctx = tuple(int(c) for c in context)
        if len(ctx) > self.order:
            ctx = ctx[-self.order :]
        if ctx and UNK not in ctx:
            keys = self._keys
            for j in range(min(len(ctx), self.order), 0, -1):
                key = self._key(ctx[-j:])
                lo = int(np.searchsorted(keys, key, side="left"))
                if lo < len(keys) and keys[lo] == key:
                    hi = int(np.searchsorted(keys, key, side="right"))
                    ranked = self._nxt[lo:hi].tolist()
                    return _fill_ranked(ranked, user, self._user_rank, self._global_rank, k)
        return _fill_ranked([], user, self._user_rank, self._global_rank, k)

    def predict(self, context: tuple[int, ...], user: str | None = None) -> int:
        return self.predict_ranked(context, user, k=1)[0]


class _PairAccumulator:
    """Associative (ctx_key, nxt) -> count accumulator with periodic compaction."""

    _FLUSH_ROWS = 20_000_000

    def __init__(self) -> None:
        self._merged: pd.DataFrame | None = None
        self._parts: list[pd.DataFrame] = []
        self._pending = 0

    def add(self, ctx: np.ndarray, nxt: np.ndarray, cnt: np.ndarray) -> None:
        self._parts.append(pd.DataFrame({"ctx": ctx, "nxt": nxt, "cnt": cnt}))
        self._pending += len(ctx)
        if self._pending >= self._FLUSH_ROWS:
            self._flush()

    def _flush(self) -> None:
        if not self._parts:
            return
        objs = self._parts if self._merged is None else [*self._parts, self._merged]
        df = pd.concat(objs, ignore_index=True)
        self._merged = df.groupby(["ctx", "nxt"], sort=False, as_index=False)["cnt"].sum()
        self._parts = []
        self._pending = 0

    def finalize(self) -> pd.DataFrame:
        """Rows sorted by ctx asc, count desc, next cell asc (ranking order)."""
        self._flush()
        if self._merged is None or self._merged.empty:
            return pd.DataFrame({"ctx": [], "nxt": [], "cnt": []})
        return self._merged.sort_values(
            ["ctx", "cnt", "nxt"], ascending=[True, False, True], kind="stable"
        ).reset_index(drop=True)


def _stream_pooled_state(
    seq_path: Path, test_frac: float, vocab: int, batch_rows: int = 1_000_000
) -> tuple[tuple[int, ...], dict[int, pd.DataFrame], list[str]]:
    """Stream the user-contiguous hourly panel, accumulating pooled predictor state.

    Pass 1 of the sharded path: for every complete user (rows contiguous and
    verified on the fly; id sort order is irrelevant) apply the same per-user
    temporal split as the monolith, then accumulate (a) global known-cell
    counts and (b) pooled order-1..3 transition counts from each user's train
    sequence. Count summation is associative, so the result equals the
    monolithic fit.
    Returns (global_rank, {order: sorted transition table}, sorted users).
    """
    import pyarrow.parquet as pq

    orders = (1, 2, 3)
    if vocab**max(orders) >= 2**62:
        raise NotImplementedError("vocab too large for int64 context encoding")
    powvecs = {
        k: np.array([vocab ** (k - 1 - j) for j in range(k)], dtype=np.int64) for k in orders
    }
    gcounts = np.zeros(vocab, dtype=np.int64)
    acc = {k: _PairAccumulator() for k in orders}
    users: set[str] = set()

    def process(done: pd.DataFrame) -> None:
        nonlocal gcounts
        if done.empty:
            return
        users.update(done["user"].unique().tolist())
        train, _ = temporal_split(done, test_frac)
        known = train.loc[train["cell_idx"] != UNK, "cell_idx"].to_numpy(dtype=np.int64)
        if known.size:
            if known.max() >= vocab:
                raise ValueError("seq_hourly contains cells missing from the cells vocabulary")
            gcounts += np.bincount(known, minlength=vocab)
            for seq in _user_sequences(train).values():
                for k in orders:
                    if seq.size <= k:
                        continue
                    # windows ending at i-1 pair with seq[i] (ctx = seq[i-k:i], nxt = seq[i])
                    keys = np.lib.stride_tricks.sliding_window_view(seq, k)[:-1] @ powvecs[k]
                    nxt = seq[k:]
                    ukeys, inv = np.unique(keys, return_inverse=True)
                    pair = inv.astype(np.int64) * vocab + nxt
                    upair, cnt = np.unique(pair, return_counts=True)
                    acc[k].add(ukeys[upair // vocab], upair % vocab, cnt)

    buffer: pd.DataFrame | None = None
    closed: set[str] = set()
    parquet = pq.ParquetFile(seq_path)
    for record_batch in parquet.iter_batches(batch_size=batch_rows):
        chunk = record_batch.to_pandas()
        buffer = chunk if buffer is None else pd.concat([buffer, chunk], ignore_index=True)
        user_arr = buffer["user"].to_numpy()
        n_blocks = 1 + int((user_arr[1:] != user_arr[:-1]).sum())
        if n_blocks != len(pd.unique(user_arr)):
            raise ValueError(f"{seq_path} is not user-contiguous; rebuild sequences first")
        done_mask = user_arr != user_arr[-1]
        if done_mask.any():
            done_users = set(pd.unique(user_arr[done_mask]))
            if not closed.isdisjoint(done_users):
                raise ValueError(f"{seq_path} is not user-contiguous; rebuild sequences first")
            process(buffer.loc[done_mask])
            closed |= done_users
            buffer = buffer.loc[~done_mask]
    if buffer is not None and not buffer.empty:
        if not closed.isdisjoint(set(pd.unique(buffer["user"].to_numpy()))):
            raise ValueError(f"{seq_path} is not user-contiguous; rebuild sequences first")
        process(buffer)

    nz = np.nonzero(gcounts)[0]
    rank_order = np.lexsort((nz, -gcounts[nz]))
    global_rank = tuple(int(c) for c in nz[rank_order])
    return global_rank, {k: acc[k].finalize() for k in orders}, sorted(users)


def evaluate_hourly_sharded(
    seq_path: Path,
    cells: pd.DataFrame,
    n_shards: int,
    test_frac: float = 0.2,
    batch_rows: int = 1_000_000,
) -> pd.DataFrame:
    """Memory-bounded, bit-exact ``evaluate_hourly`` over a seq_hourly parquet.

    Pass 1 streams the panel once to accumulate pooled collective state
    (global frequency ranking + collective Markov transitions, orders 1-3).
    Pass 2 evaluates user shards: per-user predictors (freq/time/individual
    Markov, global-frequency backoff) are per-user quantities, so fitting
    them on the shard's own rows is exact; collective predictors use the
    pass-1 pooled tables. Output equals the monolithic ``evaluate_hourly``.
    """
    import pyarrow.dataset as pads

    vocab = int(cells["cell_idx"].max()) + 1
    global_rank, tables, users = _stream_pooled_state(seq_path, test_frac, vocab, batch_rows)
    frames: list[pd.DataFrame] = []
    dataset = pads.dataset(seq_path)
    user_arr = np.asarray(users, dtype=object)
    for shard in np.array_split(user_arr, n_shards):
        if len(shard) == 0:
            continue
        seq = dataset.to_table(filter=pads.field("user").isin(shard.tolist())).to_pandas()
        train, test = temporal_split(seq, test_frac)
        predictors = _fit_hourly_predictors(train)
        user_rank, _ = _frequency_ranks(train)
        for pred in predictors.values():
            if isinstance(pred, MarkovPredictor | FrequencyPredictor | TimeConditionedPredictor):
                pred._global_rank = global_rank
        for k in (1, 2, 3):
            predictors[f"markov{k}_col"] = PooledMarkovPredictor(
                order=k, vocab=vocab, table=tables[k], user_rank=user_rank, global_rank=global_rank
            )
        frames.append(_eval_hourly_predictors(train, test, cells, predictors))
        del seq, train, test, predictors
    if not frames:
        return pd.DataFrame(columns=_RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


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


_AnyPredictor = (
    FrequencyPredictor | TimeConditionedPredictor | MarkovPredictor | PooledMarkovPredictor
)


def _predict_ranked(
    pred: _AnyPredictor, history: list[int], user: str, hour: pd.Timestamp
) -> tuple:
    """Dispatch a ranked top-3 prediction for one test row."""
    if isinstance(pred, TimeConditionedPredictor):
        return pred.predict_ranked(user, hour, k=3)
    if isinstance(pred, MarkovPredictor | PooledMarkovPredictor):
        return pred.predict_ranked(tuple(history[-pred.order :]), user, k=3)
    return pred.predict_ranked(user, k=3)


def _fit_hourly_predictors(train: pd.DataFrame) -> dict[str, _AnyPredictor]:
    """Fit the 8 hourly predictors on a per-user chronological train split."""
    predictors: dict[str, _AnyPredictor] = {
        "freq": FrequencyPredictor().fit(train),
        "time": TimeConditionedPredictor().fit(train),
    }
    for k in (1, 2, 3):
        predictors[f"markov{k}"] = MarkovPredictor(order=k, individual=True).fit(train)
        predictors[f"markov{k}_col"] = MarkovPredictor(order=k, individual=False).fit(train)
    return predictors


def _eval_hourly_predictors(
    train: pd.DataFrame,
    test: pd.DataFrame,
    cells: pd.DataFrame,
    predictors: dict[str, _AnyPredictor],
) -> pd.DataFrame:
    """Score fitted predictors over the per-user test split (long result frame)."""
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
    return _eval_hourly_predictors(train, test, cells, _fit_hourly_predictors(train))


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


def run_baselines(processed_dir: Path | None = None, shards: int = 1) -> None:
    """Read the processed parquets, evaluate all baselines, save + print summary.

    ``shards > 1`` switches the hourly evaluation to the memory-bounded
    streaming/sharded path (bit-exact with the monolithic computation);
    the trip-destination evaluation always uses the monolith path.
    """
    pdir = processed_dir or config.PROCESSED
    cells = pd.read_parquet(pdir / "cells_r8.parquet")
    trips_path = pdir / "trips.parquet"
    trips = pd.read_parquet(trips_path) if trips_path.exists() else pd.DataFrame()
    if shards > 1:
        print(f"sharded hourly baselines: {shards} user shards (streaming pass + shard eval)")
        hourly = evaluate_hourly_sharded(pdir / "seq_hourly.parquet", cells, shards)
    else:
        seq = pd.read_parquet(pdir / "seq_hourly.parquet")
        hourly = evaluate_hourly(seq, cells)
    hourly.to_parquet(pdir / "baseline_hourly_results.parquet", index=False)
    if trips.empty:
        print("no trips (grid dataset) -> skipping trip-destination baselines")
        return
    trip_res = evaluate_trip_destination(trips, cells)
    trip_res.to_parquet(pdir / "baseline_trip_results.parquet", index=False)
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
