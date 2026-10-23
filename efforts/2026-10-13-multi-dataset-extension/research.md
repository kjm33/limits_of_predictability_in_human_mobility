# Research Note: Additional Mobility Datasets

Date: 2026-10-13
Goal: Based on what worked and what didn't on GeoLife, find open datasets that fix the pipeline's documented bottlenecks (sparsity, small cohort, data-starved deep models) and enable new analyses (predictability under disruption, social+mobility graphs, DeepMove-benchmark validation).

## 1. Motivation — what worked / what didn't on GeoLife

| Outcome | Evidence | Dataset requirement it implies |
|---|---|---|
| Sparsity is the core limit | median hourly missingness q = 0.905; cohort ∧ q≤0.70 = only 3 users (nb 02 §1); Π correlates with q (small-N artefact), Π = 0.64 vs paper's 0.93 | Dense per-user coverage (low q), long duration |
| Deep models are data-limited | ~48.5k train windows over 5,364 classes; Transformer top-1 0.260 (+0.03 over Markov); "the limit is in the data, not the model class" (nb 06) | Many users × many records |
| GraphSeq collapsed | frozen PPR embeddings + linear head can't express 5,364-class distribution (nb 06) | Cell context features (e.g. POI vectors) |
| Routines coverage-limited | 154/176 users never fire a trigger; cards dominated by home stays (nb 04) | Dense 24/7 logging over weeks |
| Entropy/baselines/graph predictors work | S ≤ S_unc ≤ S_rand holds 100% in cohort; markov3_col top-1 0.231; RW predictor wins trip task (nb 02/03/05) | Abstract cell sequences are enough |

## 2. Verified candidate datasets (canonical pages fetched 2026-10-13)

### Tier 1 — open, direct download, high impact

| Dataset | Users | Period | Records | Access | Verdict |
|---|---|---|---|---|---|
| **YJMob100K** (LY Corp/Yahoo Japan + MIT; Yabe et al., Sci Data 11:397, 2024) | 100,000 (Dataset1) / 25,000 (Dataset2) | 75 days, masked dates (D1); 60d + 15d emergency (D2) | 111,535,175 | Zenodo DOI 10.5281/zenodo.10836269 | **Primary addition** |
| **Foursquare NYC+Tokyo** (TSMC'15, Dingqi Yang) | ~1,000 (dense subset) | Apr 2012 – Feb 2013 | 227,428 NYC + 573,703 Tokyo check-ins | Direct download: sites.google.com/site/yangdingqi/home/foursquare-dataset | **DeepMove benchmark** |
| **Foursquare Global** (TIST'15 / WWW'19) | 266,909 (114,324 in WWW'19) | 18–22 months | 33M (raw 90M in WWW'19) + social graphs | Same page, ~775 MB / 2.68 GB | Later, for scale |
| **Gowalla** (SNAP, Cho/Myers/Leskovec KDD'11) | 196,591 | Feb 2009 – Oct 2010 | 6,442,890 check-ins + 950,327 friendship edges | Direct: loc-gowalla_totalCheckins.txt.gz + loc-gowalla_edges.txt.gz | **Graphs module** |
| **Brightkite** (SNAP, same paper) | 58,228 | Apr 2008 – Oct 2010 | 4,491,143 check-ins + 214,078 edges | Direct: loc-Brightkite_totalCheckins.txt.gz + loc-Brightkite_edges.txt.gz | **Graphs module** |

**YJMob100K details** (Zenodo record):
- Format: `user-id, day, timeslot, x, y` — 48 half-hour timeslots/day, 500 m grid 200×200 (x,y ∈ 1..200), day 0–74.
- Dataset2: 25k users; day 27 = natural disaster (authors advise dropping); 15-day emergency period after.
- POI context: `cell_POIcat.csv.gz` — 85-dim anonymous POI-category count vector per cell (+ 85 category names in `POI_datacategories.csv`).
- Sampling adaptive (~5% of population; ~100k unique users/slot during 6am–8pm) → dense where it matters; census-validated (Pearson 0.781 cell-level, 0.967 admin).
- Lineage: HuMob Challenge 2023 (SIGSPATIAL) + SIGSPATIAL GIS Cup 2025.
- Caveats: pre-discretized (no raw GPS → no stay re-detection, no transport modes), city/coords/dates masked → `routing`/`suggest`/folium inapplicable; `dist_km` needs grid metric (cell steps × 500 m).

**Foursquare NYC/Tokyo details**: check-ins with GPS coords + venue categories; canonical benchmark for DeepMove (which `deep.py` reimplements) — direct external validation of our model implementations.

**Gowalla/Brightkite details**: format `[user] [check-in time ISO8601] [lat] [lon] [location id]`; Brightkite location id is a hex hash. Friendship edge lists enable social+mobility analysis for `graphs` module. Known LBSN pathologies: check-in bursts (gaming), sparse per-user coverage.

### Tier 2 — dense but small-N or restricted

| Dataset | Why interesting | Blocker |
|---|---|---|
| StudentLife (Dartmouth, 2013) | 48 students × 10 weeks, dense 24/7 sensing incl. GPS → lowest-q data, tests routines coverage failure | Small N |
| College Experience Study (Dartmouth 2017–22) | 200 students × 4 years, de-identified, released | Contact A. Campbell; tier 2 |
| Reality Mining (MIT 2004–05) | Tower-level ~3 km² — like-for-like with Song et al. Π=0.93 | Registration; old; 100 subjects |
| Nokia MDC (Idiap) | dense multimodal | Restricted (already rejected v1); page moved |
| D4D/Orange, Privamov, SafeGraph/Meta, Cuebiq, Veraset, UK Biobank | — | Restricted/discontinued → skip |

### Tier 3 — vehicles, not humans

NYC TLC (open parquet, 2009–), Porto taxi (Kaggle PKDD'15, 442 taxis), T-Drive (10,357 taxis but 1 week only), CitiBike. Useful only to stress-test trip-level/graph predictors; weak for "human predictability" claims.

## 3. Integration surface (verified against code)

The modeling stack (`entropy`, `baselines`, `deep`, graphs' predictors) runs off abstract integer `cell_idx` + string cell tokens — only these are geo-coupled:
1. `ingest` → `points.parquet` (lat/lon hard; haversine QC)
2. `sequences.hourly_sequences` (lat/lon → H3) + `cell_vocab` (H3 → centroid)
3. `stay`/`routines`/`suggest` (haversine + DBSCAN) — real-coords datasets only
4. `dist_km` metrics need vocab lat/lon (`cells_r8.parquet` accepts any coords as-is)

- **YJMob100K**: bypass ingest/stay/h3map; write `seq_hourly.parquet` + `cells_*.parquet` with synthetic grid centroids (500 m spacing → plausible dist) directly. Entropy/baselines/deep work unmodified; trips module N/A.
- **Foursquare NYC/Tokyo, Gowalla/Brightkite**: new ingest adapters to the `user, ts, lat, lon, alt_m, seg_id, mode` contract (mode all-null; seg_id from 20-min gap rule as-is); full pipeline incl. stays/routines/maps applies. Venue categories + friendship edges are new artifacts needing new columns/modules (`graphs.build_global_graph` is the natural hook for social edges).

## 4. Decisions

- Proceed with integration plans for **YJMob100K**, **Foursquare NYC/Tokyo**, **Gowalla/Brightkite** (chosen 2026-10-13).
- Foursquare Global deferred until the NYC/Tokyo adapter proves out.
- Priority rationale: YJMob100K fixes sparsity + N + enables emergency-period predictability-shift analysis (novel angle vs the Π limit); NYC/Tokyo validates DeepMove-style `deep.py` on its home benchmark; Gowalla/Brightkite feed the social-graph extension.

## 5. Sources

- YJMob100K: https://doi.org/10.5281/zenodo.10836269 ; paper https://www.nature.com/articles/s41597-024-03370-w
- Foursquare: https://sites.google.com/site/yangdingqi/home/foursquare-dataset
- Gowalla/Brightkite: https://snap.stanford.edu/data/loc-Gowalla.html , https://snap.stanford.edu/data/loc-Brightkite.html
- StudentLife: https://studentlife.cs.dartmouth.edu/ ; College Experience Study via A.T.P. Campbell
- Method note: search engines were unreliable for these queries; all facts verified by fetching canonical pages directly.
