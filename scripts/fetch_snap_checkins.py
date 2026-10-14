"""Download Gowalla/Brightkite check-ins + friendship edges (SNAP) into data/raw/.

Source: https://snap.stanford.edu/data/loc-gowalla.html and loc-brightkite.html
(Cho/Myers/Leskovec, KDD'11). Check-ins feed mobility.checkins; edges are
fetched for future social+mobility analysis in the graphs module.
"""

import gzip
import sys
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://snap.stanford.edu/data"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
FILES = {
    "gowalla/loc-gowalla_totalCheckins.txt.gz": 6_442_890,
    "gowalla/loc-gowalla_edges.txt.gz": 950_327,
    "brightkite/loc-brightkite_totalCheckins.txt.gz": 4_491_143,
    "brightkite/loc-brightkite_edges.txt.gz": 214_078,
}


def _count_lines(path: Path) -> int:
    with gzip.open(path, "rt") as f:
        return sum(1 for _ in f)


def main() -> None:
    for rel, want in FILES.items():
        dest = RAW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            url = f"{BASE}/{rel}"
            print(f"downloading {url} -> {dest}", flush=True)
            urlretrieve(url, dest)
        n = _count_lines(dest)
        print(f"{rel}: {n:,} lines")
        if n != want:
            print(f"WARNING: expected {want:,} lines in {rel}", file=sys.stderr)


if __name__ == "__main__":
    main()
