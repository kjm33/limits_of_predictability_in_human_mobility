"""Mobility graphs: per-user H3 transition graphs, global prior, random-walk predictor.

Per-user directed weighted graph over H3-r8 cells: nodes carry dwell semantics
(home/work inference), edges carry transition counts, mean travel time and a
24-bin departure-hour histogram (serialized as a comma-separated string for
GraphML compatibility). Also: pooled global transition graph, graph analytics,
and a teleport-smoothed random-walk next-cell predictor evaluated like the
Phase-3 baselines (top-1/top-3 accuracy, centroid distance error).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities

from . import config

RW_COLUMNS = ["user", "method", "n_eval", "top1_acc", "top3_acc", "dist_err_km"]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    r = 6_371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


def _temporal_split(n: int, test_frac: float) -> int:
    """Index of the first held-out observation (always at least 1 train row)."""
    return min(max(int(np.floor(n * (1.0 - test_frac))), 1), n)


def build_user_graph(stops: pd.DataFrame, trips: pd.DataFrame, user: str) -> nx.DiGraph:
    """Directed weighted H3-r8 transition graph for one user.

    Nodes: r8 cells visited via stops (and trip endpoints), with attrs lat, lon,
    n_stops, total_dwell_min, mean_arrive_hour, night_dwell_min (arrive 0-6h),
    work_dwell_min (weekday arrive 9-17h). Cells seen only as trip endpoints get
    zero dwell stats and mean_arrive_hour = -1.

    Edges: one increment per trip o_h3_r8 -> d_h3_r8 with attrs count,
    travel_min_mean and hour_hist (24-bin departure-hour histogram as a
    comma-separated string, for GraphML compatibility).
    """
    import h3

    s = stops[stops["user"] == user]
    t = trips[trips["user"] == user].sort_values("depart")
    sub = t.dropna(subset=["o_h3_r8", "d_h3_r8"])

    g = nx.DiGraph()
    for cell, grp in s.groupby("h3_r8"):
        hours = grp["arrive"].dt.hour
        dows = grp["arrive"].dt.dayofweek
        dwell = grp["dwell_min"].astype("f8")
        g.add_node(
            cell,
            lat=float(grp["lat"].mean()),
            lon=float(grp["lon"].mean()),
            n_stops=int(len(grp)),
            total_dwell_min=float(dwell.sum()),
            mean_arrive_hour=float(hours.mean()),
            night_dwell_min=float(dwell[hours < 6].sum()),
            work_dwell_min=float(dwell[(dows < 5) & (hours >= 9) & (hours < 17)].sum()),
        )
    for cell in set(sub["o_h3_r8"]) | set(sub["d_h3_r8"]):
        if cell in g:
            continue
        lat, lon = h3.cell_to_latlng(cell)
        g.add_node(
            cell,
            lat=float(lat),
            lon=float(lon),
            n_stops=0,
            total_dwell_min=0.0,
            mean_arrive_hour=-1.0,
            night_dwell_min=0.0,
            work_dwell_min=0.0,
        )

    agg: dict[tuple[str, str], dict] = {}
    for o, d, travel_min, hour in zip(
        sub["o_h3_r8"], sub["d_h3_r8"], sub["travel_min"], sub["depart"].dt.hour, strict=True
    ):
        rec = agg.setdefault(
            (o, d), {"count": 0, "travel_min": 0.0, "hist": np.zeros(24, dtype=int)}
        )
        rec["count"] += 1
        rec["travel_min"] += float(travel_min)
        rec["hist"][int(hour)] += 1
    for (o, d), rec in agg.items():
        g.add_edge(
            o,
            d,
            count=int(rec["count"]),
            travel_min_mean=rec["travel_min"] / rec["count"],
            hour_hist=",".join(str(int(v)) for v in rec["hist"]),
        )
    return g


def build_all_graphs(
    stops: pd.DataFrame, trips: pd.DataFrame, out_dir: str | Path | None = None
) -> dict[str, nx.DiGraph]:
    """Per-user graphs (over all users present); optionally written as GraphML."""
    users = sorted(set(stops["user"]) | set(trips["user"]))
    graphs = {user: build_user_graph(stops, trips, user) for user in users}
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for user, g in graphs.items():
            nx.write_graphml(g, out_dir / f"{user}.graphml")
    return graphs


def build_global_graph(trips: pd.DataFrame) -> nx.DiGraph:
    """Pooled cross-user o_h3_r8 -> d_h3_r8 transition counts (spatial prior).

    Nodes carry lat/lon cell centroids; edges carry count only.
    """
    import h3

    sub = trips.dropna(subset=["o_h3_r8", "d_h3_r8"])
    g = nx.DiGraph()
    if sub.empty:
        return g
    counts = sub.groupby(["o_h3_r8", "d_h3_r8"], sort=True).size()
    for (o, d), n in counts.items():
        g.add_edge(o, d, count=int(n))
    for cell in g.nodes:
        lat, lon = h3.cell_to_latlng(cell)
        g.nodes[cell]["lat"] = float(lat)
        g.nodes[cell]["lon"] = float(lon)
    return g


def infer_home_work(g: nx.DiGraph) -> dict:
    """Home = cell with max night (0-6h) dwell; work = max weekday 9-17h dwell.

    Returns {"home": cell | None, "work": cell | None}; a value is None when
    there is no positive evidence (no night / no weekday-work dwell anywhere).
    """

    def _argmax(attr: str) -> str | None:
        best, best_val = None, 0.0
        for node, attrs in g.nodes(data=True):
            try:
                val = float(attrs.get(attr, 0.0))
            except (TypeError, ValueError):
                continue
            if val > best_val:
                best, best_val = node, val
        return best

    return {"home": _argmax("night_dwell_min"), "work": _argmax("work_dwell_min")}


def graph_analytics(g: nx.DiGraph) -> dict:
    """Size, density, centrality leaders, community count, mean clustering.

    Communities via greedy modularity on the undirected count-weighted
    projection; betweenness uses a 500-pivot sample when n > 1000.
    """
    n_nodes, n_edges = g.number_of_nodes(), g.number_of_edges()
    out: dict = {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "density": nx.density(g) if n_nodes else 0.0,
        "top_pagerank": None,
        "top_betweenness": None,
        "n_communities": 0,
        "mean_clustering": 0.0,
    }
    if not n_nodes:
        return out
    pr = nx.pagerank(g, weight="count")
    out["top_pagerank"] = max(pr, key=pr.__getitem__)
    bc = nx.betweenness_centrality(g, k=None if n_nodes <= 1000 else 500)
    out["top_betweenness"] = max(bc, key=bc.__getitem__)

    und = nx.Graph()
    for u, v, attrs in g.edges(data=True):
        w = float(attrs.get("count", 1))
        if und.has_edge(u, v):
            und[u][v]["weight"] += w
        else:
            und.add_edge(u, v, weight=w)
    out["n_communities"] = len(greedy_modularity_communities(und, weight="weight"))
    out["mean_clustering"] = float(nx.average_clustering(und)) if n_nodes > 1 else 0.0
    return out


class RandomWalkPredictor:
    """Teleport-smoothed first-order random-walk next-cell predictor.

    P(v | u) = (1 - teleport) * N(u, v) / N(u, .) + teleport * freq(v) / freq(.),
    where freq is the user's cell marginal. An unseen current cell falls back to
    the user marginal; an unseen user falls back to the global marginal.
    """

    def __init__(
        self,
        transitions: dict[str, dict[str, Counter[str]]],
        user_freq: dict[str, Counter[str]],
        teleport: float = 0.15,
    ) -> None:
        self.teleport = float(teleport)
        self.transitions = {
            user: {cell: Counter(row) for cell, row in row_map.items()}
            for user, row_map in transitions.items()
        }
        self.user_freq = {user: Counter(freq) for user, freq in user_freq.items()}
        self.global_freq: Counter[str] = Counter()
        for freq in self.user_freq.values():
            self.global_freq.update(freq)

    @classmethod
    def fit(cls, trips: pd.DataFrame, teleport: float = 0.15) -> RandomWalkPredictor:
        """Per-user transition counts and destination marginals from trips."""
        trips = trips.sort_values(["user", "depart"])
        transitions: dict[str, dict[str, Counter[str]]] = defaultdict(dict)
        user_freq: dict[str, Counter[str]] = defaultdict(Counter)
        for user, o, d in zip(trips["user"], trips["o_h3_r8"], trips["d_h3_r8"], strict=True):
            if pd.isna(o) or pd.isna(d):
                continue
            row = transitions[user].setdefault(o, Counter())
            row[d] += 1
            user_freq[user][d] += 1
        return cls(dict(transitions), dict(user_freq), teleport)

    def _marginal(self, user: str) -> Counter[str]:
        return self.user_freq.get(user) or self.global_freq

    def predict_proba(self, user: str, current_cell: str) -> dict[str, float]:
        """Next-cell probability distribution; {} when nothing is known."""
        probs: dict[str, float] = {}
        row = self.transitions.get(user, {}).get(current_cell)
        if row:
            total = sum(row.values())
            for cell, cnt in row.items():
                probs[cell] = probs.get(cell, 0.0) + (1.0 - self.teleport) * cnt / total
        freq = self._marginal(user)
        total = sum(freq.values())
        if total:
            for cell, cnt in freq.items():
                probs[cell] = probs.get(cell, 0.0) + self.teleport * cnt / total
        norm = sum(probs.values())
        if not norm:
            return {}
        return {cell: p / norm for cell, p in probs.items()}

    def predict(
        self, user: str, current_cell: str, exclude: Iterable[str] | None = None
    ) -> str | None:
        """Most likely next cell (None when nothing is known).

        Ties broken deterministically by probability desc, then cell id asc.
        """
        proba = self.predict_proba(user, current_cell)
        if exclude:
            filtered = {c: p for c, p in proba.items() if c not in exclude}
            if filtered:
                proba = filtered
        if not proba:
            return None
        return min(proba, key=lambda c: (-proba[c], c))


def _score_pairs(
    pred: RandomWalkPredictor,
    user: str,
    pairs: list[tuple[str, str]],
    cell_set: set[str] | None,
) -> tuple[int, float, float, float]:
    """(n_eval, top1_acc, top3_acc, mean centroid distance error km) for (cur, tgt) pairs."""
    import h3

    n_eval = top1 = top3 = 0
    dists: list[float] = []
    for cur, tgt in pairs:
        proba = pred.predict_proba(user, cur)
        if cell_set is not None:
            proba = {c: p for c, p in proba.items() if c in cell_set}
        if not proba:
            continue
        ranked = sorted(proba, key=lambda c: (-proba[c], c))
        n_eval += 1
        top1 += ranked[0] == tgt
        top3 += tgt in ranked[:3]
        p_lat, p_lon = h3.cell_to_latlng(ranked[0])
        t_lat, t_lon = h3.cell_to_latlng(tgt)
        dists.append(_haversine_km(p_lat, p_lon, t_lat, t_lon))
    top1_acc = top1 / n_eval if n_eval else np.nan
    top3_acc = top3 / n_eval if n_eval else np.nan
    dist_err = float(np.mean(dists)) if dists else np.nan
    return n_eval, top1_acc, top3_acc, dist_err


def evaluate_random_walk(
    trips: pd.DataFrame,
    seq_hourly: pd.DataFrame,
    cells: Iterable[str] | None = None,
    test_frac: float = 0.2,
) -> pd.DataFrame:
    """Next-r8-cell evaluation of RandomWalkPredictor, mirroring the baselines.

    Per user (users present in `trips` only): fit on the first (1 - test_frac)
    chronological trips, then score
      - rw_trip_dest: predict trip destination cell from origin cell;
      - rw_hourly_seq: on the held-out tail of the hourly sequence, predict the
        next known cell (UNKNOWN rows dropped) from the previous known cell.
    Metrics: top-1/top-3 accuracy and mean centroid distance error (km).
    `cells` optionally restricts the candidate set. One row per (user, method).
    """
    if trips.empty or seq_hourly.empty:
        return pd.DataFrame(columns=RW_COLUMNS)
    cell_set = None if cells is None else set(cells)
    # Single groupby pass per frame; both iterate users in ascending order, so a
    # merge-join aligns them without materializing per-user copies of seq_hourly.
    seq_iter = iter(seq_hourly.groupby("user", sort=True))
    seq_user, s_u = next(seq_iter, (None, None))
    rows: list[dict] = []
    for user, t_u in trips.groupby("user", sort=True):
        while seq_user is not None and seq_user < user:
            seq_user, s_u = next(seq_iter, (None, None))
        t_u = t_u.sort_values("depart").reset_index(drop=True)
        k_train = _temporal_split(len(t_u), test_frac)
        pred = RandomWalkPredictor.fit(t_u.iloc[:k_train])

        test_t = t_u.dropna(subset=["o_h3_r8", "d_h3_r8"]).iloc[k_train:]
        pairs = list(zip(test_t["o_h3_r8"], test_t["d_h3_r8"], strict=True))
        n_eval, top1, top3, dist_err = _score_pairs(pred, user, pairs, cell_set)
        if n_eval:
            rows.append(
                {
                    "user": user,
                    "method": "rw_trip_dest",
                    "n_eval": n_eval,
                    "top1_acc": top1,
                    "top3_acc": top3,
                    "dist_err_km": dist_err,
                }
            )

        seq: list[str] = []
        if seq_user == user:
            known = s_u.sort_values("hour")
            known = known[(known["cell_idx"] != config.UNKNOWN) & known["h3"].notna()]
            seq = known["h3"].astype(str).tolist()
        if len(seq) >= 2:
            k_seq = _temporal_split(len(seq), test_frac)
            pairs = list(zip(seq[k_seq - 1 : -1], seq[k_seq:], strict=True))
            n_eval, top1, top3, dist_err = _score_pairs(pred, user, pairs, cell_set)
            if n_eval:
                rows.append(
                    {
                        "user": user,
                        "method": "rw_hourly_seq",
                        "n_eval": n_eval,
                        "top1_acc": top1,
                        "top3_acc": top3,
                        "dist_err_km": dist_err,
                    }
                )
    out = pd.DataFrame(rows, columns=RW_COLUMNS)
    return out.sort_values(["user", "method"]).reset_index(drop=True)


def run_graphs(processed_dir: Path | None = None) -> None:
    """Build graphs + analytics + random-walk evaluation from processed parquets."""
    pdir = processed_dir or config.PROCESSED
    stops = pd.read_parquet(pdir / "stops.parquet")
    trips = pd.read_parquet(pdir / "trips.parquet")
    cohort_path = pdir / "cohort.parquet"
    cohort = None
    if cohort_path.exists():
        cohort = pd.read_parquet(cohort_path)["user"]
        stops = stops[stops["user"].isin(cohort)]
        trips = trips[trips["user"].isin(cohort)]

    out_dir = pdir / "graphs"
    graphs = build_all_graphs(stops, trips, out_dir=out_dir)
    g_global = build_global_graph(trips)
    nx.write_graphml(g_global, out_dir / "global.graphml")

    rows = [{"user": user, **graph_analytics(g)} for user, g in graphs.items()]
    rows.append({"user": "__global__", **graph_analytics(g_global)})
    pd.DataFrame(rows).to_parquet(pdir / "graph_analytics.parquet", index=False)

    seq_path = pdir / "seq_hourly.parquet"
    if seq_path.exists():
        seq_hourly = pd.read_parquet(seq_path)
        if cohort is not None:
            seq_hourly = seq_hourly[seq_hourly["user"].isin(cohort)]
        cells = sorted(set(trips["o_h3_r8"].dropna()) | set(trips["d_h3_r8"].dropna()))
        rw = evaluate_random_walk(trips, seq_hourly, cells=cells)
    else:
        print(f"{seq_path.name} not found; skipping random-walk evaluation")
        rw = pd.DataFrame(columns=RW_COLUMNS)
    rw.to_parquet(pdir / "rw_results.parquet", index=False)

    total_nodes = sum(g.number_of_nodes() for g in graphs.values())
    total_edges = sum(g.number_of_edges() for g in graphs.values())
    print(
        f"users: {len(graphs)} nodes: {total_nodes:,} edges: {total_edges:,} "
        f"global: {g_global.number_of_nodes()}n/{g_global.number_of_edges()}e -> {out_dir}"
    )
    if not rw.empty:
        print(rw.groupby("method")[["top1_acc", "top3_acc", "dist_err_km"]].mean().round(3))


if __name__ == "__main__":
    run_graphs()
