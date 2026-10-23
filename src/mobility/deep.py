"""Phase 6: deep next-hourly-cell prediction vs Markov baselines (CPU torch).

Three models score ``P(next cell | context cells, target hour-of-week)`` over
hourly location sequences (UNKNOWN hours dropped, gaps kept implicit):

- ``DeepMoveRNN``: cell embedding + LSTM; the last hidden state is concatenated
  with an embedding of the target hour-of-week. This is a DeepMove-style
  (Feng et al., KDD 2018) *temporal* module: we condition on the current
  context + target hour instead of the full historical attention mechanism of
  the original paper.
- ``TemporalTransformer``: causal-masked transformer encoder over the context
  cells with learned positional embeddings; the target hour-of-week embedding
  is added at the query (last) position, whose output feeds the vocab logits.
- ``GraphSeqModel``: a light MobGT homage. Node embeddings are precomputed by
  power iteration of personalized-PageRank-style vectors on the global trip
  transition graph (o_h3_r8 -> d_h3_r8 pooled counts), then frozen; the model
  is a linear head from the last-cell and mean-over-context node embeddings
  plus hour embedding to vocab logits.

Training is plain Adam + CrossEntropyLoss with deterministic manual batching;
``run_deep`` reads the processed parquets, trains/evaluates on the cohort,
writes ``data/processed/deep_results.parquet`` (columns matching the baseline
result tables but with ``model`` instead of ``predictor``) and prints a
side-by-side summary against ``baseline_hourly_results.parquet``.
"""

from __future__ import annotations

import math
import random
import time
from pathlib import Path
from typing import TypedDict, cast

import numpy as np
import pandas as pd
import torch
from torch import nn

from . import config
from .baselines import distance_error_km, topk_accuracy

UNK = config.UNKNOWN
HOURS_PER_WEEK = 168
CONTEXT_LEN = 24
MAX_TRAIN_WINDOWS = 300_000
EVAL_BATCH = 4096
MAX_GRAPH_VOCAB = 40_000  # dense PPR transition matrix is vocab^2 * 8 bytes (40k -> ~12.8 GB)
_RESULT_COLUMNS = ["model", "user", "n_eval", "top1", "top3", "dist_km"]
DEEP_CACHE_DIR = config.ROOT / "data" / "cache" / "deep"


class DeepDataset(TypedDict):
    """Torch-ready windows from ``build_dataset`` (all arrays int64 except split)."""

    contexts: np.ndarray  # (n, context_len)
    targets: np.ndarray  # (n,)
    hours: np.ndarray  # (n,) hour-of-week of the target hour
    user_idx: np.ndarray  # (n,)
    positions: np.ndarray  # (n,) target index within the user's known sequence
    split: np.ndarray  # (n,) bool, True = train
    user_labels: list[str]
    vocab: int


def vocab_size(cells: pd.DataFrame) -> int:
    """Model vocabulary: one logit per known cell_idx (0..max)."""
    return int(cells["cell_idx"].max()) + 1


def _hourofweek(hours: pd.Series) -> np.ndarray:
    """Hour-of-week in 0..167 (Monday 00:00 = 0)."""
    h = pd.to_datetime(hours)
    return (h.dt.dayofweek.to_numpy() * 24 + h.dt.hour.to_numpy()).astype(np.int64)


def build_dataset(
    seq: pd.DataFrame, cells: pd.DataFrame, users: list[str], context_len: int = CONTEXT_LEN
) -> DeepDataset:
    """Windows of ``context_len`` known cells -> next cell, per cohort user.

    For each user the known-cell subsequence is chronological (UNKNOWN rows
    dropped, hour gaps implicit). Every position with ``context_len`` known
    predecessors yields one window; the target keeps its hour-of-week. The
    per-user chronological 80/20 split is over *windows* (first ceil(80%) of
    each user's windows train, the rest test), so training targets always
    precede test targets - no leakage.
    """
    allowed = {str(u) for u in users}
    known = seq.loc[seq["cell_idx"] != UNK].copy()
    known["user"] = known["user"].astype(str)
    known = known.loc[known["user"].isin(allowed)]
    known = known.sort_values(["user", "hour"], kind="stable")
    labels = sorted(known["user"].unique().tolist())
    label_idx = {u: i for i, u in enumerate(labels)}

    ctx_blocks: list[np.ndarray] = []
    tgt_blocks: list[np.ndarray] = []
    hr_blocks: list[np.ndarray] = []
    pos_blocks: list[np.ndarray] = []
    user_blocks: list[np.ndarray] = []
    split_blocks: list[np.ndarray] = []
    for user, g in known.groupby("user", sort=False):
        arr = g["cell_idx"].to_numpy(dtype=np.int64)
        if arr.size <= context_len:
            continue
        win = np.lib.stride_tricks.sliding_window_view(arr, context_len + 1)
        n_win = win.shape[0]
        ctx_blocks.append(np.ascontiguousarray(win[:, :-1]))
        tgt_blocks.append(np.ascontiguousarray(win[:, -1]))
        hr_blocks.append(_hourofweek(g["hour"].iloc[context_len:].reset_index(drop=True)))
        pos_blocks.append(np.arange(context_len, arr.size, dtype=np.int64))
        user_blocks.append(np.full(n_win, label_idx[str(user)], dtype=np.int64))
        n_train = math.ceil(0.8 * n_win)
        split_blocks.append(np.arange(n_win, dtype=np.int64) < n_train)

    return {
        "contexts": (
            np.concatenate(ctx_blocks) if ctx_blocks else np.empty((0, context_len), np.int64)
        ),
        "targets": np.concatenate(tgt_blocks) if tgt_blocks else np.empty(0, np.int64),
        "hours": np.concatenate(hr_blocks) if hr_blocks else np.empty(0, np.int64),
        "user_idx": np.concatenate(user_blocks) if user_blocks else np.empty(0, np.int64),
        "positions": np.concatenate(pos_blocks) if pos_blocks else np.empty(0, np.int64),
        "split": np.concatenate(split_blocks) if split_blocks else np.empty(0, np.bool_),
        "user_labels": labels,
        "vocab": vocab_size(cells),
    }


class DeepMoveRNN(nn.Module):
    """Embedding + LSTM with target-hour conditioning (DeepMove-style temporal module).

    The original DeepMove (Feng et al. 2018) combines a historical-attention
    module with a temporal module; this CPU-friendly variant keeps only the
    temporal part: the LSTM's final hidden state is concatenated with an
    embedding of the target hour-of-week before the vocab projection.
    """

    def __init__(
        self,
        vocab_size: int,
        embed: int = 64,
        hidden: int = 128,
        layers: int = 1,
        hour_dim: int = 16,
    ) -> None:
        super().__init__()
        self.cell_emb = nn.Embedding(vocab_size, embed)
        self.lstm = nn.LSTM(embed, hidden, num_layers=layers, batch_first=True)
        self.hour_emb = nn.Embedding(HOURS_PER_WEEK, hour_dim)
        self.head = nn.Linear(hidden + hour_dim, vocab_size)

    def forward(self, ctx: torch.Tensor, hr: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(self.cell_emb(ctx))
        feats = torch.cat([out[:, -1], self.hour_emb(hr)], dim=1)
        return self.head(feats)


class TemporalTransformer(nn.Module):
    """Causal-masked transformer over context cells; last-token vocab logits.

    Input token = cell embedding projected to ``d_model`` + learned positional
    embedding. The dataset keeps a single hour per window (the target's), so the
    hour-of-week embedding (projected to ``d_model``) is added at the last
    (query) position only.
    """

    def __init__(
        self,
        vocab_size: int,
        embed: int = 64,
        d_model: int = 128,
        heads: int = 4,
        layers: int = 2,
        max_len: int = 48,
        hour_dim: int = 16,
    ) -> None:
        super().__init__()
        self.cell_emb = nn.Embedding(vocab_size, embed)
        self.in_proj = nn.Linear(embed, d_model)
        self.pos_emb = nn.Embedding(max_len, d_model)
        self.hour_emb = nn.Embedding(HOURS_PER_WEEK, hour_dim)
        self.hour_proj = nn.Linear(hour_dim, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model, heads, dim_feedforward=4 * d_model, batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, layers, enable_nested_tensor=False)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, ctx: torch.Tensor, hr: torch.Tensor) -> torch.Tensor:
        n_ctx = ctx.shape[1]
        pos = torch.arange(n_ctx, device=ctx.device)
        x = self.in_proj(self.cell_emb(ctx)) + self.pos_emb(pos)
        hour = self.hour_proj(self.hour_emb(hr)).unsqueeze(1)
        x = torch.cat([x[:, :-1], x[:, -1:] + hour], dim=1)
        mask = torch.triu(torch.full((n_ctx, n_ctx), float("-inf"), device=x.device), diagonal=1)
        y = self.encoder(x, mask=mask, is_causal=True)
        return self.head(y[:, -1])


def graph_node_embeddings(
    trips: pd.DataFrame, cells: pd.DataFrame, d: int = 64, iters: int = 10, teleport: float = 0.1
) -> torch.Tensor:
    """Frozen (vocab, d) node embeddings from power iteration on the trip graph.

    Pooled o_h3_r8 -> d_h3_r8 trip counts (unmappable endpoints dropped) give a
    row-normalized transition matrix over cells (dangling rows uniform). For
    ``min(d, vocab)`` seed cells (highest trip mass, ties by cell_idx) a
    personalized-PageRank vector is power-iterated for ``iters`` steps with
    ``teleport`` probability back to its seed; vectors are stacked column-wise
    into the embedding matrix and each column normalized to sum to 1.
    """
    n_cells = vocab_size(cells)
    h3_to_idx = {str(h): int(i) for h, i in zip(cells["h3"], cells["cell_idx"], strict=True)}
    o = trips["o_h3_r8"].astype(str).map(h3_to_idx)
    dd = trips["d_h3_r8"].astype(str).map(h3_to_idx)
    ok = o.notna() & dd.notna()
    trans = np.zeros((n_cells, n_cells), dtype=np.float64)
    np.add.at(trans, (o[ok].to_numpy(dtype=np.int64), dd[ok].to_numpy(dtype=np.int64)), 1.0)
    row_sums = trans.sum(axis=1)
    dangling = row_sums == 0
    safe = np.where(dangling, 1.0, row_sums)
    p_row = np.where(dangling[:, None], 1.0 / n_cells, trans / safe[:, None])

    mass = trans.sum(axis=0) + trans.sum(axis=1)
    seeds = sorted(range(n_cells), key=lambda c: (-mass[c], c))[: min(d, n_cells)]
    n_seeds = len(seeds)
    seed_mask = np.zeros((n_cells, n_seeds), dtype=np.float64)
    seed_mask[seeds, np.arange(n_seeds)] = 1.0

    emb = seed_mask.copy()
    pt = np.ascontiguousarray(p_row.T)
    for _ in range(iters):
        emb = teleport * seed_mask + (1.0 - teleport) * (emb.T @ pt).T
    emb /= emb.sum(axis=0, keepdims=True)
    return torch.from_numpy(np.ascontiguousarray(emb)).float()


class GraphSeqModel(nn.Module):
    """Light MobGT homage: frozen graph node embeddings + linear head to vocab.

    Context cells are mapped through the frozen power-iteration node embeddings
    (see ``graph_node_embeddings``); the last cell's embedding and the
    mean-over-context embedding are concatenated with the target hour-of-week
    embedding and linearly projected to vocab logits (the bilinear-style MobGT
    scoring, simplified to a linear head).
    """

    def __init__(self, vocab_size: int, node_emb: torch.Tensor, hour_dim: int = 16) -> None:
        super().__init__()
        if node_emb.shape[0] != vocab_size:
            raise ValueError(
                f"node_emb has {node_emb.shape[0]} rows, expected vocab_size={vocab_size}"
            )
        self.node_emb = nn.Embedding.from_pretrained(node_emb.detach().clone().float(), freeze=True)
        self.hour_emb = nn.Embedding(HOURS_PER_WEEK, hour_dim)
        self.head = nn.Linear(2 * node_emb.shape[1] + hour_dim, vocab_size)

    def forward(self, ctx: torch.Tensor, hr: torch.Tensor) -> torch.Tensor:
        ctx_emb = self.node_emb(ctx)
        feats = torch.cat([ctx_emb[:, -1], ctx_emb.mean(dim=1), self.hour_emb(hr)], dim=1)
        return self.head(feats)


def _seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_model(
    model: nn.Module,
    train_ctx: np.ndarray,
    train_tgt: np.ndarray,
    train_hr: np.ndarray,
    epochs: int = 3,
    lr: float = 1e-3,
    batch: int = 256,
    seed: int = 0,
) -> tuple[nn.Module, list[float]]:
    """Adam + CrossEntropyLoss with deterministic manual batching.

    If there are more than ``MAX_TRAIN_WINDOWS`` training windows they are
    subsampled deterministically (seeded permutation, first
    ``MAX_TRAIN_WINDOWS`` kept). Returns ``(model, per-batch train loss log)``.
    """
    _seed_all(seed)
    ctx = torch.from_numpy(np.ascontiguousarray(train_ctx, dtype=np.int64)).long()
    tgt = torch.from_numpy(np.ascontiguousarray(train_tgt, dtype=np.int64)).long()
    hr = torch.from_numpy(np.ascontiguousarray(train_hr, dtype=np.int64)).long()
    n = ctx.shape[0]
    if n > MAX_TRAIN_WINDOWS:
        keep = torch.randperm(n, generator=torch.Generator().manual_seed(seed))[:MAX_TRAIN_WINDOWS]
        ctx, tgt, hr = ctx[keep], tgt[keep], hr[keep]
        n = MAX_TRAIN_WINDOWS
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    losses: list[float] = []
    model.train()
    for epoch in range(epochs):
        perm = torch.randperm(n, generator=torch.Generator().manual_seed(seed + epoch))
        for start in range(0, n, batch):
            idx = perm[start : start + batch]
            loss = loss_fn(model(ctx[idx], hr[idx]), tgt[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach()))
    return model, losses


def evaluate_deep(
    model: nn.Module,
    ctx: np.ndarray,
    tgt: np.ndarray,
    hr: np.ndarray,
    cells: pd.DataFrame,
    k: tuple[int, ...] = (1, 3),
) -> dict[str, float | int]:
    """Batched top-k ranking -> pooled top-k accuracy + mean distance error (km)."""
    max_k = max(k)
    ctx_t = torch.from_numpy(np.ascontiguousarray(ctx, dtype=np.int64)).long()
    hr_t = torch.from_numpy(np.ascontiguousarray(hr, dtype=np.int64)).long()
    ranked_batches: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, ctx_t.shape[0], EVAL_BATCH):
            logits = model(ctx_t[start : start + EVAL_BATCH], hr_t[start : start + EVAL_BATCH])
            ranked_batches.append(torch.topk(logits, k=max_k, dim=1).indices.numpy())
    ranked = (
        np.concatenate(ranked_batches) if ranked_batches else np.empty((0, max_k), dtype=np.int64)
    )
    y = np.asarray(tgt, dtype=np.int64)
    accs = cast("dict[int, float]", topk_accuracy(y, ranked, tuple(k)))
    dist = distance_error_km(y, ranked[:, 0], cells)
    finite = dist[np.isfinite(dist)]
    out: dict[str, float | int] = {"n_eval": int(y.size)}
    for kk in k:
        out[f"top{kk}"] = float(accs[kk])
    out["dist_km"] = float(finite.mean()) if finite.size else float("nan")
    return out


def _per_user_eval(
    model: nn.Module, data: DeepDataset, cells: pd.DataFrame, name: str
) -> list[dict]:
    """Evaluate ``model`` on each user's test windows (one result row per user)."""
    test_mask = ~data["split"]
    rows: list[dict] = []
    for u, user in enumerate(data["user_labels"]):
        m = test_mask & (data["user_idx"] == u)
        if not m.any():
            continue
        res = evaluate_deep(model, data["contexts"][m], data["targets"][m], data["hours"][m], cells)
        rows.append(
            {
                "model": name,
                "user": user,
                "n_eval": int(res["n_eval"]),
                "top1": float(res["top1"]),
                "top3": float(res["top3"]),
                "dist_km": float(res["dist_km"]),
            }
        )
    return rows


def run_deep(epochs: int = 3, processed_dir: Path | None = None) -> None:
    """Train + evaluate the three models on the cohort, save results, print summary."""
    t_start = time.perf_counter()
    pdir = processed_dir or config.PROCESSED
    cache_dir = pdir / "cache" / "deep"
    seq = pd.read_parquet(pdir / "seq_hourly.parquet")
    cells = pd.read_parquet(pdir / "cells_r8.parquet")
    trips_path = pdir / "trips.parquet"
    trips = pd.read_parquet(trips_path) if trips_path.exists() else pd.DataFrame()
    cohort = pd.read_parquet(pdir / "cohort.parquet")
    baseline_path = pdir / "baseline_hourly_results.parquet"
    baselines = pd.read_parquet(baseline_path) if baseline_path.exists() else pd.DataFrame()

    data = build_dataset(seq, cells, [str(u) for u in cohort["user"]], context_len=CONTEXT_LEN)
    n_train = int(data["split"].sum())
    n_test = int((~data["split"]).sum())
    print(
        f"dataset: vocab={data['vocab']} users={len(data['user_labels'])} "
        f"windows={data['targets'].size} (train={n_train}, test={n_test})"
    )

    models: dict[str, nn.Module] = {
        "deepmove_rnn": DeepMoveRNN(int(data["vocab"])),
        "temporal_transformer": TemporalTransformer(int(data["vocab"])),
    }
    if len(trips) and len(cells) > MAX_GRAPH_VOCAB:
        print(
            f"vocab {len(cells)} > {MAX_GRAPH_VOCAB}; skipping GraphSeq "
            "(dense PPR transition matrix would need "
            f"{len(cells) ** 2 * 8 / 1e9:.0f} GB)"
        )
    elif len(trips):
        t0 = time.perf_counter()
        node_emb = graph_node_embeddings(trips, cells, d=64, iters=10, teleport=0.1)
        print(f"graph node embeddings: {tuple(node_emb.shape)} in {time.perf_counter() - t0:.1f}s")
        models["graphseq"] = GraphSeqModel(int(data["vocab"]), node_emb)
    else:
        print("no trips; skipping GraphSeq (needs the trip transition graph)")
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for name, model in models.items():
        t0 = time.perf_counter()
        model, losses = train_model(
            model, data["contexts"][data["split"]], data["targets"][data["split"]],
            data["hours"][data["split"]], epochs=epochs, seed=0,
        )
        torch.save(model.state_dict(), cache_dir / f"{name}.pt")
        user_rows = _per_user_eval(model, data, cells, name)
        rows.extend(user_rows)
        m = pd.DataFrame(user_rows)
        print(
            f"{name}: {len(losses)} batches, final loss {losses[-1]:.4f} "
            f"({time.perf_counter() - t0:.1f}s) | mean top1 {m['top1'].mean():.4f} "
            f"top3 {m['top3'].mean():.4f} dist_km {m['dist_km'].mean():.1f}"
        )

    results = pd.DataFrame(rows, columns=_RESULT_COLUMNS)
    results.to_parquet(pdir / "deep_results.parquet", index=False)

    if len(baselines):
        combined = pd.concat(
            [
                baselines.rename(columns={"predictor": "model"})[
                    ["model", "top1", "top3", "dist_km"]
                ],
                results[["model", "top1", "top3", "dist_km"]],
            ]
        )
        summary = combined.groupby("model")[["top1", "top3", "dist_km"]].mean().round(4)
        print("\n=== hourly next-cell: baselines vs deep (per-user means) ===")
        print(summary.to_string())
    else:
        print("\n(no baseline_hourly_results.parquet; deep-only summary above)")
    print(f"\ntotal: {time.perf_counter() - t_start:.1f}s")
    print(f"results -> {pdir / 'deep_results.parquet'}")
    print(f"model state_dicts -> {cache_dir}/<model>.pt")


if __name__ == "__main__":
    run_deep()
