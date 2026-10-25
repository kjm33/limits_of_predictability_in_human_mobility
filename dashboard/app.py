"""How predictable is human movement? — portfolio dashboard.

    uv run --group demo streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root for dashboard.*

import streamlit as st  # noqa: E402
from dashboard.lib import config  # noqa: E402

st.set_page_config(
    page_title="Limits of Predictability — Human Mobility",
    page_icon="🧭",
    layout="wide",
)

st.title("🧭 How predictable is human movement?")
st.markdown(
    """
    Song *et al.* (2010) put a **93%** ceiling on where a person will be next.
    Reproducing that analysis across **six datasets** — GPS traces, grid data and
    check-ins, 234k+ users — the honest ceiling lands at **~0.44–0.65**.
    Explore where the number comes from, which models fight for it, and meet the
    people behind the distribution.
    """
)

pages = {
    "1": ("1_The_Question", "🎯 The Question"),
    "2": ("2_Predictability_Ceiling", "📐 Predictability Ceiling"),
    "3": ("3_Model_Arena", "🏟️ Model Arena"),
    "4": ("4_User_Explorer", "🔎 User Explorer"),
    "5": ("5_Suggest_Demo", "🚗 Suggest Demo"),
    "6": ("6_Method_Data", "🛠️ Method & Data"),
}
cols = st.columns(6)
for col, (_, (slug, title)) in zip(cols, pages.items(), strict=True):
    with col:
        st.page_link(f"pages/{slug}.py", label=title, use_container_width=True)

st.divider()
st.caption(
    "Built on the curated package in `data/processed/dashboard/` — "
    f"{len(config.DATASETS)} dataset cards, Π = Fano predictability from actual entropy "
    "(apples-to-apples with Song et al.)."
)
