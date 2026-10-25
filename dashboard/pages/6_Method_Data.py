"""Method & Data — pipeline, provenance, cohort, limitations, repro commands."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.lib import config, data  # noqa: E402

st.title("🛠️ Method & Data")

st.header("Pipeline at a glance")
st.markdown(
    """
    ```
    ingest ─► stays ─► H3 r9 ─► hourly sequences ─┬─► entropy (S_rand/S_unc/S_actual → Π)
    (PLT/grid/  (250 m,  (r8 grid   (most-frequent ├─► baselines (freq/time/Markov 1-3)
     check-ins)  10 min,  via       cell per hour) ├─► routines (DBSCAN places, cards)
                 20-min   parent)                  ├─► graphs (transitions, PPR)
                 merge)                            └─► deep (DeepMove, Transformer, GraphSeq)
    ```
    Stops are assigned at **H3 resolution 9** (~0.10 km²); the analysis grid is **r8**
    (~0.74 km²), *derived by* `h3.cell_to_parent` — point-derived parents mismatch ~7% of
    cells because H3 does not nest perfectly. Splits are per-user chronological (last 20%
    of hours = test).
    """
)

st.header("Dataset provenance")
summary = data.dataset_summary()
rows = []
for _, r in summary.iterrows():
    meta = config.DATASETS[r["dataset"]]
    rows.append({
        "dataset": config.label_of(r["dataset"]),
        "source": meta["provider"],
        "scope": meta["scope"],
        "users": int(r["n_users"]),
        "cohort": int(r["n_cohort"]),
        "Π_actual (mean)": r["pi_actual_mean"],
    })
prov = pd.DataFrame(rows)
st.dataframe(
    prov,
    hide_index=True,
    use_container_width=True,
    column_config={
        "users": st.column_config.NumberColumn(format=",.0f"),
        "cohort": st.column_config.NumberColumn(format=",.0f"),
        "Π_actual (mean)": st.column_config.NumberColumn(format="%.3f"),
    },
)
st.markdown(
    """
    | key | what it is |
    |---|---|
    | GeoLife | GPS trajectories, Beijing, 2007–2012 (182 users) — the Song-2010 setting |
    | YJMob100K #1/#2 | *synthetic* 500 m-grid mobility, Tokyo-style, 100k/25k users, 30-min slots |
    | Foursquare NYC/Tokyo | TSMC2014 check-ins — venue visits, no interpolation between them |
    | Gowalla / Brightkite | SNAP global check-in networks — worldwide footprints |
    """
)

st.header("Cohort rules")
st.markdown(
    """
    A user joins the modelling cohort with **≥ 30 active days** and **≥ 5 distinct r8 cells**
    (`MIN_ACTIVE_DAYS`, `MIN_DISTINCT_R8` in `mobility.config`). Cohort sizes differ wildly —
    62 (Foursquare NYC) to 99,974 (YJMob100K #1) — which is exactly why the headline stats
    above are computed over **all** users and the cohort is reported next to them.
    """
)

st.header("Limitations — read before quoting numbers")
st.markdown(
    """
    - **SNAP global footprint inflates dist_km.** Gowalla/Brightkite users check in across
      continents; a 550–650 km distance error means "wrong country", not "wrong street".
      Compare those datasets on top-1 accuracy, not kilometres.
    - **Gowalla's fano_frac ≈ 0.86** is not a bug: a wave of never-revisiting users sits at
      the Fano floor (Π = 1/N by construction), where Π_unc can nudge above Π_actual.
    - **Check-in data has no interpolation.** Between check-ins the location is unknown —
      sequences are sparser and harder than GPS traces, so lower Π here partly reflects the
      sensor, not the human.
    - **Π_actual is a ceiling, not a model score.** No predictor reaches it; the best
      baselines land at 0.18–0.51 top-1. The gap between 0.65 and 0.29 is *the* open problem.
    - **YJMob100K is synthetic.** Realistic marginals, generated ground truth.
    """
)

st.header("Reproduce it")
left, right = st.columns(2)
with left:
    st.markdown("**Pipeline stages** (each reads predecessors from `data/processed/`):")
    st.code(
        "uv run python scripts/run_stage.py <stage> --dataset <key>\n"
        "# stages: ingest sequences entropy baselines routines\n"
        "#         graphs deep   (yjmob/checkins ingest via -m mobility.yjmob / .checkins)",
        language="bash",
    )
    st.markdown("**This dashboard:**")
    st.code("uv run --group demo streamlit run dashboard/app.py", language="bash")
with right:
    st.markdown("**Suggestion CLI** (the page-5 engine):")
    st.code(
        'uv run python -m mobility.suggest --user 022 --now "Mon 15:14" --route',
        language="bash",
    )
    st.markdown("**Notebooks** (numbered walk-through of the same stages):")
    st.code(
        "\n".join([
            "01_data_qc", "02_entropy_predictability", "03_baselines",
            "04_routines", "05_graphs", "06_deep_learning", "07_demo_curation",
        ]),
        language="text",
    )

st.caption(
    "Everything on these pages comes from the curated package "
    "`data/processed/dashboard/` — pre-aggregated parquets only; the heavy pipeline outputs "
    "(e.g. YJMob100K's 180M-row hourly sequences) are never loaded here."
)
