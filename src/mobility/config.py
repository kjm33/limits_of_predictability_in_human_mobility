"""Central paths and constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "Geolife Trajectories 1.3" / "Data"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

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
