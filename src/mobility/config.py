"""Central paths and constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "Geolife Trajectories 1.3" / "Data"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

# Non-GeoLife datasets: raw locations and processed-output namespaces.
RAW_DIRS = {
    "yjmob1": ROOT / "data" / "raw" / "yjmob100k",
    "yjmob2": ROOT / "data" / "raw" / "yjmob100k",
    "fsq_nyc": ROOT / "data" / "raw" / "foursquare",
    "fsq_tky": ROOT / "data" / "raw" / "foursquare",
    "gowalla": ROOT / "data" / "raw" / "gowalla",
    "brightkite": ROOT / "data" / "raw" / "brightkite",
}


def processed_dir(dataset: str = "geolife") -> Path:
    """Processed-output directory for a dataset.

    ``geolife`` keeps the flat ``data/processed/`` layout (default); other
    datasets get a namespaced subdirectory with the same artifact names
    (points/seq_hourly/cells_r8/...), so downstream stages run unchanged via
    their ``processed_dir`` parameter.
    """
    if dataset == "geolife":
        return PROCESSED
    if dataset not in RAW_DIRS:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(RAW_DIRS)}")
    d = PROCESSED / dataset
    d.mkdir(parents=True, exist_ok=True)
    return d

# H3 resolutions (avg hex edge/area):
#   r9 ~0.10 km^2 (stop detail), r8 ~0.74 km^2 (primary modeling),
#   r7 ~5.2 km^2, r6 ~36 km^2 (corridors)
H3_STOP_RES = 9
H3_PRIMARY_RES = 8
H3_CORRIDOR_RES = 7
H3_COARSE_RES = 6

# Stay-point detection (Zheng et al. 2009 style parameters)
STAY_RADIUS_M = 250.0
STAY_MIN_MINUTES = 10.0

# QC / segmentation
SEGMENT_GAP_MIN = 20.0  # split trajectory on time gaps > 20 min
MAX_SPEED_MS = 90.0  # drop points implying speeds > 324 km/h (train/plane outliers)
TIME_BIN_S = 60  # pre-binning for stay detection

# Cohort selection
MIN_ACTIVE_DAYS = 30
MIN_DISTINCT_R8 = 5

# Analysis defaults
UNKNOWN = -1  # sentinel cell index for unknown hourly location
