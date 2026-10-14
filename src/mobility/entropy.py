"""Entropy and Fano predictability per Song et al. 2010 (Science, SOM S4).

S_rand     = log2 N                                    (random entropy)
S_unc      = -sum p_i log2 p_i                         (uncorrelated entropy)
S_actual   = (n / sum_i Lambda(i)) * log2 n            (Kontoyiannis et al. 1998)
Pi_*       solves  H(Pi) + (1 - Pi) * log2(N - 1) = S  (Fano bound inversion)

Unknown hours (config.UNKNOWN sentinel) are dropped before all estimates.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def _known(seq: np.ndarray, unknown: int) -> np.ndarray:
    arr = np.asarray(seq).ravel()
    return arr[arr != unknown]


def random_entropy(cell_idx: np.ndarray, unknown: int = config.UNKNOWN) -> float:
    """S_rand = log2 N over distinct known cells; nan when no known cells."""
    known = _known(cell_idx, unknown)
    n = np.unique(known).size
    if n < 1:
        return np.nan
    return float(math.log2(n))


def uncorrelated_entropy(cell_idx: np.ndarray, unknown: int = config.UNKNOWN) -> float:
    """S_unc = -sum p_i log2 p_i over known-cell visitation frequencies."""
    known = _known(cell_idx, unknown)
    n = known.size
    if n < 1:
        return np.nan
    _, counts = np.unique(known, return_counts=True)
    p = counts / n
    return float(-(p * np.log2(p)).sum())


def lz_entropy(seq: np.ndarray, unknown: int = config.UNKNOWN) -> float:
    """S_actual via the Kontoyiannis et al. (1998) Lempel-Ziv estimator.

    Lambda(i) is the length of the shortest contiguous subsequence starting at
    i that does not occur as a contiguous block fully inside the prefix
    seq[0:i]; S = n log2 n / sum_i Lambda(i). Matching uses str.find against
    the exact prefix (C-speed two-way search, no extra memory): O(n) expected
    match length is O(log n) on stochastic sequences, so the practical cost is
    a few seconds for n ~ 5e4; worst case O(n^2) C-level character scans on
    pathological long-repeat inputs. When every substring up to the end of the
    sequence matches, Lambda(i) is capped at n - i + 1 (boundary convention).
    """
    known = _known(seq, unknown)
    n = known.size
    if n < 1:
        return np.nan
    if n == 1 or np.unique(known).size == 1:
        return 0.0  # constant sequence: the estimator's limit is exactly 0
    _, codes = np.unique(known, return_inverse=True)
    s = "".join(map(chr, codes.tolist()))
    total = 0.0
    find = s.find
    for i in range(n):
        length = 1
        while i + length <= n and find(s[i:i + length], 0, i) != -1:
            length += 1
        total += length
    return float(n * math.log2(n) / total)


def fano_predictability(s: float, n: int) -> float:
    """Solve H(Pi) + (1 - Pi) log2(n - 1) = s for Pi in [1/n, 1] by bisection.

    The left-hand side decreases monotonically from log2(n) at Pi = 1/n to 0 at
    Pi = 1. Degenerate cases (n < 2, non-finite s) return nan; s outside
    [0, log2 n] is clipped into range.
    """
    if n < 2 or not np.isfinite(s):
        return np.nan
    s = float(np.clip(s, 0.0, math.log2(n)))

    def lhs(p: float) -> float:
        if p <= 0.0 or p >= 1.0:
            return (1.0 - p) * math.log2(n - 1)
        h = -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)
        return h + (1.0 - p) * math.log2(n - 1)

    lo, hi = 1.0 / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if lhs(mid) > s:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def analyze_user(cell_idx_seq: np.ndarray) -> dict:
    """All seven Song et al. quantities for one user's known/unknown sequence."""
    seq = np.asarray(cell_idx_seq).ravel()
    known = seq[seq != config.UNKNOWN]
    n = int(np.unique(known).size)
    out = {
        "N": n,
        "S_rand": random_entropy(seq),
        "S_unc": uncorrelated_entropy(seq),
        "S_actual": lz_entropy(seq),
    }
    for key in ("S_rand", "S_unc", "S_actual"):
        out[f"Pi_{key.split('_')[1]}"] = fano_predictability(out[key], n)
    return out


def analyze_all(seq_path: str | Path | None = None) -> pd.DataFrame:
    """Per-user entropy/predictability table from seq_hourly.parquet."""
    path = Path(seq_path) if seq_path is not None else config.PROCESSED / "seq_hourly.parquet"
    seq = pd.read_parquet(path, columns=["user", "hour", "cell_idx"]).sort_values(
        ["user", "hour"], kind="stable"
    )
    rows = [
        {"user": user, **analyze_user(grp["cell_idx"].to_numpy())}
        for user, grp in seq.groupby("user", sort=True)
    ]
    return pd.DataFrame(rows)


def run_entropy(processed_dir: Path | None = None) -> pd.DataFrame:
    """analyze_all on a dataset's seq_hourly.parquet -> entropy.parquet."""
    pdir = processed_dir or config.PROCESSED
    table = analyze_all(pdir / "seq_hourly.parquet")
    table.to_parquet(pdir / "entropy.parquet", index=False)
    print(table.describe().to_string())
    return table


if __name__ == "__main__":
    run_entropy()
