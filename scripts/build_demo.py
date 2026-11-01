"""Build demo/public/data.json for the static scrollytelling demo.

Reads only data/processed/ parquets (incl. the curated dashboard/ extracts) and
emits one compact JSON payload consumed by the Vite+Svelte app in demo/.

Schema (top level):
  meta    : {built_at, source note}
  hero    : {n_datasets, people, records, records_label, share_geolife,
             trigger_precision_geolife}
  datasets: [{key,label,city,country,watch,volunteered,unit,n_users,n_cohort,
              records,span_days,median_user_days,pi_mean,best_model,best_top1,
              n_cards,users_with_cards,cohort_with_cards,pct_pattern,conf_mean,
              trigger:{fired,hit,precision}|None, note}]  (6 entries; yjmob merged)
  funnel  : {points,stops,places,cohort,users_with_cards,cards}  (geolife)
  pi      : {<key>: [Pi_actual samples <=1500]}
  game    : {regular:{diary:[cell names],N,S_unc,S_actual,Pi_unc,Pi_actual},
             wanderer:{...}}
  user022 : {pi:{N,S_unc,S_actual,Pi_actual},
              lz:{k,cells,phrases,n_hours},          # gzip walk payload
              markov:{top,n,rows,acc,n_pairs,n_eval},
             cells:[{i,h3,lat,lon,label}],
             hexes:{r9,r8,r7},       # GeoJSON FeatureCollections
             seq:{h0:[hours],cell:[i],known:[0/1]},
             stops:[{lat,lon,t,dwell}],         # <=1500, t = minutes since first
             grids:{"5"|"15"|"60":{nb,cells:[i|-1],support:[n weeks]}},
             places:[...], cards:[...]}
  lz_trio : [{name,diary,S_rand,S_unc,S_actual}]   (4-hour toy diaries)
  fano    : {n, points:[[S,Pi]]}   S -> ceiling curve for user022's N

Run:  uv run python scripts/build_demo.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from mobility import entropy as ent

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
OUT_DEFAULT = REPO / "demo" / "public" / "data.json"

# YJMob100K ships grid pings with no raw points parquet; total across both
# sub-datasets, documented in reports/2026-11-01-demo-website-analysis.md.
YJMOB_RECORDS = 111_535_175
UNKNOWN = -1

DATASETS: dict[str, dict] = {
    "geolife": {
        "label": "GeoLife",
        "city": "Beijing",
        "country": "China",
        "watch": "GPS loggers recording every 1–5 seconds",
        "volunteered": False,
        "unit": "GPS points",
        "dir": PROC,
    },
    "yjmob1": {
        "label": "YJMob100K",
        "city": "Japan (nationwide)",
        "country": "Japan",
        "watch": "App pings snapped to a 500 m grid",
        "volunteered": False,
        "unit": "grid pings",
        "dir": PROC / "yjmob1",
        "note": "100,000 people · sub-dataset 1",
    },
    "yjmob2": {
        "label": "YJMob100K",
        "city": "Japan (nationwide)",
        "country": "Japan",
        "watch": "App pings snapped to a 500 m grid",
        "volunteered": False,
        "unit": "grid pings",
        "dir": PROC / "yjmob2",
        "note": "25,000 people · sub-dataset 2",
    },
    "fsq_nyc": {
        "label": "Foursquare NYC",
        "city": "New York",
        "country": "USA",
        "watch": "Check-ins you post yourself",
        "volunteered": True,
        "unit": "check-ins",
        "dir": PROC / "fsq_nyc",
    },
    "fsq_tky": {
        "label": "Foursquare Tokyo",
        "city": "Tokyo",
        "country": "Japan",
        "watch": "Check-ins you post yourself",
        "volunteered": True,
        "unit": "check-ins",
        "dir": PROC / "fsq_tky",
    },
    "gowalla": {
        "label": "Gowalla",
        "city": "Worldwide",
        "country": "Global",
        "watch": "Check-ins you post yourself",
        "volunteered": True,
        "unit": "check-ins",
        "dir": PROC / "gowalla",
    },
    "brightkite": {
        "label": "Brightkite",
        "city": "Worldwide",
        "country": "Global",
        "watch": "Check-ins you post yourself",
        "volunteered": True,
        "unit": "check-ins",
        "dir": PROC / "brightkite",
    },
}


# --------------------------------------------------------------------------
# Pure helpers (unit-tested with synthetic data in tests/test_build_demo.py)
# --------------------------------------------------------------------------


def abs_slots(ts: pd.Series, minutes: int) -> pd.Series:
    """Absolute slot index (epoch-minute // minutes) for datetime stamps.

    Follows the repo rule: never trust parquet ns units — normalise through
    datetime64[s] before integer arithmetic.
    """
    secs = ts.astype("datetime64[s]").astype("int64").to_numpy()
    return pd.Series(secs // 60 // minutes, index=ts.index)


def weekly_slot(k: int, nb: int) -> int:
    """Weekly slot index (Mon 00:00 = 0) from an absolute slot index.

    Epoch day 0 (1970-01-01) was a Thursday, hence the +3 shift.
    """
    return ((k // nb + 3) % 7) * nb + (k % nb)


def week_grid(
    arrives: pd.Series, departs: pd.Series, cells: pd.Series, minutes: int
) -> dict:
    """Modal cell + supporting-week count per weekly slot from stop episodes.

    A stop from Mon 23:50 to Tue 00:20 fills every bucket it touches (a stop
    means the person was in that cell the whole time). Cells map to vocab
    indices; empty slots get UNKNOWN (-1). ``support`` counts distinct weeks
    (ISO-style epoch weeks of the resolution given).
    """
    nb = 1440 // minutes
    slots_per_week = 7 * nb
    starts = abs_slots(arrives, minutes).to_numpy()
    ends = abs_slots(departs, minutes).to_numpy()
    cell_v = cells.to_numpy()
    rows = []
    for s, e, c in zip(starts, ends, cell_v, strict=True):
        if c == UNKNOWN or not np.isfinite(s):
            continue
        for k in range(int(s), int(e) + 1):
            rows.append((weekly_slot(k, nb), k // slots_per_week, int(c)))
    grid_cells = np.full(slots_per_week, UNKNOWN, dtype=np.int32)
    grid_support = np.zeros(slots_per_week, dtype=np.int32)
    if rows:
        frame = pd.DataFrame(rows, columns=["wslot", "week", "cell"])
        for wslot, grp in frame.groupby("wslot"):
            grid_cells[wslot] = grp["cell"].mode().iloc[0]
            grid_support[wslot] = grp["week"].nunique()
    return {
        "nb": nb,
        "cells": grid_cells.tolist(),
        "support": grid_support.tolist(),
    }


def hexes_geojson(cells: list[str]) -> dict:
    """GeoJSON FeatureCollection of H3 boundaries (lng/lat, rounded 5 dp)."""
    feats = []
    for c in cells:
        ring = [[round(lng, 5), round(lat, 5)] for lat, lng in h3.cell_to_boundary(c)]
        ring.append(ring[0])
        feats.append(
            {"type": "Feature", "id": c, "geometry": {"type": "Polygon",
             "coordinates": [ring]}, "properties": {}}
        )
    return {"type": "FeatureCollection", "features": feats}


def diary_song(names: list[str]) -> dict:
    """Song et al. quantities for a toy diary given as cell-name sequence."""
    vocab = sorted(set(names))
    idx = {n: i for i, n in enumerate(vocab)}
    seq = np.array([idx[n] for n in names], dtype=np.int64)
    stats = ent.analyze_user(seq)
    return {
        "diary": names,
        "N": int(stats["N"]),
        "S_unc": round(float(stats["S_unc"]), 2),
        "S_actual": round(float(stats["S_actual"]), 2),
        "Pi_unc": round(float(stats["Pi_unc"]), 3),
        "Pi_actual": round(float(stats["Pi_actual"]), 3),
    }


def toy_diaries() -> dict:
    """Two toy weeks for the guessing game: a commuter and a wanderer."""
    commuter = (
        ["home", "work", "work", "work", "gym", "home"]
        + ["home", "work", "work", "work", "shop", "home"]
        + ["home", "work", "work", "work", "work", "home"]
        + ["home", "work", "work", "work", "work", "home"]
        + ["home", "work", "work", "work", "pub", "home"]
        + ["home", "park", "home"]
        + ["home", "home", "home"]
    ) * 12
    rng = np.random.default_rng(7)
    wanderer = [rng.choice(["a", "b", "c", "d", "e", "f", "g", "h"]).item()
                for _ in range(252)]
    return {"regular": diary_song(commuter), "wanderer": diary_song(wanderer)}


def lz_phrases(cells: list[int]) -> list[list[int]]:
    """Greedy Lempel-Ziv parse for the walk animation: disjoint blocks, each
    the shortest block starting there that never appeared earlier (the same
    novel-block rule lz_entropy sums over *every* hour of the diary).
    """
    s = "".join(map(chr, cells))
    n = len(s)
    phrases: list[list[int]] = []
    i = 0
    while i < n:
        length = 1
        while i + length <= n and s.find(s[i:i + length], 0, i) != -1:
            length += 1
        phrases.append(list(range(i, min(i + length, n))))
        i += length
    return phrases


def lz_toy_trio() -> list[dict]:
    """Three 4-hour toy diaries: the routine, the drum beat, the free rein."""
    out = []
    for name, names in (
        ("the routine", ["h"] * 4),
        ("the drum beat", ["h", "w", "h", "w"]),
        ("the free rein", ["h", "w", "c", "g"]),
    ):
        stats = diary_song(names)
        out.append({
            "name": name,
            "diary": names,
            "S_rand": round(math.log2(max(stats["N"], 1)), 2),
            "S_unc": stats["S_unc"],
            "S_actual": stats["S_actual"],
        })
    return out


def fano_curve(n: int, steps: int = 61) -> list[list[float]]:
    """[S, Pi] points from S=0..log2(n): the referee's rulebook as a curve."""
    top = math.log2(n)
    return [
        [round(s, 3), round(float(ent.fano_predictability(s, n)), 3)]
        for s in (i * top / (steps - 1) for i in range(steps))
    ]


def markov_table(cells: list[int], known: list[int], top: int = 4) -> dict:
    """Order-1 "from here, where next?" table over a user's hourly cells.

    The most-visited `top` cells keep their identity; the rest collapse into
    one "elsewhere" bucket. Trained on the first 80% of consecutive known-hour
    pairs, evaluated on the last 20% (origins never seen in training skipped).
    """
    pairs = [
        (a, b)
        for a, b, ka, kb in zip(
            cells[:-1], cells[1:], known[:-1], known[1:], strict=True
        )
        if ka and kb
    ]
    if len(pairs) < 10:
        return {}
    counts_by = pd.Series([a for a, _ in pairs]).value_counts()
    top_ids = [int(c) for c in counts_by.index[:top]]
    remap = {c: i for i, c in enumerate(top_ids)}
    other = len(top_ids)

    def enc(c: int) -> int:
        return remap.get(int(c), other)

    n_train = int(len(pairs) * 0.8)
    counts = np.zeros((other + 1, other + 1))
    for a, b in pairs[:n_train]:
        counts[enc(a), enc(b)] += 1
    hits = eval_n = 0
    for a, b in pairs[n_train:]:
        row = counts[enc(a)]
        if row.sum() == 0:
            continue
        eval_n += 1
        hits += int(int(row.argmax()) == enc(b))
    rows = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    return {
        "top": top_ids,
        "n": other + 1,
        "rows": [[round(float(v), 3) for v in r] for r in rows],
        "acc": round(hits / eval_n, 3) if eval_n else None,
        "n_pairs": len(pairs),
        "n_eval": eval_n,
    }


# --------------------------------------------------------------------------
# Real-data assembly
# --------------------------------------------------------------------------


def n_rows(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows


def span_and_median_days(
    points: Path, cohort_users: pd.DataFrame | None = None
) -> tuple[int | None, int | None]:
    """(robust span_days, median per-user active days over cohort) from points.

    Span uses the 0.1%–99.9% timestamp range — loggers occasionally write a
    broken device clock (one GeoLife point sits in the year 2000).
    """
    if not points.exists():
        return None, None
    df = pd.read_parquet(points, columns=["user", "ts"])
    lo, hi = df["ts"].quantile([0.001, 0.999])
    span = int((hi - lo).total_seconds() // 86400)
    if cohort_users is not None:
        df = df[df["user"].isin(cohort_users["user"])]
    day_units = df["ts"].dt.floor("D").astype("datetime64[s]").astype("int64")
    pairs = pd.DataFrame({"u": df["user"].to_numpy(), "d": day_units.to_numpy()})
    median = int(pairs.drop_duplicates()["u"].value_counts().median())
    return span, median


def dataset_row(key: str, meta: dict, summary: pd.DataFrame) -> dict:
    s = summary[summary["dataset"] == key].iloc[0]
    d = meta["dir"]
    out = {
        "key": key,
        "label": meta["label"],
        "city": meta["city"],
        "country": meta["country"],
        "watch": meta["watch"],
        "volunteered": meta["volunteered"],
        "unit": meta["unit"],
        "n_users": int(s["n_users"]),
        "n_cohort": int(s["n_cohort"]),
        "pi_mean": round(float(s["pi_actual_mean"]), 3),
        "best_model": str(s["best_baseline"]),
        "best_top1": round(float(s["best_baseline_top1"]), 3),
        "n_cards": int(s["n_cards"]),
        "note": meta.get("note"),
    }
    pdir = PROC if key == "geolife" else d
    if key.startswith("yjmob"):
        out["records"] = None  # no raw points parquet; hero uses the constant
        out["span_days"], out["median_user_days"] = 75, None
    else:
        cohort = pd.read_parquet(pdir / "cohort.parquet")
        span, median = span_and_median_days(pdir / "points.parquet", cohort)
        out["records"] = n_rows(pdir / "points.parquet")
        out["span_days"], out["median_user_days"] = span, median

    routines = pdir / "routines.parquet"
    if routines.exists():
        r = pd.read_parquet(routines)
        per_user = r.groupby("user").agg(
            cards=("confidence", "size"), conf=("confidence", "mean")
        )
        out["users_with_cards"] = int(len(per_user))
        out["cohort_with_cards"] = int(s["n_cohort"])
        out["pct_pattern"] = round(len(per_user) / max(int(s["n_cohort"]), 1), 3)
        out["conf_mean"] = round(float(per_user["conf"].mean()), 3)
    trig = pdir / "trigger_eval.parquet"
    if trig.exists():
        t = pd.read_parquet(trig)
        fired, hits = int(t["n_fired"].sum()), int(t["n_hits"].sum())
        out["trigger"] = (
            {"fired": fired, "hit": hits,
             "precision": round(hits / fired, 3)} if fired else None
        )
    return out


def build_user022() -> dict:
    base = PROC / "dashboard" / "users" / "geolife" / "022"
    seq = pd.read_parquet(base / "seq.parquet")
    places = pd.read_parquet(base / "places.parquet")
    cards = pd.read_parquet(base / "cards.parquet")
    stops = pd.read_parquet(
        PROC / "stops.parquet",
        columns=["user", "arrive", "depart", "lat", "lon", "dwell_min", "h3_r9"],
    )
    stops = stops[stops["user"] == "022"]

    ent022 = pd.read_parquet(PROC / "entropy.parquet")
    ent022 = ent022[ent022["user"] == "022"].iloc[0]

    stops_r8 = stops["h3_r9"].map(lambda c: h3.cell_to_parent(c, 8))
    # Vocabulary: r8 cells (seq.h3 is r8; stop cells roll up via cell_to_parent).
    vocab = sorted(set(seq["h3"].dropna()) | set(stops_r8.dropna()))
    # District-level r7 cells, also derived the official way (parent of parent).
    vocab7 = sorted({h3.cell_to_parent(h, 7) for h in vocab})
    vidx = {h: i for i, h in enumerate(vocab)}
    label_by_r8 = {
        r["modal_h3_r8"]: (r["label"] or None) for _, r in places.iterrows()
    }
    cells = []
    for i, h in enumerate(vocab):
        lat, lon = h3.cell_to_latlng(h)
        cells.append({
            "i": i, "h3": h, "lat": round(lat, 5), "lon": round(lon, 5),
            "label": label_by_r8.get(h),
        })

    t0 = int(seq["hour"].astype("datetime64[s]").astype("int64").min() // 3600)
    hours = (seq["hour"].astype("datetime64[s]").astype("int64") // 3600 - t0)

    grids = {
        str(m): week_grid(stops["arrive"], stops["depart"],
                          stops_r8.map(vidx).fillna(UNKNOWN).astype(int), m)
        for m in (5, 15, 60)
    }

    cell_seq = seq["h3"].map(vidx).fillna(UNKNOWN).astype(int).tolist()
    known_seq = seq["known"].astype(int).tolist()

    # gzip-walk payload: first 96 known hours over the top-6 cells (+ elsewhere)
    known_cells = [c for c, k in zip(cell_seq, known_seq, strict=True) if k]
    top6 = [int(c) for c in pd.Series(known_cells).value_counts().index[:6]]
    t6 = {c: i for i, c in enumerate(top6)}
    lz_cells = [t6.get(int(c), 6) for c in known_cells[:96]]
    lz = {
        "k": 6,
        "cells": lz_cells,
        "phrases": lz_phrases(lz_cells),
        "n_hours": len(known_cells),
    }

    # Discretization demo: a raw-GPS window around a Monday-15:00 departure
    # (the very trip the trigger rule fires on). Points keep their raw
    # lat/lon/t for the ticker; each also carries its r8 cell and quarter-hour
    # bucket so the scene never computes H3 in the browser.
    discretize = {}
    pts = pd.read_parquet(
        PROC / "points.parquet",
        columns=["user", "ts", "lat", "lon"],
        filters=[("user", "==", "022")],
    )
    mon = stops.copy()
    mon["wd"] = mon["depart"].dt.weekday
    hh = mon["depart"].dt.hour + mon["depart"].dt.minute / 60.0
    mon = mon[(mon["wd"] == 0) & (hh >= 14.9) & (hh <= 15.3)]
    anchor = mon["depart"].iloc[0] if len(mon) else stops["depart"].iloc[0]
    w0 = anchor - pd.Timedelta(minutes=25)
    win = pts[(pts["ts"] >= w0) & (pts["ts"] <= anchor + pd.Timedelta(minutes=45))]
    win = win.sort_values("ts")
    if len(win):
        sampled = win.iloc[:: len(win) // 400 + 1] if len(win) > 400 else win
        order: list[str] = []
        raw = []
        for r in sampled.itertuples():
            c8 = h3.cell_to_parent(h3.latlng_to_cell(r.lat, r.lon, 9), 8)
            if c8 not in order:
                order.append(c8)
            raw.append((r.ts, r.lat, r.lon, order.index(c8)))
        dcells = []
        for c8 in order:
            lat8, lon8 = h3.cell_to_latlng(c8)
            dcells.append({"lat": round(lat8, 5), "lon": round(lon8, 5)})
        points = [
            {
                "t": int((ts - w0).total_seconds()),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "c": ci,
                "b": int((ts.hour * 60 + ts.minute) // 15),
                "wd": int(ts.weekday()),
            }
            for ts, lat, lon, ci in raw
        ]
        n_buckets = len({p["b"] for p in points})
        discretize = {
            "n_raw": int(len(win)),
            "n_sample": len(points),
            "n_cells": len(order),
            "n_buckets": n_buckets,
            "window_min": 70,
            "cells": dcells,
            "points": points,
        }

    srt = stops.sort_values("arrive")
    if len(srt) > 1500:
        srt = srt.iloc[:: len(srt) // 1500 + 1]
    st0 = int(srt["arrive"].iloc[0].timestamp() // 60)
    stop_list = [
        {"lat": round(r.lat, 5), "lon": round(r.lon, 5),
         "t": int(r.arrive.timestamp() // 60) - st0,
         "dwell": round(float(r.dwell_min), 1)}
        for r in srt.itertuples()
    ]

    def clean(df: pd.DataFrame) -> list[dict]:
        keep = df[[
            "weekday", "bucket_str", "o_label", "d_label", "n_trips",
            "support", "confidence", "stability", "o_lat", "o_lon", "d_lat", "d_lon",
        ]].copy()
        return json.loads(keep.to_json(orient="records"))

    return {
        "pi": {
            "N": int(ent022["N"]),
            "S_unc": round(float(ent022["S_unc"]), 2),
            "S_actual": round(float(ent022["S_actual"]), 2),
            "Pi_actual": round(float(ent022["Pi_actual"]), 3),
        },
        "cells": cells,
        "hexes": {
            "r9": hexes_geojson(sorted(stops["h3_r9"].dropna().unique())),
            "r8": hexes_geojson(vocab),
            "r7": hexes_geojson(vocab7),
        },
        "seq": {
            "h0": hours.astype(int).tolist(),
            "cell": cell_seq,
            "known": known_seq,
        },
        "lz": lz,
        "markov": markov_table(cell_seq, known_seq),
        "discretize": discretize,
        "stops": stop_list,
        "grids": grids,
        "places": json.loads(places.to_json(orient="records")),
        "cards": clean(cards),
    }


def main(out: Path = OUT_DEFAULT) -> Path:
    summary = pd.read_parquet(PROC / "dashboard" / "dataset_summary.parquet")
    rows = [dataset_row(k, m, summary) for k, m in DATASETS.items()]

    pi = pd.read_parquet(
        PROC / "dashboard" / "pi_distributions.parquet",
        columns=["dataset", "Pi_actual"],
    )
    pi_samples = {}
    for k, g in pi.groupby("dataset"):
        vals = g["Pi_actual"].dropna()
        pi_samples[k] = [
            round(float(v), 3)
            for v in vals.sample(min(1500, len(vals)), random_state=11)
        ]

    geo_row = summary[summary["dataset"] == "geolife"].iloc[0]
    geo = next(r for r in rows if r["key"] == "geolife")
    u022 = build_user022()
    payload = {
        "meta": {
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "data/processed/ parquets via scripts/build_demo.py",
        },
        "hero": {
            "n_datasets": 6,
            "people": sum(r["n_users"] for r in rows),
            "records": sum(r["records"] or 0 for r in rows) + YJMOB_RECORDS,
            "records_label": "location records",
            "share_geolife": geo["pct_pattern"],
            "trigger_precision_geolife": geo["trigger"]["precision"],
        },
        "datasets": rows,
        "funnel": {
            "points": n_rows(PROC / "points.parquet"),
            "stops": n_rows(PROC / "stops.parquet"),
            "places": int(geo_row["n_places"]),
            "cohort": geo["n_cohort"],
            "users_with_cards": geo["users_with_cards"],
            "cards": geo["n_cards"],
        },
        "pi": pi_samples,
        "game": toy_diaries(),
        "lz_trio": lz_toy_trio(),
        "fano": {
            "n": u022["pi"]["N"],
            "points": fano_curve(u022["pi"]["N"]),
        },
        "user022": u022,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(payload, fh, separators=(",", ":"), allow_nan=False)
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} KB)")
    if out.stat().st_size > 900_000:
        print("WARNING: data.json above 900 KB budget")
    return out


if __name__ == "__main__":
    main()
