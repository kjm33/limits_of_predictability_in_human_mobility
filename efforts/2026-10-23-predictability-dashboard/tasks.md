# Tasks — Predictability dashboard

<!-- Implementation plan + progress tracker. Updated at END of each session (anti-drift rule). -->

**Status: done (2026-10-23)** — all tasks complete; acceptance verified by owner
(134 tests green, ruff clean incl. `dashboard/`, server smoke + all 6 pages 200).
Pages built in plan order 2→3→4→1→5→6. Deviations: `st.scatter_map` gone in
streamlit ≥1.6x → `lib/maps.py` compat wrapper; Suggest page adds dataset
`routines.parquet` users because no fsq/gowalla featured pick had cards.

## Plan

1. Start only after `2026-10-23-demo-curation` closes.
2. Scaffold: `demo` dep group, `dashboard/lib/` (registry + loaders, tests first),
   `app.py` + 6 page stubs.
3. Pages in order: 2 (Ceiling) → 3 (Arena) → 4 (User Explorer) → 1 (Question) →
   5 (Suggest) → 6 (Method) — data-heavy pages first to shake out loader needs.
4. Perf pass: `@st.cache_data` everywhere, verify warm-cache loads < 2 s.
5. README demo section; acceptance commands; close out.

## Tasks

- [x] `demo` dep group + scaffold (lib, app, pages, tests) — 2026-10-23
- [x] lib/config.py dataset registry + lib/data.py loaders with tests — 2026-10-23
- [x] page 2 Predictability_Ceiling — 2026-10-23
- [x] page 3 Model_Arena — 2026-10-23
- [x] page 4 User_Explorer — 2026-10-23
- [x] page 1 The_Question — 2026-10-23
- [x] page 5 Suggest_Demo — 2026-10-23
- [x] page 6 Method_Data — 2026-10-23
- [x] README demo section + acceptance: pytest/ruff/streamlit smoke green — 2026-10-23

## Blockers / open questions

- none open. Note (2026-10-23): `st.scatter_map` no longer exists in streamlit
  (≥1.6x ships the pydeck `st.map` again) — `dashboard/lib/maps.py` wraps
  whichever element the installed version provides, so pages run unchanged on
  any streamlit.
