"""Suggest Demo — live routine-card trigger → destination → optional OSRM route."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402
from dashboard.lib.maps import scatter_map  # noqa: E402

st.title("🚗 Suggest Demo")
st.markdown(
    "The point of predictability is *useful* anticipation: **\"it's Monday 15:14 — you usually "
    "head somewhere around now; want the route?\"** This page runs the mined routine cards "
    "through the same trigger rule as the CLI (`python -m mobility.suggest`)."
)

# Datasets with any card source (yjmob ships no routines at all).
SUGGESTABLE = ["geolife", "fsq_nyc", "fsq_tky", "gowalla", "brightkite"]

dataset = st.selectbox(
    "Dataset",
    SUGGESTABLE,
    format_func=config.label_of,
    index=0,
    help="YJMob100K ships no routine cards (grid data, no stop-level places).",
)

featured = data.featured_users()
fu = featured[featured["dataset"] == dataset]

options: list[str] = []
labels: dict[str, str] = {}
for r in fu.itertuples():
    key = f"featured:{r.user}"
    pi_txt = "n/a" if pd.isna(r.Pi_actual) else f"{r.Pi_actual:.0%}"
    why = r.why.replace("_", " ")
    labels[key] = (f"⭐ {r.user} — {why}, Π {pi_txt}, {int(r.n_cards)} cards")
    options.append(key)

routines = data.dataset_routines(dataset)
if not routines.empty:
    extra = sorted(set(routines["user"].astype(str)) - set(fu["user"].astype(str)),
                   key=lambda s: (len(s), s))
    for u in extra[:50]:
        key = f"routine:{u}"
        n = int((routines["user"].astype(str) == u).sum())
        labels[key] = f"🔁 {u} — {n} routine cards"
        options.append(key)

default = options[0] if options else None
for key, lbl in labels.items():
    if key.startswith("featured:") and "cards" in lbl and " 0 cards" not in lbl:
        default = key
        break
if default is None:
    st.info("No routine cards exist for this dataset — pick another one.")
    st.stop()

sel = st.selectbox("User", options, index=options.index(default), format_func=lambda k: labels[k])
user = sel.split(":", 1)[1]

left, mid, right = st.columns(3)
weekday = left.selectbox("Weekday", data.WEEKDAYS, index=0)  # Mon — flagship card day
t = mid.time_input("Time", value=pd.Timestamp("2000-01-01 15:14").time())
lookahead = right.slider("Lookahead (15-min buckets)", 1, 4, 1)
threshold = st.slider("Min score (confidence × stability)", 0.0, 1.0, 0.5, 0.05)

now = data.resolve_now(weekday, t.hour, t.minute, ref=pd.Timestamp("2026-10-12").to_pydatetime())
st.caption(f"Resolved trigger instant: **{data.WEEKDAYS[now.weekday()]} {now:%H:%M}** "
           "(next such weekday from a Monday, matching the CLI).")

cards, places, source = data.suggest_frames(dataset, user)
if cards.empty:
    st.warning(
        f"User **{user}** has no routine cards (neither in the curated package nor in the "
        "dataset's routines.parquet). Nothing to trigger."
    )
    st.stop()

origin = data.origin_for(places, user)
if origin is None:
    st.warning("No origin place could be located for this user.")
    st.stop()

st.caption(f"Card source: `{source}` · origin from home/most-visited place "
           f"({origin[0]:.4f}, {origin[1]:.4f}).")

triggers = data.run_trigger(user, now, origin, cards, places,
                            threshold=threshold, lookahead=lookahead)

st.subheader("Trigger result")
if not triggers:
    st.warning("No routine triggers within the lookahead — try another time, weekday, "
               "a larger lookahead, or a lower threshold.")
    st.stop()

rows = []
for c in triggers:
    ev = c["evidence"]
    rows.append({
        "score": round(c["score"], 2),
        "destination": ev["d_label"] or f"place {ev['d_place']}",
        "bucket": ev["bucket_str"],
        "trips seen": ev["n_trips"],
        "weeks": ev["support_weeks"],
        "confidence": round(ev["confidence"], 2),
        "stability": round(ev["stability"], 2),
        "last seen": ev["last_seen"][:10],
        "d_lat": c["d_lat"],
        "d_lon": c["d_lon"],
    })
res = pd.DataFrame(rows)
st.dataframe(
    res.drop(columns=["d_lat", "d_lon"]),
    hide_index=True,
    use_container_width=True,
)
top = res.iloc[0]

pins = pd.DataFrame(
    [{"lat": origin[0], "lon": origin[1], "dot": "#2a9d8f", "pt": "origin"},
     {"lat": float(top["d_lat"]), "lon": float(top["d_lon"]), "dot": "#e76f51",
      "pt": "destination"}]
)
st.subheader("Suggested trip")
scatter_map(pins, lat="lat", lon="lon", color="dot")

with st.expander("Fetch a driving route (OSRM)", expanded=False):
    st.caption(
        "Tries a local OSRM docker first, then the rate-limited public demo server "
        "(1 req/s, self-throttled), and degrades to a straight-line estimate when offline."
    )
    if st.checkbox("Request route", value=False):
        from mobility.routing import OsrmClient, fallback_straight_line

        o = (origin[0], origin[1])
        d = (float(top["d_lat"]), float(top["d_lon"]))
        route, src = None, "straight-line fallback"
        try:
            local = OsrmClient.local()
            if local.is_local_available():
                client = local
                src = "local OSRM"
            else:
                client = OsrmClient()
                src = "public OSRM"
            route = client.route(o[0], o[1], d[0], d[1])
            if route is None:
                src = "straight-line fallback"
        except Exception:  # never crash the page without network
            route = None
            src = "straight-line fallback"
        if route is None:
            route = fallback_straight_line(o, d)

        geometry = list(route["geometry"])
        fig = go.Figure()
        if len(geometry) > 1:
            fig.add_trace(go.Scattermap(
                lat=[p[0] for p in geometry], lon=[p[1] for p in geometry],
                mode="lines", line={"width": 4, "color": "#1f77b4"}, name="route",
            ))
        fig.add_trace(go.Scattermap(
            lat=[o[0], d[0]], lon=[o[1], d[1]],
            mode="markers",
            marker={"size": 12, "color": ["#2a9d8f", "#e76f51"]},
            name="origin/destination",
        ))
        fig.update_layout(
            map={"style": "open-street-map"},
            margin=dict(t=0, b=0, l=0, r=0), height=420,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Route via **{src}**: {route['distance_m'] / 1000:.1f} km, "
            f"~{route['duration_s'] / 60:.0f} min."
        )
