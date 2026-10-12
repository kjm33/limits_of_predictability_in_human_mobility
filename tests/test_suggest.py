from datetime import datetime

import pandas as pd

from mobility.suggest import _origin, parse_now


def test_parse_now_weekday_time():
    ref = datetime(2026, 10, 12)  # Monday
    ts = parse_now("Thu 15:15", ref=ref)
    assert ts.weekday() == 3
    assert ts.hour == 15 and ts.minute == 15
    assert ts > pd.Timestamp(ref)  # next Thursday, not past


def test_parse_now_iso():
    ts = parse_now("2026-10-15 15:15")
    assert ts == pd.Timestamp("2026-10-15 15:15:00")


def test_origin_home_and_coords():
    places = pd.DataFrame(
        [
            {
                "user": "u1", "place_id": 0, "n_visits": 5, "label": "home",
                "mean_lat": 39.9, "mean_lon": 116.3,
            },
            {
                "user": "u1", "place_id": 1, "n_visits": 9, "label": "work",
                "mean_lat": 40.0, "mean_lon": 116.4,
            },
        ]
    )
    assert _origin(places, "u1", None) == (39.9, 116.3)
    assert _origin(places, "u1", "work") == (40.0, 116.4)
    assert _origin(places, "u1", "39.95,116.35") == (39.95, 116.35)
    assert _origin(places, "u2", None) is None


def test_suggest_cli_end_to_end(tmp_path, monkeypatch):
    """Full main() run on a synthetic world: cards printed, route map mocked."""
    import sys

    sys.path.insert(0, "tests")
    from mobility import suggest as sug
    from mobility.routines import cluster_places, mine_routines
    from test_routines import _synthetic_world

    stops, trips = _synthetic_world()
    stops_p, places = cluster_places(stops)
    cards = mine_routines(stops_p, places, trips, min_support_weeks=4)

    proc = tmp_path / "proc"
    proc.mkdir()
    cards.to_parquet(proc / "routines.parquet", index=False)
    places.to_parquet(proc / "places_summary.parquet", index=False)
    monkeypatch.setattr(sug.config, "PROCESSED", proc)

    # fake route: straight line, no network
    class FakeClient:
        @classmethod
        def local(cls):
            return cls()

        def is_local_available(self):
            return False

        def route(self, o_lat, o_lon, d_lat, d_lon, profile="driving"):
            return None

    monkeypatch.setattr(sug, "OsrmClient", FakeClient)
    out = tmp_path / "map.html"
    monkeypatch.setattr(sug.config, "REPORTS", tmp_path)

    rc = sug.main(["--user", "u1", "--now", "2023-03-09 15:14", "--route", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    # Thursday 15:16 A->B card should be suggested (15:14 + lookahead 1 covers 15:15 bucket)
    text = out.read_text()
    assert "routine" in text and "score" in text
    # wrong weekday -> no triggers, rc 0
    assert sug.main(["--user", "u1", "--now", "2023-03-08 15:14"]) == 0
    # unknown user -> rc 1
    assert sug.main(["--user", "nobody", "--now", "2023-03-09 15:14"]) == 1
