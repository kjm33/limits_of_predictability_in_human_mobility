"""Hourly sequence construction, vocabulary, and encoding tests (synthetic)."""

import h3
import numpy as np
import pandas as pd
import pytest

from mobility import config
from mobility.sequences import (
    build_sequences,
    cell_vocab,
    encode_sequences,
    hourly_sequences,
    user_q,
)

A = h3.latlng_to_cell(39.9042, 116.4074, 8)
B = sorted(set(h3.grid_disk(A, 1)) - {A})[0]
BASE = pd.Timestamp("2021-03-01 00:00:00")


def _at(hour: int, minute: int = 0) -> pd.Timestamp:
    return BASE + pd.Timedelta(hours=hour, minutes=minute)


def _points(rows: list[tuple[str, pd.Timestamp, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["user", "ts", "cell"])
    latlng = [h3.cell_to_latlng(c) for c in df["cell"]]
    df["lat"] = [la for la, _ in latlng]
    df["lon"] = [lo for _, lo in latlng]
    return df


@pytest.fixture()
def points() -> pd.DataFrame:
    rows = [
        # user 00: hour 0-1 in A, hour 2 empty, hour 3 has 3x A + 1x B,
        # hour 4 ties 1x A (05') vs 1x B (25') -> last point (B) wins, hour 5 in A
        ("00", _at(0, 10), A),
        ("00", _at(0, 40), A),
        ("00", _at(1, 30), A),
        ("00", _at(3, 5), A),
        ("00", _at(3, 15), A),
        ("00", _at(3, 20), B),
        ("00", _at(3, 35), A),
        ("00", _at(4, 5), A),
        ("00", _at(4, 25), B),
        ("00", _at(5, 50), A),
        # user 01: starts at hour 2, hour 3 empty
        ("01", _at(2, 0), B),
        ("01", _at(4, 10), A),
    ]
    return _points(rows)


def test_full_hourly_coverage(points):
    hourly = hourly_sequences(points)
    u0 = hourly[hourly["user"] == "00"]
    assert list(u0["hour"]) == [_at(h) for h in range(6)]
    u1 = hourly[hourly["user"] == "01"]
    assert list(u1["hour"]) == [_at(h) for h in range(2, 5)]
    assert list(hourly.columns) == ["user", "hour", "h3"]
    assert hourly[["user", "hour"]].equals(hourly[["user", "hour"]].sort_values(["user", "hour"]))


def test_most_frequent_cell_wins(points):
    hourly = hourly_sequences(points).set_index(["user", "hour"])
    assert hourly.loc[("00", _at(3)), "h3"] == A  # 3x A beats 1x B


def test_tie_broken_by_last_point(points):
    hourly = hourly_sequences(points).set_index(["user", "hour"])
    assert hourly.loc[("00", _at(4)), "h3"] == B  # 1-1 tie, B logged last (25' vs 05')


def test_empty_hours_are_null(points):
    hourly = hourly_sequences(points).set_index(["user", "hour"])
    assert pd.isna(hourly.loc[("00", _at(2)), "h3"])
    assert pd.isna(hourly.loc[("01", _at(3)), "h3"])


def test_vocab_deterministic_alphabetical(points):
    hourly = hourly_sequences(points)
    v1 = cell_vocab(hourly["h3"].dropna())
    v2 = cell_vocab(hourly["h3"].dropna())
    pd.testing.assert_frame_equal(v1, v2)
    assert list(v1.columns) == ["cell_idx", "h3", "lat", "lon"]
    assert list(v1["h3"]) == sorted({A, B})
    assert list(v1["cell_idx"]) == [0, 1]
    for row in v1.itertuples():
        la, lo = h3.cell_to_latlng(row.h3)
        assert row.lat == pytest.approx(la)
        assert row.lon == pytest.approx(lo)


def test_encode_unknown_hours(points):
    hourly = hourly_sequences(points)
    vocab = cell_vocab(hourly["h3"].dropna())
    enc = encode_sequences(hourly, vocab)
    assert enc["cell_idx"].dtype == np.dtype("int64")
    assert enc.loc[(enc["user"] == "00") & (enc["hour"] == _at(2)), "cell_idx"].item() == (
        config.UNKNOWN
    )
    assert enc.loc[(enc["user"] == "01") & (enc["hour"] == _at(3)), "cell_idx"].item() == (
        config.UNKNOWN
    )
    known = enc[enc["cell_idx"] != config.UNKNOWN]
    vocab_map = dict(zip(vocab["h3"], vocab["cell_idx"], strict=True))
    assert all(
        vocab_map[h] == c
        for h, c in zip(known["h3"], known["cell_idx"], strict=True)
    )


def test_q_fraction(points):
    hourly = hourly_sequences(points)
    enc = encode_sequences(hourly, cell_vocab(hourly["h3"].dropna()))
    q = user_q(enc).set_index("user")
    assert q.loc["00", "n_hours"] == 6
    assert q.loc["00", "n_known"] == 5
    assert q.loc["00", "q"] == pytest.approx(1 / 6)
    assert q.loc["01", "n_hours"] == 3
    assert q.loc["01", "n_known"] == 2
    assert q.loc["01", "q"] == pytest.approx(1 / 3)
    assert q.loc["00", "first_hour"] == _at(0)
    assert q.loc["00", "last_hour"] == _at(5)
    assert q.loc["01", "first_hour"] == _at(2)
    assert q.loc["01", "last_hour"] == _at(4)


def test_res_parameter_changes_cells(points):
    hourly8 = hourly_sequences(points, res=8)
    assert all(h3.get_resolution(c) == 8 for c in hourly8["h3"].dropna())
    hourly9 = hourly_sequences(points, res=9)
    assert all(h3.get_resolution(c) == 9 for c in hourly9["h3"].dropna())


def test_min_points_per_user_filters_before_panel(points, tmp_path, capsys):
    # user 00 has 10 points, user 01 has 2 -> threshold 3 keeps only 00
    points_path = tmp_path / "points.parquet"
    points.to_parquet(points_path, index=False)
    build_sequences(points_path, processed_dir=tmp_path, min_points_per_user=3)

    out = capsys.readouterr().out
    assert "keeping 1 of 2 users" in out
    seq = pd.read_parquet(tmp_path / "seq_hourly.parquet")
    assert set(seq["user"]) == {"00"}
    q = pd.read_parquet(tmp_path / "seq_q.parquet")
    assert set(q["user"]) == {"00"}
    vocab = pd.read_parquet(tmp_path / "cells_r8.parquet")
    assert not vocab.empty  # vocabulary built from surviving user only


def test_min_points_none_keeps_all_users(points, tmp_path):
    points_path = tmp_path / "points.parquet"
    points.to_parquet(points_path, index=False)
    build_sequences(points_path, processed_dir=tmp_path)
    seq = pd.read_parquet(tmp_path / "seq_hourly.parquet")
    assert set(seq["user"]) == {"00", "01"}
