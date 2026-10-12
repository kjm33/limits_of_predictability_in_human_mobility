import h3
import numpy as np
import pandas as pd
import pytest
import torch

from mobility import config
from mobility.deep import (
    DeepMoveRNN,
    GraphSeqModel,
    TemporalTransformer,
    build_dataset,
    evaluate_deep,
    graph_node_embeddings,
    train_model,
)

UNK = config.UNKNOWN
BASE_CELL = h3.latlng_to_cell(39.9, 116.4, 8)
H3_CELLS = sorted(h3.grid_disk(BASE_CELL, 2))[:10]  # vocab of 10 real r8 cells
USERS = ["u0", "u1", "u2"]


def cells_frame() -> pd.DataFrame:
    rows = []
    for i, cell in enumerate(H3_CELLS):
        lat, lon = h3.cell_to_latlng(cell)
        rows.append({"cell_idx": i, "h3": cell, "lat": lat, "lon": lon})
    return pd.DataFrame(rows)


def cycle_seq(n_hours: int = 300, unk_every: int | None = 11) -> pd.DataFrame:
    """Each user cycles deterministically through the 10 cells, offset per user."""
    hours = pd.date_range("2020-01-01", periods=n_hours, freq="h")
    frames = []
    for u, user in enumerate(USERS):
        vals = [(t + 2 * u) % 10 for t in range(n_hours)]
        if unk_every:
            vals[::unk_every] = [UNK] * len(vals[::unk_every])
        frames.append(pd.DataFrame({"user": user, "hour": hours, "h3": None, "cell_idx": vals}))
    return pd.concat(frames, ignore_index=True)


def cycle_trips(n_trips: int = 200) -> pd.DataFrame:
    """Minimal trip table: consecutive-cell transitions for the pooled graph."""
    return pd.DataFrame(
        {
            "o_h3_r8": [H3_CELLS[k % 10] for k in range(n_trips)],
            "d_h3_r8": [H3_CELLS[(k + 1) % 10] for k in range(n_trips)],
        }
    )


def train_seq(n_hours: int = 200) -> pd.DataFrame:
    """Clean (no UNKNOWN) cycles - loss-decrease training fixture."""
    return cycle_seq(n_hours=n_hours, unk_every=None)


def test_build_dataset_shapes_and_dtypes():
    tiny = pd.DataFrame(
        {
            "user": "u3_tiny",
            "hour": pd.date_range("2020-01-01", periods=10, freq="h"),
            "h3": None,
            "cell_idx": [*range(9), UNK],
        }
    )
    seq = pd.concat([cycle_seq(), tiny], ignore_index=True)
    data = build_dataset(seq, cells_frame(), USERS + ["u3_tiny"], context_len=24)
    # 300 hours - ceil(300/11)=28 UNKNOWN -> 272 known -> 248 windows per cohort user
    assert data["contexts"].shape == (3 * 248, 24)
    assert data["targets"].shape == (248 * 3,)
    for key in ("hours", "user_idx", "positions"):
        assert data[key].shape == (248 * 3,) and data[key].dtype == np.int64
    assert data["contexts"].dtype == np.int64
    assert data["split"].dtype == np.bool_
    assert data["vocab"] == 10
    assert data["user_labels"] == USERS + ["u3_tiny"]
    # u3_tiny: 9 known cells <= context_len -> no windows
    assert set(np.unique(data["user_idx"]).tolist()) == {0, 1, 2}
    assert ((data["contexts"] != UNK).all() and (data["targets"] != UNK).all())
    assert (data["hours"] >= 0).all() and (data["hours"] < 168).all()
    # 2020-01-01 is a Wednesday; u0's 25th known hour (offset by UNKNOWN rows) is the first target
    u0_known = seq.loc[(seq["user"] == "u0") & (seq["cell_idx"] != UNK)]
    u0_known = u0_known.sort_values("hour", kind="stable")
    first_target = u0_known["hour"].iloc[24]
    assert data["hours"][0] == first_target.dayofweek * 24 + first_target.hour


def test_build_dataset_split_no_leakage():
    seq = cycle_seq()
    data = build_dataset(seq, cells_frame(), USERS, context_len=24)
    known = seq.loc[seq["cell_idx"] != UNK]
    for u, user in enumerate(data["user_labels"]):
        m = data["user_idx"] == u
        tr, te = data["split"][m], ~data["split"][m]
        n_win = int(m.sum())
        n_train = int(np.ceil(0.8 * n_win))
        assert tr.sum() == n_train and te.sum() == n_win - n_train
        # window-end positions: every train target strictly precedes every test target
        assert data["positions"][m][tr].max() < data["positions"][m][te].min()
        # same check on wall-clock target hours
        user_known = known.loc[known["user"] == user].sort_values("hour", kind="stable")
        hours = user_known["hour"].to_numpy()
        train_hours = hours[data["positions"][m][tr]]
        test_hours = hours[data["positions"][m][te]]
        assert train_hours.max() < test_hours.min()
        # contexts are the known cells immediately preceding each target
        cells_arr = user_known["cell_idx"].to_numpy()
        j = int(np.flatnonzero(te)[0])
        np.testing.assert_array_equal(data["contexts"][m][j], cells_arr[j : j + 24])
        np.testing.assert_array_equal(data["targets"][m][j], cells_arr[j + 24])


@pytest.mark.parametrize(
    "factory",
    [
        lambda v: DeepMoveRNN(v, embed=32, hidden=64),
        lambda v: TemporalTransformer(v, embed=32, d_model=64, heads=4, layers=2),
    ],
    ids=["deepmove", "transformer"],
)
def test_sequence_model_loss_decreases(factory):
    data = build_dataset(train_seq(), cells_frame(), USERS, context_len=24)
    model, losses = train_model(
        factory(data["vocab"]),
        data["contexts"][data["split"]],
        data["targets"][data["split"]],
        data["hours"][data["split"]],
        epochs=1,
        lr=5e-3,
        batch=64,
        seed=0,
    )
    assert len(losses) > 1 and all(np.isfinite(losses))
    assert losses[-1] < losses[0]  # deterministic cycles are learnable within 1 epoch


def test_graphseq_loss_decreases():
    cells = cells_frame()
    data = build_dataset(train_seq(), cells, USERS, context_len=24)
    emb = graph_node_embeddings(cycle_trips(), cells, d=8, iters=5)
    model, losses = train_model(
        GraphSeqModel(data["vocab"], emb),
        data["contexts"][data["split"]],
        data["targets"][data["split"]],
        data["hours"][data["split"]],
        epochs=1,
        lr=5e-3,
        batch=64,
        seed=0,
    )
    assert all(np.isfinite(losses))
    assert losses[-1] < losses[0]


def test_graph_node_embeddings_power_iteration_converges():
    cells = cells_frame()
    emb = graph_node_embeddings(cycle_trips(), cells, d=4, iters=10)
    assert emb.shape == (10, 4) and emb.dtype == torch.float32
    assert torch.isfinite(emb).all() and (emb >= 0).all()
    col_sums = emb.sum(axis=0)
    assert torch.allclose(col_sums, torch.ones(4), atol=1e-9)  # probabilities sum to 1
    # frozen embeddings are deterministic
    emb2 = graph_node_embeddings(cycle_trips(), cells, d=4, iters=10)
    assert torch.equal(emb, emb2)


def test_train_model_deterministic_seeding():
    data = build_dataset(train_seq(), cells_frame(), USERS, context_len=24)
    args = (
        data["contexts"][data["split"]],
        data["targets"][data["split"]],
        data["hours"][data["split"]],
    )

    def run_once() -> list[float]:
        torch.manual_seed(7)  # also fixes the model init inside run_once
        np.random.seed(7)
        _, losses = train_model(DeepMoveRNN(10, embed=32, hidden=64), *args, epochs=1, seed=7)
        return losses

    assert run_once() == run_once()


def test_evaluate_deep_sane_and_learns_cycle():
    cells = cells_frame()
    # gapless cycle: the next cell is fully determined by the context, so a
    # trained model should score near-perfectly (UNKNOWN gaps would make some
    # targets ambiguous even in principle)
    data = build_dataset(cycle_seq(n_hours=300, unk_every=None), cells, USERS, context_len=24)
    model, _ = train_model(
        DeepMoveRNN(10, embed=32, hidden=64),
        data["contexts"][data["split"]],
        data["targets"][data["split"]],
        data["hours"][data["split"]],
        epochs=8,
        lr=1e-2,
        seed=0,
    )
    test = ~data["split"]
    res = evaluate_deep(
        model, data["contexts"][test], data["targets"][test], data["hours"][test], cells
    )
    assert set(res) == {"n_eval", "top1", "top3", "dist_km"}
    assert res["n_eval"] == int(test.sum())
    assert 0.0 <= res["top1"] <= res["top3"] <= 1.0
    assert res["top1"] > 0.9  # the cycle is recoverable from the context
    assert np.isfinite(res["dist_km"]) and res["dist_km"] >= 0.0
    assert res["dist_km"] == pytest.approx(0.0, abs=1e-6)  # correct top-1 -> zero distance
