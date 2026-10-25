"""The Question — hero comparison, plain-words entropy explainer, dataset cards, map."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402
from dashboard.lib.maps import scatter_map  # noqa: E402

st.title("🎯 The Question")

summary = data.dataset_summary()

lo = float(summary["pi_actual_mean"].min())
hi = float(summary["pi_actual_mean"].max())
n_users = int(summary["n_users"].sum())

st.markdown(
    f"""
    ## Song *et al.* (2010): **93%**.
    ### Six datasets, {n_users:,} users later: **~{0.5 * (lo + hi):.0%}**
    *(dataset means run {lo:.0%} – {hi:.0%}; the GPS cohort closest to Song's setting
    lands near 64%)*
    """
)

left, right = st.columns([2, 3])
with left:
    st.markdown(
        """
        ### In plain words
        Collect where a person spends each hour, and compress that string of places.
        A life that *compresses well* is predictable: same commute, same Thursday evening.
        The Fano bound converts the compressed size into a percentage — **the best any
        algorithm could ever score** when guessing the next hour, even knowing everything
        about the person's past.
        """
    )
with right:
    st.markdown(
        """
        ### The ladder of entropies
        | entropy | question | bound |
        |---|---|---|
        | S_rand | "locations are i.i.d. by frequency" | Π_rand (floor) |
        | S_unc | "no temporal context, temporal Shannon" | Π_unc (lower bound) |
        | S_actual | "the real, compressible sequence (Lempel-Ziv)" | **Π_actual (ceiling)** |

        Ordering: S_rand ≥ S_unc ≥ S_actual ⇒ Π_rand ≤ Π_unc ≤ Π_actual.
        Song's 93% is an **actual-entropy** number — so the headline here is always
        **Π_actual**, never Π_unc (medians 0.33–0.46, a different question).
        """
    )

st.divider()
st.subheader("The seven dataset cards")
st.caption(
    "Curated stats are over ALL users; the modelling cohort "
    "(meets 30 active days + 5 distinct cells) is shown separately."
)

cards_per_row = 4
for start in range(0, len(summary), cards_per_row):
    cols = st.columns(cards_per_row)
    chunk = summary.iloc[start : start + cards_per_row]
    for col, (_, r) in zip(cols, chunk.iterrows(), strict=False):
        meta = config.DATASETS.get(r["dataset"], {})
        city = meta.get("city") or "🌐 global"
        with col:
            st.markdown(
                f"""
                <div style="border-left: 4px solid {config.color_of(r['dataset'])};
                            padding: 0.4em 0.8em; margin-bottom: 0.6em;
                            background: rgba(128,128,128,0.06); border-radius: 4px;">
                <b>{config.label_of(r['dataset'])}</b><br>
                <small>{city} · {meta.get('provider', '')}</small><br>
                <span style="font-size: 1.5em;"><b>{r['pi_actual_mean']:.0%}</b></span>
                <small>mean Π_actual</small><br>
                <small>{int(r['n_users']):,} users · cohort {int(r['n_cohort']):,}<br>
                best: <code>{r['best_baseline']}</code> {r['best_baseline_top1']:.0%} top-1 ·
                Fano {r['fano_frac']:.0%}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.subheader("Where in the world")
city_rows = summary[summary["dataset"].map(lambda d: config.DATASETS[d]["scope"] == "city")]
map_rows = []
for _, r in city_rows.iterrows():
    meta = config.DATASETS[r["dataset"]]
    lat, lon = config.CITY_COORDS[meta["city"]]
    map_rows.append(
        {"lat": lat, "lon": lon, "dataset": config.label_of(r["dataset"]),
         "color": config.color_of(r["dataset"]),
         "size": max(float(r["n_users"]) / max(city_rows["n_users"]) * 40, 12)}
    )
scatter_map(pd.DataFrame(map_rows), lat="lat", lon="lon", color="color", size="size")
global_rows = summary[summary["dataset"].map(lambda d: config.DATASETS[d]["scope"] == "global")]
if not global_rows.empty:
    st.caption(
        "🌐 Global-scope datasets ("
        + ", ".join(config.label_of(d) for d in global_rows["dataset"])
        + ") have users on every continent — no single pin; see their dist_km caveat in the "
        "Model Arena."
    )

st.divider()
st.markdown(
    "**So is the 93% wrong?** Not exactly — it was measured on 70 GPS users in one city with a "
    "particular entropy estimator. Across regimes it becomes a *range*: dense synthetic grids "
    "reach ~0.63, check-in data ~0.44–0.58, curated GPS cohorts ~0.65. The *limits of "
    "predictability* are real, but they are a property of the population, not a universal "
    "constant. The next pages show the distributions behind these means — and the people "
    "at both tails."
)
