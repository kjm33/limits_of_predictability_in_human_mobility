"""Proactive route suggestion CLI — the "Thursday 15:15" demo.

    python -m mobility.suggest --user 128 --now "Thu 15:15" [--route]

Loads mined routine cards, fires the trigger rule at --now (weekday+time or ISO
datetime), and optionally renders an OSRM route map from the origin place to the
top predicted destination.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import h3
import pandas as pd

from . import config
from .routines import suggest_destination
from .routing import OsrmClient, fallback_straight_line, make_route_map

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_now(raw: str, ref: datetime | None = None) -> pd.Timestamp:
    """Accept 'Thu 15:15' (next such weekday from ref) or ISO 'YYYY-MM-DD HH:MM'."""
    ref = ref or datetime.now()
    parts = raw.strip().split()
    if len(parts) == 2 and parts[0].title() in WEEKDAYS:
        wd = WEEKDAYS.index(parts[0].title())
        hh, mm = (int(x) for x in parts[1].split(":"))
        day = ref + timedelta(days=1)
        while day.weekday() != wd:
            day += timedelta(days=1)
        return pd.Timestamp(day.replace(hour=hh, minute=mm, second=0, microsecond=0))
    return pd.Timestamp(pd.to_datetime(raw))


def _origin(places: pd.DataFrame, user: str, at: str | None) -> tuple[float, float] | None:
    """Origin coords: --at 'lat,lon' | place label | user's home place."""
    if at:
        if "," in at:
            lat, lon = (float(x) for x in at.split(","))
            return lat, lon
        g = places[(places["user"] == user) & (places["label"] == at)]
    else:
        g = places[(places["user"] == user) & (places["label"] == "home")]
        if g.empty:
            g = places[places["user"] == user]
    if g.empty:
        return None
    row = g.sort_values("n_visits", ascending=False).iloc[0]
    return float(row["mean_lat"]), float(row["mean_lon"])


_DESC = "Proactive route suggestion CLI — the 'Thursday 15:15' demo."


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=_DESC)
    p.add_argument("--user", required=True, help="user id, e.g. 128")
    p.add_argument("--now", required=True, help="'Thu 15:15' or ISO datetime")
    p.add_argument("--lookahead", type=int, default=1, help="buckets to look ahead")
    p.add_argument("--threshold", type=float, default=0.5, help="min score confidence*stability")
    p.add_argument("--at", default=None, help="origin: 'lat,lon' or place label, default home")
    p.add_argument("--route", action="store_true", help="fetch OSRM route + folium map")
    p.add_argument(
        "--out", default=None, help="map html path (default reports/suggest_<user>.html)"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    routines = pd.read_parquet(config.PROCESSED / "routines.parquet")
    summary_path = config.PROCESSED / "places_summary.parquet"
    if summary_path.exists():
        places = pd.read_parquet(summary_path)
    else:  # older artifact: places.parquet holds stops+place_id; rebuild summary
        from .routines import summarize_places

        places = summarize_places(pd.read_parquet(config.PROCESSED / "places.parquet"))
    now = parse_now(args.now)

    routines_u = routines[routines["user"] == args.user]
    if routines_u.empty:
        print(f"user {args.user}: no routine cards mined (see mobility.routines)")
        return 1

    origin = _origin(places, args.user, args.at)
    if origin is None:
        print(f"user {args.user}: unknown origin (no places, wrong label?)")
        return 1
    recent = [h3.latlng_to_cell(origin[0], origin[1], 8)]

    cards = suggest_destination(
        args.user, now, recent, routines, places, threshold=args.threshold,
        lookahead_buckets=args.lookahead,
    )
    wd = WEEKDAYS[now.weekday()]
    print(f"user {args.user} @ {wd} {now.strftime('%H:%M')} "
          f"from ({origin[0]:.4f}, {origin[1]:.4f})")
    if not cards:
        print("no routine triggers within lookahead")
        return 0

    for i, c in enumerate(cards, 1):
        ev = c["evidence"]
        print(
            f"\n#{i} -> ({c['d_lat']:.4f}, {c['d_lon']:.4f})  score {c['score']:.2f}"
            f"  [{ev['d_label'] or 'place ' + str(ev['d_place'])}]"
        )
        print(
            f"    seen {ev['n_trips']}x over {ev['support_weeks']} weeks"
            f" ({ev['bucket_str']}, conf {ev['confidence']:.2f}, stab {ev['stability']:.2f},"
            f" last {ev['last_seen'][:10]})"
        )

    if args.route:
        top = cards[0]
        local = OsrmClient.local()
        client = local if local.is_local_available() else OsrmClient()
        route = client.route(origin[0], origin[1], top["d_lat"], top["d_lon"])
        src = "osrm"
        if route is None:
            route = fallback_straight_line(origin, (top["d_lat"], top["d_lon"]))
            src = "straight-line fallback"
        out = Path(args.out) if args.out else config.REPORTS / f"suggest_{args.user}.html"
        ev = cards[0]["evidence"]
        routine_txt = {
            "routine": f"{ev['bucket_str']} ({WEEKDAYS[now.weekday()]})",
            "support_weeks": ev["support_weeks"],
            "confidence": f"{ev['confidence']:.2f}",
            "stability": f"{ev['stability']:.2f}",
            "score": f"{cards[0]['score']:.2f}",
        }
        make_route_map(origin, (top["d_lat"], top["d_lon"]), route, out, routine=routine_txt)
        km = route["distance_m"] / 1000
        mins = route["duration_s"] / 60
        print(f"\nroute ({src}): {km:.1f} km, {mins:.0f} min -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
