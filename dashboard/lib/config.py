"""Dashboard dataset registry and paths — pure data, no streamlit imports."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_ROOT = REPO_ROOT / "data" / "processed"
DEFAULT_PACKAGE_DIR = PROCESSED_ROOT / "dashboard"

# Tests point this at a synthetic mini-package (never real parquet).
ENV_DATA_DIR = "MOBILITY_DASHBOARD_DATA"
ENV_PROCESSED_DIR = "MOBILITY_DASHBOARD_PROCESSED"

# Plotly "Plotly" qualitative palette, first 7 colors — one per dataset card.
PALETTE = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692"]

# song2010 headline for the hero comparisons.
SONG_PI = 0.93

# City anchors for the locator map (global-scope datasets are shown as cards only).
CITY_COORDS = {
    "Beijing": (39.9042, 116.4074),
    "Tokyo": (35.6762, 139.6503),
    "New York": (40.7128, -74.0060),
}


def package_dir() -> Path:
    """Curated-package dir (env override for tests), default data/processed/dashboard."""
    override = os.environ.get(ENV_DATA_DIR)
    return Path(override).expanduser() if override else DEFAULT_PACKAGE_DIR


def processed_dir(dataset: str) -> Path:
    """Per-dataset processed root (geolife is flat; others namespaced).

    Env override ``MOBILITY_DASHBOARD_PROCESSED`` repoints the whole tree so the
    suggest page's fallback reads stay out of real data during tests.
    """
    override = os.environ.get(ENV_PROCESSED_DIR)
    root = Path(override).expanduser() if override else PROCESSED_ROOT
    return root if dataset == "geolife" else root / dataset


DATASETS: dict[str, dict] = {
    "geolife": {
        "label": "GeoLife (GPS)",
        "city": "Beijing",
        "color": PALETTE[0],
        "scope": "city",
        "provider": "Microsoft GeoLife GPS",
        "n_cohort": 76,
        "q_median": 0.905,
    },
    "yjmob1": {
        "label": "YJMob100K #1",
        "city": "Tokyo",
        "color": PALETTE[1],
        "scope": "city",
        "provider": "YJMob100K (synthetic-grid)",
        "n_cohort": 99974,
        "q_median": 0.620,
    },
    "yjmob2": {
        "label": "YJMob100K #2",
        "city": "Tokyo",
        "color": PALETTE[2],
        "scope": "city",
        "provider": "YJMob100K (synthetic-grid)",
        "n_cohort": 24997,
        "q_median": 0.596,
    },
    "fsq_nyc": {
        "label": "Foursquare NYC",
        "city": "New York",
        "color": PALETTE[3],
        "scope": "city",
        "provider": "Foursquare TSMC2014",
        "n_cohort": 62,
        "q_median": 0.978,
    },
    "fsq_tky": {
        "label": "Foursquare Tokyo",
        "city": "Tokyo",
        "color": PALETTE[4],
        "scope": "city",
        "provider": "Foursquare TSMC2014",
        "n_cohort": 494,
        "q_median": 0.978,
    },
    "gowalla": {
        "label": "Gowalla (global)",
        "city": None,
        "color": PALETTE[5],
        "scope": "global",
        "provider": "SNAP Gowalla check-ins",
        "n_cohort": 1954,
        "q_median": 0.980,
    },
    "brightkite": {
        "label": "Brightkite (global)",
        "city": None,
        "color": PALETTE[6],
        "scope": "global",
        "provider": "SNAP Brightkite check-ins",
        "n_cohort": 2757,
        "q_median": 0.978,
    },
}

SOURCE_BADGE = {"baseline": "🧮 baseline", "deep": "🧠 deep", "rw": "🎲 random walk"}


def color_of(dataset: str) -> str:
    return DATASETS.get(dataset, {}).get("color", "#888888")


def label_of(dataset: str) -> str:
    return DATASETS.get(dataset, {}).get("label", dataset)
