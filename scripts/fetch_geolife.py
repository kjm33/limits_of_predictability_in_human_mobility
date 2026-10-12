"""Download and extract the GeoLife 1.3 dataset into data/raw/."""

import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

URL = "https://download.microsoft.com/download/f/4/8/f4894aa5-fdbc-481e-9285-d5f8c4c4f039/Geolife%20Trajectories%201.3.zip"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    zip_path = RAW / "Geolife Trajectories 1.3.zip"
    if not zip_path.exists():
        print(f"downloading {URL} -> {zip_path}", flush=True)
        urlretrieve(URL, zip_path)
    print("extracting ...", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(RAW)
    users = sorted((RAW / "Geolife Trajectories 1.3" / "Data").iterdir())
    plts = list((RAW / "Geolife Trajectories 1.3" / "Data").glob("*/*.plt")) + list(
        (RAW / "Geolife Trajectories 1.3" / "Data").glob("*/Trajectory/*.plt")
    )
    print(f"users: {len(users)}, plt files: {len(plts)}")
    if len(users) != 182 or len(plts) != 18670:  # v1.3 has 18,670 plt files (v1.2 had 17,621)
        print("WARNING: unexpected counts", file=sys.stderr)


if __name__ == "__main__":
    main()
