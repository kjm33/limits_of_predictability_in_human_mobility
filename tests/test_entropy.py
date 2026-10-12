"""Entropy / predictability tests on synthetic sequences (Song et al. 2010)."""

import math

import numpy as np
import pytest

from mobility import config
from mobility.entropy import (
    analyze_user,
    fano_predictability,
    lz_entropy,
    random_entropy,
    uncorrelated_entropy,
)


def test_all_same_sequence():
    seq = np.full(200, 7)
    assert random_entropy(seq) == 0.0
    assert uncorrelated_entropy(seq) == 0.0
    assert lz_entropy(seq) == 0.0
    assert fano_predictability(0.0, 5) == pytest.approx(1.0)


def test_alternating_abab():
    seq = np.array([0, 1] * 4)
    assert uncorrelated_entropy(seq) == pytest.approx(1.0)
    # Exact Kontoyiannis on short periodic sequences sits just above 1 bit.
    assert lz_entropy(seq) == pytest.approx(1.0, abs=0.15)


def test_periodic_abc_below_uncorrelated_bound():
    seq = np.array([0, 1, 2] * 2)
    # The uncorrelated bound log2(3) is the ceiling; the LZ estimate of a
    # deterministic periodic sequence stays strictly below it (phase-aligned
    # repeats inflate prefix matches, so ~1.3 rather than log2(3) at n=6).
    s = lz_entropy(seq)
    assert s == pytest.approx(math.log2(3), abs=0.35)
    assert s < math.log2(3)


def test_iid_uniform_converges_to_log2_k():
    rng = np.random.default_rng(42)
    k, n = 8, 50_000
    seq = rng.integers(0, k, n)
    assert uncorrelated_entropy(seq) == pytest.approx(math.log2(k), rel=0.01)
    # Kontoyiannis has a small negative finite-n bias (~-5% at n=5e4, k=8).
    assert lz_entropy(seq) == pytest.approx(math.log2(k), rel=0.10)


def test_lz_shift_invariance():
    assert lz_entropy(np.array([0, 1] * 20)) == pytest.approx(lz_entropy(np.array([1, 0] * 20)))


def test_lz_drops_unknowns():
    seq = np.array([0, -1, 0, 1, 0, -1, 1])
    assert lz_entropy(seq) == pytest.approx(lz_entropy(np.array([0, 0, 1, 0, 1])))


def test_monotonicity_on_realistic_sequence():
    rng = np.random.default_rng(7)
    # Two weeks of a stylized 24h routine (home/sleep, commute, work, lunch)
    # with occasional exploration and missing hours.
    routine = [0, 0, 1, 2, 2, 3, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    seq = np.array(
        [routine[i % 24] if rng.random() > 0.05 else rng.integers(0, 30) for i in range(24 * 14)]
    )
    s_rand = random_entropy(seq)
    s_unc = uncorrelated_entropy(seq)
    s_act = lz_entropy(seq)
    assert s_act <= s_unc + 1e-9 <= s_rand + 1e-9


def test_fano_extremes_and_monotonicity():
    n = 10
    assert fano_predictability(0.0, n) == pytest.approx(1.0)
    assert fano_predictability(math.log2(n), n) == pytest.approx(1.0 / n)
    pis = [fano_predictability(s, n) for s in np.linspace(0.0, math.log2(n), 25)]
    assert all(a > b for a, b in zip(pis, pis[1:], strict=False))  # monotone decreasing in s
    assert np.isnan(fano_predictability(1.0, 1))
    assert np.isnan(fano_predictability(np.nan, 10))


def test_fano_root_residual():
    def h2(p: float) -> float:
        if p <= 0.0 or p >= 1.0:
            return 0.0
        return -p * math.log2(p) - (1 - p) * math.log2(1 - p)

    for n in (2, 3, 10, 97):
        for s in np.linspace(0.0, math.log2(n), 11):
            pi = fano_predictability(s, n)
            assert h2(pi) + (1 - pi) * math.log2(n - 1) == pytest.approx(s, abs=1e-8)
            assert 1.0 / n <= pi <= 1.0


def test_empty_and_unknown_edge_cases():
    assert np.isnan(random_entropy(np.array([config.UNKNOWN] * 4)))
    assert np.isnan(uncorrelated_entropy(np.array([], dtype=int)))
    assert np.isnan(lz_entropy(np.array([config.UNKNOWN])))
    assert lz_entropy(np.array([5, config.UNKNOWN, 5])) == 0.0
    out = analyze_user(np.array([1, 1, 1]))
    assert out["N"] == 1
    assert out["S_rand"] == 0.0
    assert np.isnan(out["Pi_actual"])  # n < 2 is degenerate for the Fano bound
