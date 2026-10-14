"""Download Foursquare NYC/Tokyo check-ins (TSMC'15, Dingqi Yang) into data/raw/foursquare/.

Source page: https://sites.google.com/site/yangdingqi/home/foursquare-dataset
(hosted on Google Drive; 227,428 NYC + 573,703 Tokyo check-ins, Apr 2012 - Feb 2013).
"""

import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

URL = "https://drive.google.com/uc?export=download&id=1VE67jfSN-GV6fkCfuyBEQJzk_qy-SfOk"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "foursquare"
EXPECTED = {
    "dataset_TSMC2014_NYC.txt": 227_428,
    "dataset_TSMC2014_TKY.txt": 573_703,
}


def _count_lines(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    zip_path = RAW / "tsmc2014.zip"
    if not all((RAW / "dataset_tsmc2014" / name).exists() for name in EXPECTED):
        if not zip_path.exists():
            print(f"downloading {URL} -> {zip_path}", flush=True)
            urlretrieve(URL, zip_path)
        print("extracting ...", flush=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(RAW)
    for name, want in EXPECTED.items():
        n = _count_lines(RAW / "dataset_tsmc2014" / name)
        print(f"{name}: {n:,} check-ins")
        if n != want:
            print(f"WARNING: expected {want:,} lines in {name}", file=sys.stderr)


if __name__ == "__main__":
    main()
