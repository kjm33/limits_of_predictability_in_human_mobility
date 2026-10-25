"""Model Arena — leaderboards, winner-flips-by-regime, deep vs baseline, random walk."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402

st.title("🏟️ Model Arena")
st.markdown(
    "Eight baselines, random-walk references and the deep models fight for top-1 accuracy "
    "on the same per-user chronological splits. **There is no universal winner — the crown "
    "flips with the data regime.**"
)

lb = data.leaderboards()
summary = data.dataset_summary()

MODEL_COLORS = {
    "freq": "#8c8c8c", "time": "#5a9bd5", "rw_trip_dest": "#c9c9c9",
    "markov1": "#f4a261", "markov2": "#e76f51", "markov3": "#d67ba8",
    "markov1_col": "#2a9d8f", "markov2_col": "#1f7a70", "markov3_col": "#145c55",
    "deepmove": "#9b5de5", "temporal_transformer": "#f15bb5", "graphseq": "#fee440",
}

dataset = st.selectbox(
    "Dataset", options=list(lb["dataset"].unique()), index=0, format_func=config.label_of,
)
board = data.leaderboard_for(lb, dataset)
show = board[["source_badge", "model", "top1", "top3", "dist_km", "n_eval_sum"]].copy()
show.columns = ["source", "model", "top-1", "top-3", "dist err (km)", "n eval"]
st.dataframe(
    show,
    hide_index=True,
    use_container_width=True,
    column_config={
        "top-1": st.column_config.NumberColumn(format="%.3f"),
        "top-3": st.column_config.NumberColumn(format="%.3f"),
        "dist err (km)": st.column_config.NumberColumn(format="%.0f"),
        "n eval": st.column_config.NumberColumn(format=",.0f"),
    },
)
st.caption(
    "n_eval-weighted means over per-user chronological test splits (test_frac = 0.2). "
    "Row counts differ by dataset — e.g. YJMob100K #1 has no deep or random-walk entries "
    "(100k users × deep models didn't fit the CPU budget)."
)

left, right = st.columns(2)
with left:
    st.subheader("The winner flips by regime")
    winners = data.winner_table(summary)
    fig = px.bar(
        winners, x="dataset", y="best_baseline_top1", color="best_baseline",
        color_discrete_map=MODEL_COLORS,
        labels={"dataset": "", "best_baseline_top1": "best baseline top-1",
                "best_baseline": "model"},
        category_orders={"dataset": list(winners["dataset"])},
    )
    fig.update_layout(margin=dict(t=10, b=0), legend_title_text=None)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "markov1 on the huge synthetic grid (YJMob100K), markov2_col on GPS (GeoLife), "
        "time-conditioned on sparse check-ins (NYC, Gowalla), plain frequency on Foursquare "
        "Tokyo, and the collective markov1 on Brightkite's dense-repeat regime."
    )
with right:
    st.subheader("Deep vs best baseline")
    deep_rows = lb[lb["source"] == "deep"]
    if deep_rows.empty:
        st.info("No deep-model rows in this build (see YJMob100K #1).")
    else:
        deep_sets = [d for d in lb["dataset"].unique() if not lb[
            (lb["dataset"] == d) & (lb["source"] == "deep")
        ].empty]
        pick = st.selectbox("dataset with deep rows", deep_sets, format_func=config.label_of,
                            index=deep_sets.index(dataset) if dataset in deep_sets else 0)
        cmp_df = data.deep_vs_baseline(lb, pick)
        fig = px.bar(
            cmp_df, x="model", y="top1", color="model",
            color_discrete_map=MODEL_COLORS,
            labels={"model": "", "top1": "top-1"},
            category_orders={"model": list(cmp_df.sort_values("top1", ascending=False)["model"])},
        )
        fig.update_layout(showlegend=False, margin=dict(t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
        best_base = cmp_df[cmp_df["source"] == "baseline"]["top1"].iloc[0]
        best_deep = cmp_df[cmp_df["source"] == "deep"]["top1"].max()
        delta = best_deep - best_base
        st.caption(
            f"Best deep beats the best baseline by {delta:+.3f} top-1 — a marginal gain for "
            "an order of magnitude more compute. The ceiling is informational, not architectural."
        )

st.subheader("Random-walk references")
rw = board[board["source"] == "rw"]
if rw.empty:
    st.caption("No random-walk rows for this dataset.")
else:
    st.dataframe(
        rw[["model", "top1", "top3", "dist_km"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "top1": st.column_config.NumberColumn(format="%.3f"),
            "top3": st.column_config.NumberColumn(format="%.3f"),
            "dist_km": st.column_config.NumberColumn(format="%.0f"),
        },
    )

st.warning(
    "**Distance-error caveat.** dist_km on the SNAP check-in datasets (Gowalla, Brightkite) "
    "runs to hundreds of km because those users travel globally — an error of 550 km is a "
    "wrong *continent*, not a wrong street. Judge city datasets on dist_km, global ones on top-1."
)
