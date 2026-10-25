"""Predictability Ceiling — Π_actual distributions, Fano compliance, entropy trio."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402

st.title("📐 The Predictability Ceiling")
st.markdown(
    "Per-user **Π_actual** — the Fano inversion of the *actual* (LZ) entropy — is the "
    "apples-to-apples ceiling with Song et al.'s 93%. Trio ordering S_rand ≥ S_unc ≥ S_actual "
    "implies Π_rand ≤ Π_unc ≤ Π_actual — **Π_unc is a lower-bound context number, "
    "never the ceiling**."
)

pi = data.pi_distributions()
keys = st.multiselect(
    "Datasets",
    options=list(config.DATASETS),
    default=list(config.DATASETS),
    format_func=config.label_of,
)
if not keys:
    st.info("Pick at least one dataset.")
    st.stop()

sub = pi[pi["dataset"].isin(keys)]
cmap = {k: config.color_of(k) for k in keys}

left, right = st.columns(2)
with left:
    st.subheader("Π_actual distribution")
    counts = (
        sub.groupby(["dataset", pd.cut(sub["Pi_actual"], bins=40)], observed=True)["user"]
        .count()
        .rename("n")
        .reset_index()
    )
    counts["bin_mid"] = counts["Pi_actual"].apply(lambda iv: float(iv.left))
    fig = px.bar(
        counts, x="bin_mid", y="n", color="dataset", barmode="overlay",
        color_discrete_map=cmap,
        labels={"bin_mid": "Π_actual", "n": "users"},
    )
    fig.update_layout(legend_title_text=None, margin=dict(t=10, b=0), bargap=0.02)
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Π_actual ECDF")
    fig = px.ecdf(sub, x="Pi_actual", color="dataset", color_discrete_map=cmap)
    fig.update_layout(legend_title_text=None, margin=dict(t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Regularity q vs Π_actual")
st.caption(
    "q is the fraction of hours spent in the single most-frequent cell — "
    "raw inertia, not predictability."
)
scatter = data.pi_vs_q(sub, keys=keys)
fig = px.scatter(
    scatter, x="q", y="Pi_actual", color="dataset", opacity=0.35, color_discrete_map=cmap,
    labels={"q": "regularity q", "Pi_actual": "Π_actual"},
)
fig.update_layout(legend_title_text=None, margin=dict(t=10, b=0), height=460)
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns([2, 3])
with left:
    st.subheader("Fano-bound compliance")
    fano = data.fano_frac_table(sub)
    fano["label"] = [config.label_of(d) for d in fano["dataset"]]
    fig = px.bar(
        fano, x="fano_frac", y="label", orientation="h", text_auto=".3f",
        color="label", color_discrete_map=cmap,
        labels={"fano_frac": "share of users", "label": ""},
    )
    fig.add_vline(x=1.0, annotation_text="bound", line_dash="dot")
    fig.update_layout(showlegend=False, margin=dict(t=10, b=0), xaxis_range=[0, 1.05])
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.markdown(
        """
        **Why this panel exists.** The Fano bound turns entropy into a guessing accuracy:
        a user whose *uncertainty* entropy is S_unc gets Π_unc — a *lower bound* on
        predictability. The actual entropy S_actual (compressibility of the real sequence)
        gives Π_actual. fano_frac is the share of users where the ordering holds, i.e.
        Π_actual ≥ Π_unc. It stays ≈1.0 everywhere — except Gowalla (~0.86), where a wave
        of never-revisiting users sits at the Fano floor (Π ≈ 1/N by construction).
        """
    )

st.subheader("Entropy trio (medians per user)")
trio = data.entropy_medians(sub)
trio["label"] = [config.label_of(d) for d in trio["dataset"]]
long = trio.melt(
    id_vars=["dataset", "label"], value_vars=["S_rand", "S_unc", "S_actual"],
    var_name="entropy", value_name="bits",
)
order = ["S_rand", "S_unc", "S_actual"]
fig = px.bar(
    long, x="label", y="bits", color="entropy", barmode="group",
    category_orders={"entropy": order},
    color_discrete_sequence=px.colors.qualitative.Set2,
    labels={"label": "", "bits": "bits (median)"},
)
fig.update_layout(legend_title_text=None, margin=dict(t=10, b=0))
st.plotly_chart(fig, use_container_width=True)
bad = trio[~trio["monotone"]]
if not bad.empty:
    st.warning("Ordering violation in: " + ", ".join(bad["dataset"]))
else:
    st.success(
        "S_rand ≥ S_unc ≥ S_actual holds for every dataset — so Π_rand ≤ Π_unc ≤ Π_actual. "
        "The trio is internally consistent, and Π_actual is the top of the ladder."
    )

if st.toggle("Show under-the-hood numbers", value=False):
    stats = data.pi_stats_table(sub)
    stats["label"] = [config.label_of(d) for d in stats["dataset"]]
    st.dataframe(stats, use_container_width=True)
