"""Download YJMob100K (Zenodo 10.5281/zenodo.10836269) into data/raw/yjmob100k/.

Files: dataset1 (100k users, 75 d), dataset2 (20k users, incl. 15 d emergency),
per-cell POI category counts, and the 85 POI category names.
"""

import hashlib
import sys
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://zenodo.org/api/records/10836269/files"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "yjmob100k"

FILES = {
    "yjmob100k-dataset1.csv.gz": "3781f6f03a118b5f639bdb4f94dcfdb8",
    "yjmob100k-dataset2.csv.gz": "ec769fafa7a746caa3d48d2844b9735c",
    "cell_POIcat.csv.gz": "93af4bb0b417cd20e95fdc1d8f7b459f",
    "POI_datacategories.csv": "fd024e10c1d1dd91356d010413ace390",
}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for fname, want in FILES.items():
        dest = RAW / fname
        if not dest.exists():
            url = f"{BASE}/{fname}/content"
            print(f"downloading {url} -> {dest}", flush=True)
            urlretrieve(url, dest)
        got = _md5(dest)
        print(f"{fname}: {dest.stat().st_size:,} bytes  md5={got}")
        if got != want:
            print(f"WARNING: md5 mismatch for {fname} (expected {want})", file=sys.stderr)


if __name__ == "__main__":
    main()
