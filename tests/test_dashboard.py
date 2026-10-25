"""Dashboard tests — synthetic parquets only (never the real curated package)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root for dashboard.*

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from dashboard.lib import config, data  # noqa: E402

SEQ_COLS = data.SEQ_COLS
CARD_COLS = data.CARD_COLS
PLACE_COLS = data.PLACE_COLS


# ------------------------------------------------------- synthetic fixtures ----

def _cards_frame(users: list[str]) -> pd.DataFrame:
    rows = [
        {
            "user": u, "o_place": 0, "d_place": 1, "weekday": 0, "bucket": 60,
            "bucket_str": "15:00-15:15", "n_trips": 3, "support": 3, "confidence": 1.0,
            "stability": 1.0, "first_seen": "2009-01-05", "last_seen": "2009-10-01",
            "o_h3_r8": "8831aa50e9fffff", "d_h3_r8": "8831aa51d9fffff",
            "o_lat": 39.9, "o_lon": 116.3, "d_lat": 39.91, "d_lon": 116.31,
            "o_label": "home", "d_label": "work",
        }
        for u in users
    ]
    return pd.DataFrame(rows, columns=CARD_COLS)


def _seq_frame(user: str) -> pd.DataFrame:
    rows = []
    for h in range(48):
        known = h % 3 != 0
        rows.append(
            {
                "user": user,
                "hour": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=h),
                "cell_idx": (h % 5) if known else -1,
                "h3": f"8831aa50e{h:05d}fffff" if known else None,
                "weekday": h % 7,
                "hour_of_day": h % 24,
                "lat": 39.9 + 0.01 * (h % 5) if known else None,
                "lon": 116.3 + 0.01 * (h % 5) if known else None,
                "known": known,
            }
        )
    return pd.DataFrame(rows, columns=SEQ_COLS)


def _places_frame(user: str, n: int = 2) -> pd.DataFrame:
    rows = [
        {
            "user": user, "place_id": i, "n_visits": 10 - i, "mean_lat": 39.9 + i * 0.01,
            "mean_lon": 116.3 + i * 0.01, "mean_dwell_min": 90.0,
            "modal_h3_r8": f"8831aa5{i}", "label": "home" if i == 0 else None,
            "top_venue_cat": None, "n_venue_checkins": None,
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows, columns=PLACE_COLS)


def _pi_frame() -> pd.DataFrame:
    rows = []
    for i in range(30):
        rows.append(
            {
                "dataset": "geolife", "user": f"g{i:03d}", "N": 50 + i,
                "S_rand": 6.0, "S_unc": 4.0, "S_actual": 2.0,
                "Pi_rand": 0.01, "Pi_unc": 0.40, "Pi_actual": 0.65, "q": 0.5 + 0.01 * i,
            }
        )
    for i in range(20):
        # one Fano violation (Pi_actual < Pi_unc) to make fano_frac interesting
        viol = i == 0
        rows.append(
            {
                "dataset": "yjmob1", "user": f"y{i:05d}", "N": 100 + i,
                "S_rand": 5.0, "S_unc": 4.5 if viol else 3.0, "S_actual": 2.5,
                "Pi_rand": 0.01, "Pi_unc": 0.30 if viol else 0.45,
                "Pi_actual": 0.20 if viol else 0.60, "q": 0.3 + 0.01 * i,
            }
        )
    return pd.DataFrame(rows)


def _summary_frame() -> pd.DataFrame:
    common = {
        "q_median": 0.9, "n_median": 55.0, "s_unc_median": 4.0, "pi_unc_median": 0.4,
        "pi_unc_mean": 0.4, "fano_frac": 1.0,
    }
    return pd.DataFrame(
        [
            {"dataset": "geolife", "n_users": 30, "n_cohort": 12, "q_median": 0.9,
             "n_median": 55.0, "s_unc_median": 4.0, "pi_unc_median": 0.4, "pi_unc_mean": 0.4,
             "pi_actual_median": 0.65, "pi_actual_mean": 0.65, "fano_frac": 1.0,
             "best_baseline": "markov2_col", "best_baseline_top1": 0.23, "n_cards": 2,
             "n_places": 4},
            {"dataset": "yjmob1", **common, "n_users": 20, "n_cohort": 20, "q_median": 0.6,
             "n_median": 105.0, "s_unc_median": 3.0, "pi_unc_median": 0.45, "pi_unc_mean": 0.44,
             "pi_actual_median": 0.60, "pi_actual_mean": 0.58, "fano_frac": 0.95,
             "best_baseline": "markov1", "best_baseline_top1": 0.29, "n_cards": 0,
             "n_places": 0},
        ]
    )


def _leaderboards_frame() -> pd.DataFrame:
    rows = [
        {"dataset": "geolife", "model": "freq", "source": "baseline", "n_users": 30,
         "n_eval_sum": 500, "top1": 0.15, "top3": 0.28, "dist_km": 100.0},
        {"dataset": "geolife", "model": "markov2_col", "source": "baseline", "n_users": 30,
         "n_eval_sum": 500, "top1": 0.23, "top3": 0.37, "dist_km": 90.0},
        {"dataset": "geolife", "model": "temporal_transformer", "source": "deep", "n_users": 12,
         "n_eval_sum": 200, "top1": 0.24, "top3": 0.40, "dist_km": 88.0},
        {"dataset": "geolife", "model": "rw_trip_dest", "source": "rw", "n_users": 12,
         "n_eval_sum": 200, "top1": 0.05, "top3": 0.10, "dist_km": 120.0},
        # yjmob1: baselines only — no deep, no rw rows
        {"dataset": "yjmob1", "model": "markov1", "source": "baseline", "n_users": 20,
         "n_eval_sum": 900, "top1": 0.29, "top3": 0.49, "dist_km": 5.0},
    ]
    return pd.DataFrame(rows)


def _featured_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"dataset": "geolife", "user": "022", "why": "most_predictable", "Pi_unc": 0.54,
             "Pi_actual": 0.86, "N": 104, "q": 0.77, "n_cards": 1, "n_places": 2},
            {"dataset": "geolife", "user": "111", "why": "most_exploratory", "Pi_unc": 0.06,
             "Pi_actual": 0.22, "N": 194, "q": 0.99, "n_cards": 1, "n_places": 1},
            # single-cell user: NaN predictability, but a pile of routine cards
            {"dataset": "geolife", "user": "9957", "why": "routine_creature", "Pi_unc": None,
             "Pi_actual": None, "N": 1, "q": 0.58, "n_cards": 3, "n_places": 1},
            {"dataset": "yjmob1", "user": "29085", "why": "most_exploratory", "Pi_unc": 0.04,
             "Pi_actual": 0.20, "N": 316, "q": 0.79, "n_cards": 0, "n_places": 0},
        ]
    )


def mini_package(tmp_path: Path) -> Path:
    """Write a two-dataset synthetic curated package; return its base dir."""
    base = tmp_path / "dashboard"
    base.mkdir()
    _summary_frame().to_parquet(base / "dataset_summary.parquet")
    _pi_frame().to_parquet(base / "pi_distributions.parquet")
    _leaderboards_frame().to_parquet(base / "leaderboards.parquet")
    _featured_frame().to_parquet(base / "featured_users.parquet")

    for user in ("022", "111"):
        d = base / "users" / "geolife" / user
        d.mkdir(parents=True)
        _seq_frame(user).to_parquet(d / "seq.parquet")
        _cards_frame([user]).to_parquet(d / "cards.parquet")
        _places_frame(user).to_parquet(d / "places.parquet")

    # single-cell "routine creature": canonical EMPTY cards, 1 place, exactly one known hour
    d = base / "users" / "geolife" / "9957"
    d.mkdir(parents=True)
    _cards_frame([]).to_parquet(d / "cards.parquet")
    _places_frame("9957", n=1).to_parquet(d / "places.parquet")
    seq = _seq_frame("9957").iloc[[1]].copy()  # row 1: h%3==0 -> unknown; flip to known
    seq["cell_idx"] = 7
    seq["h3"] = "8831aa50e9fffff"
    seq["lat"] = 39.9
    seq["lon"] = 116.3
    seq["known"] = True
    seq.to_parquet(d / "seq.parquet")

    d = base / "users" / "yjmob1" / "29085"
    d.mkdir(parents=True)
    _seq_frame("29085").to_parquet(d / "seq.parquet")
    _cards_frame([]).to_parquet(d / "cards.parquet")  # canonical empty
    _places_frame("29085", n=0).to_parquet(d / "places.parquet")
    pd.DataFrame([{"poi_Food": 3, "poi_Shopping": 1}]).to_parquet(d / "poi.parquet")
    return base


@pytest.fixture
def pkg(tmp_path, monkeypatch):
    base = mini_package(tmp_path)
    monkeypatch.setenv(config.ENV_DATA_DIR, str(base))
    monkeypatch.setenv(config.ENV_PROCESSED_DIR, str(tmp_path / "processed"))  # empty tree
    return base


# ------------------------------------------------------------- registry tests ----

def test_registry_completeness():
    assert set(config.DATASETS) == {
        "geolife", "yjmob1", "yjmob2", "fsq_nyc", "fsq_tky", "gowalla", "brightkite",
    }
    for key, meta in config.DATASETS.items():
        assert {"label", "city", "color", "scope", "provider", "n_cohort", "q_median"} <= set(
            meta
        ), key
        assert meta["color"].startswith("#")
        assert meta["scope"] in {"city", "global"}
        assert 0 < meta["q_median"] <= 1
    assert len({m["color"] for m in config.DATASETS.values()}) == len(config.DATASETS)
    assert config.processed_dir("geolife").name == "processed"
    assert config.processed_dir("yjmob1").name == "yjmob1"


def test_cohort_numbers_match_spec():
    assert config.DATASETS["yjmob1"]["n_cohort"] == 99974
    assert config.DATASETS["yjmob2"]["n_cohort"] == 24997
    assert config.DATASETS["geolife"]["n_cohort"] == 76
    assert abs(config.DATASETS["geolife"]["q_median"] - 0.905) < 1e-3
    assert abs(config.DATASETS["brightkite"]["q_median"] - 0.978) < 1e-3


# -------------------------------------------------------------- loader tests ----

def test_loaders_read_synthetic_package(pkg):
    summary = data.dataset_summary()
    assert list(summary["dataset"]) == ["geolife", "yjmob1"]
    pi = data.pi_distributions()
    assert len(pi) == 50
    lb = data.leaderboards()
    assert set(lb["source"]) == {"baseline", "deep", "rw"}
    fu = data.featured_users()
    assert len(fu) == 4
    assert data.has_package(pkg)
    assert not data.has_package(pkg.parent / "nowhere")


def test_user_loader_schemas_and_empty_cards(pkg):
    seq = data.user_seq("geolife", "022")
    assert list(seq.columns) == SEQ_COLS
    assert len(seq) == 48
    assert seq["known"].dtype == bool

    cards = data.user_cards("geolife", "022")
    assert list(cards.columns) == CARD_COLS
    assert len(cards) == 1

    empty = data.user_cards("yjmob1", "29085")  # canonical empty frame
    assert list(empty.columns) == CARD_COLS
    assert empty.empty

    places = data.user_places("yjmob1", "29085")
    assert places.empty and list(places.columns) == PLACE_COLS

    missing = data.user_seq("geolife", "nobody")
    assert missing.empty and list(missing.columns) == SEQ_COLS

    poi = data.user_poi("yjmob1", "29085")
    assert len(poi) == 1
    assert data.user_poi("geolife", "022").empty  # absent -> empty frame


def test_missing_core_file_raises(pkg):
    (pkg / "leaderboards.parquet").unlink()
    with pytest.raises(FileNotFoundError):
        data.leaderboards()


# ------------------------------------------------------ aggregation helpers ----

def test_fano_frac_table_counts_violations():
    fano = data.fano_frac_table(_pi_frame()).set_index("dataset")
    assert fano.loc["geolife", "fano_frac"] == 1.0
    assert fano.loc["geolife", "n_users"] == 30
    assert fano.loc["yjmob1", "fano_frac"] == pytest.approx(19 / 20)
    assert fano.loc["yjmob1", "n_users"] == 20


def test_pi_stats_and_entropy_medians_monotone():
    pi = _pi_frame()
    stats = data.pi_stats_table(pi).set_index("dataset")
    assert stats.loc["geolife", "n_users"] == 30
    assert stats.loc["geolife", "pi_actual_median"] == pytest.approx(0.65)
    assert stats.loc["geolife", "pi_rand_median"] < stats.loc["geolife", "pi_unc_median"]

    trio = data.entropy_medians(pi).set_index("dataset")
    assert trio["monotone"].all()
    for ds in trio.index:
        t = trio.loc[ds]
        assert t["S_rand"] >= t["S_unc"] >= t["S_actual"]


def test_pi_vs_q_samples_and_filters():
    pi = _pi_frame()
    sub = data.pi_vs_q(pi, keys=["geolife"], per_dataset=5, seed=0)
    assert len(sub) == 5 and (sub["dataset"] == "geolife").all()
    assert len(data.pi_vs_q(pi)) == 50


def test_leaderboard_helpers():
    lb = _leaderboards_frame()
    board = data.leaderboard_for(lb, "geolife")
    assert list(board["top1"]) == sorted(board["top1"], reverse=True)
    assert board.iloc[0]["model"] == "temporal_transformer"
    assert set(board["source_badge"]) == {"🧮 baseline", "🧠 deep", "🎲 random walk"}

    winners = data.winner_table(_summary_frame())
    assert list(winners["best_baseline"]) == ["markov1", "markov2_col"]  # sorted by top1

    cmp_df = data.deep_vs_baseline(lb, "geolife")
    assert len(cmp_df) == 2  # best baseline + one deep model
    assert cmp_df["top1"].max() == 0.24
    assert data.deep_vs_baseline(lb, "yjmob1").empty  # no deep rows -> empty, not crash


def test_weekday_hour_matrix_and_poi():
    seq = _seq_frame("022")
    grid = data.weekday_hour_matrix(seq)
    assert grid.shape == (7, 24)
    assert int(grid.to_numpy().sum()) == int(seq["known"].sum())
    assert data.weekday_hour_matrix(seq.iloc[:0]).to_numpy().sum() == 0

    poi = pd.DataFrame(
        [{"category": "poi_Food", "count": 3}, {"category": "poi_Bar", "count": 9}]
    )
    top = data.poi_top(poi, n=2)
    assert list(top["category"]) == ["poi_Bar", "poi_Food"]
    assert data.poi_top(pd.DataFrame()).empty


# ------------------------------------------------------------- suggest glue ----

def test_resolve_now_matches_cli_semantics():
    from mobility.suggest import parse_now

    ref = datetime(2026, 10, 12)  # Monday
    ts = data.resolve_now("Mon", 15, 14, ref=ref)
    assert (ts.weekday(), ts.hour, ts.minute) == (0, 15, 14)
    assert ts == parse_now("Mon 15:14", ref=ref)  # next such weekday strictly after ref
    assert data.resolve_now("Sun", 8, 0, ref=ref).weekday() == 6


def test_run_trigger_fires_flagship_card(pkg):
    cards = data.user_cards("geolife", "022")
    places = data.user_places("geolife", "022")
    now = data.resolve_now("Mon", 15, 14, ref=datetime(2026, 10, 12))
    origin = data.origin_for(places, "022")
    assert origin is not None

    hits = data.run_trigger("022", now, origin, cards, places, threshold=0.5, lookahead=1)
    assert len(hits) == 1
    ev = hits[0]["evidence"]
    assert ev["bucket_str"] == "15:00-15:15" and ev["n_trips"] == 3
    assert hits[0]["score"] == pytest.approx(1.0)

    # a threshold above 1.0 or a time outside the bucket silences the trigger
    assert data.run_trigger("022", now, origin, cards, places, threshold=1.5) == []
    later = data.resolve_now("Mon", 18, 0, ref=datetime(2026, 10, 12))
    assert data.run_trigger("022", later, origin, cards, places) == []


def test_origin_and_suggest_frames_fallback(pkg):
    places = _places_frame("u1", n=2)
    assert data.origin_for(places, "u1") == (39.9, 116.3)  # home wins over n_visits
    no_home = places.copy()
    no_home["label"] = None
    assert data.origin_for(no_home, "u1") == (39.9, 116.3)  # most-visited fallback
    assert data.origin_for(places[places["user"] == "ghost"], "ghost") is None

    # curated cards exist -> served from the package
    cards, places2, source = data.suggest_frames("geolife", "022")
    assert source == "curated user package" and len(cards) == 1 and len(places2) == 2

    # no curated cards -> falls back to the (synthetic, empty) processed tree
    cards, places2, source = data.suggest_frames("yjmob1", "29085")
    assert source == "dataset routines.parquet" and cards.empty
    assert data.dataset_routines("yjmob1").empty  # empty-tree fallback, no crash


# -------------------------------------------------------- AppTest smoke tests ----

def _run(app_path: Path):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(app_path), default_timeout=60)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_apptest_app_and_all_pages(pkg):
    pytest.importorskip("streamlit")
    root = Path(__file__).resolve().parents[1] / "dashboard"
    _run(root / "app.py")
    pages = sorted((root / "pages").glob("*.py"))
    assert len(pages) == 6
    for page in pages:
        _run(page)  # asserts no exception inside _run


def test_apptest_suggest_page_fires_trigger(pkg):
    pytest.importorskip("streamlit")
    root = Path(__file__).resolve().parents[1] / "dashboard"
    at = _run(root / "pages" / "5_Suggest_Demo.py")
    # default selection is the flagship geolife user on Mon 15:14 -> exactly one hit
    assert len(at.dataframe) >= 1
    captions = " ".join(str(c.value) for c in at.caption)
    assert "curated user package" in captions
