"""User Explorer — per-user Π gauge, cell map, weekday×hour heatmap, places, POI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402
from dashboard.lib.maps import scatter_map  # noqa: E402

st.title("🔎 User Explorer")
st.markdown(
    "The aggregate is a distribution of people. Here are fifteen of them — the most "
    "predictable, the most exploratory, and one true routine creature per dataset."
)

featured = data.featured_users()
pi = data.pi_distributions()


def _fmt(x: float, pct: bool = True) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:.0%}" if pct else f"{x:.2f}"


label_map: dict[str, str] = {}
for r in featured.itertuples():
    why = r.why.replace("_", " ")
    pi_txt = _fmt(r.Pi_actual)
    label_map[f"{config.label_of(r.dataset)} · {r.user} — {why} (Π {pi_txt})"] = (r.dataset, r.user)

choice = st.selectbox("Featured user", options=list(label_map), index=0)
dataset, user = label_map[choice]
row = featured[(featured["dataset"] == dataset) & (featured["user"] == user)].iloc[0]

seq = data.user_seq(dataset, user)
cards = data.user_cards(dataset, user)
places = data.user_places(dataset, user)
poi = data.user_poi(dataset, user)

metrics = st.columns(6)
metrics[0].metric("Π_actual", _fmt(row["Pi_actual"]))
metrics[1].metric("Π_unc (lower bound)", _fmt(row["Pi_unc"]))
metrics[2].metric("Hours N", f"{int(row['N']):,}")
metrics[3].metric("Regularity q", _fmt(row["q"]))
metrics[4].metric("Routine cards", str(int(row["n_cards"])))
metrics[5].metric("Places", str(int(row["n_places"])))

left, right = st.columns([2, 3])
with left:
    st.subheader("Where this user sits")
    if pd.isna(row["Pi_actual"]):
        st.warning(
            "Π is undefined: this user was observed in a **single** cell "
            f"(N = {int(row['N'])}). Entropy needs at least two distinct locations — "
            "the honest answer is that their predictability is trivially 1, and the Fano "
            "inversion returns NaN. Shown as-is, not swept under the rug."
        )
    else:
        ds_pi = pi[pi["dataset"] == dataset]["Pi_actual"]
        ds_med = float(ds_pi.median())
        fig = go.Figure(
            go.Indicator(
                mode="gauge+delta+number",
                value=float(row["Pi_actual"]),
                delta={"reference": ds_med, "valueformat": ".1%"},
                number={"valueformat": ".1%"},
                gauge={
                    "axis": {"range": [0, 1], "tickformat": ".1f"},
                    "bar": {"color": config.color_of(dataset)},
                    "steps": [
                        {"range": [0, 0.4], "color": "#f0f0f0"},
                        {"range": [0.4, 0.65], "color": "#e2ecf7"},
                        {"range": [0.65, 1.0], "color": "#d2e3f4"},
                    ],
                    "threshold": {"line": {"color": "#444", "width": 2}, "value": ds_med},
                },
            )
        )
        fig.update_layout(height=280, margin=dict(t=30, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Δ vs dataset median Π_actual ({ds_med:.1%}); band edges at 0.40/0.65.")
with right:
    st.subheader("Observed cells")
    pts = seq[seq["known"] & seq["lat"].notna()]
    pts = pts.assign(dot=config.color_of(dataset))
    scatter_map(pts, lat="lat", lon="lon", color="dot")

st.subheader("Weekday × hour activity")
grid = data.weekday_hour_matrix(seq)
if grid.to_numpy().sum() == 0:
    st.caption("No known-hour activity recorded for this user.")
else:
    ylabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = px.imshow(
        np.asarray(grid), aspect="auto", color_continuous_scale="Viridis",
        labels={"x": "hour of day", "y": "", "color": "known hours"},
        x=[f"{h:02d}" for h in range(24)],
        y=ylabels,
    )
    fig.update_layout(margin=dict(t=10, b=0), height=300)
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns([3, 2])
with left:
    st.subheader("Places")
    if places.empty:
        st.caption("No places clustered for this user (grid data has no stop-level coordinates).")
    else:
        cols = [c for c in ["label", "n_visits", "mean_dwell_min", "top_venue_cat",
                            "n_venue_checkins"] if c in places.columns]
        show = places[cols].copy()
        show.columns = [c.replace("_", " ") for c in cols]
        st.dataframe(show, hide_index=True, use_container_width=True)
        if "top_venue_cat" in cols:
            st.caption("Venue categories come from Foursquare check-ins; blank = no venue match.")
with right:
    st.subheader("POI profile")
    if poi.empty or "category" not in poi.columns:
        st.caption(
            "No POI table for this dataset (YJMob100K only — it ships an 84-category POI grid)."
        )
    else:
        top = data.poi_top(poi)
        fig = px.bar(
            top[::-1], x="count", y="category", orientation="h",
            labels={"category": "", "count": "POIs in visited cells"},
        )
        fig.update_layout(showlegend=False, margin=dict(t=10, b=0), height=380)
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Routine cards")
if cards.empty:
    st.caption("No routine cards mined for this user — the trigger rule would stay silent.")
else:
    show = cards[["weekday", "bucket_str", "n_trips", "support", "confidence", "stability",
                  "o_label", "d_label"]].copy()
    show["weekday"] = show["weekday"].map(lambda w: data.WEEKDAYS[int(w)])
    show.columns = ["weekday", "bucket", "n trips", "weeks", "confidence", "stability",
                    "origin", "destination"]
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption("Cards = (origin, destination, weekday, 15-min bucket) tuples with support stats. "
               "Try them live on the Suggest Demo page.")
