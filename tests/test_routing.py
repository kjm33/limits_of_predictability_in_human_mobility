"""Tests for mobility.routing (all HTTP mocked; no real network, no repo cache)."""

from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from mobility import routing
from mobility.routing import (
    OsrmClient,
    decode_polyline,
    fallback_straight_line,
    make_route_map,
)

PUBLIC_BASE = "http://router.project-osrm.org"
ORIGIN = (39.9042, 116.4074)  # Beijing city center
DEST = (39.9950, 116.4800)

GEOJSON_OK = {
    "code": "Ok",
    "routes": [
        {
            "distance": 1234.5,
            "duration": 300.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [[116.4074, 39.9042], [116.44, 39.95], [116.48, 39.995]],
            },
        }
    ],
}

# documented Google example, 1e5 precision
ENCODED = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
ENCODED_COORDS = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


@pytest.fixture(autouse=True)
def _fast_no_network_state(monkeypatch):
    """Reset throttle clock and make any accidental throttle sleep a no-op."""
    monkeypatch.setattr(routing, "_LAST_REQUEST_AT", 0.0)
    monkeypatch.setattr(routing, "sleep", lambda s: None)


def _mock_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


def test_decode_polyline_documented_example():
    assert decode_polyline(ENCODED) == pytest.approx(ENCODED_COORDS)


def test_route_geojson_success_and_request_shape(tmp_path):
    with patch("mobility.routing.requests.get", return_value=_mock_response(GEOJSON_OK)) as get:
        client = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path)
        result = client.route(*ORIGIN, *DEST)

    assert result == {
        "distance_m": 1234.5,
        "duration_s": 300.0,
        "geometry": [(39.9042, 116.4074), (39.95, 116.44), (39.995, 116.48)],
    }
    url = get.call_args.args[0]
    assert url == f"{PUBLIC_BASE}/route/v1/driving/116.4074,39.9042;116.48,39.995"
    assert get.call_args.kwargs["params"] == {"overview": "full", "geometries": "geojson"}
    assert get.call_args.kwargs["headers"]["User-Agent"] == "mobility-study/0.1"
    assert get.call_args.kwargs["timeout"] == client.timeout


def test_route_polyline_geometry_fallback(tmp_path):
    payload = {
        "code": "Ok",
        "routes": [{"distance": 100.0, "duration": 10.0, "geometry": ENCODED}],
    }
    with patch("mobility.routing.requests.get", return_value=_mock_response(payload)):
        client = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path)
        result = client.route(*ORIGIN, *DEST, geometries="polyline")
    assert result is not None
    assert result["geometry"] == pytest.approx(ENCODED_COORDS)
    assert result["distance_m"] == 100.0


def test_route_no_route_code_returns_none(tmp_path):
    payload = {"code": "NoRoute", "message": "No route found"}
    with patch("mobility.routing.requests.get", return_value=_mock_response(payload)):
        client = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path)
        assert client.route(*ORIGIN, *DEST) is None


def test_route_network_exception_returns_none(tmp_path):
    with patch(
        "mobility.routing.requests.get",
        side_effect=requests_lib.ConnectionError("boom"),
    ):
        client = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path)
        assert client.route(*ORIGIN, *DEST) is None


def test_route_second_call_served_from_disk_cache(tmp_path):
    with patch("mobility.routing.requests.get", return_value=_mock_response(GEOJSON_OK)) as get:
        first = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path).route(*ORIGIN, *DEST)
        # new client instance over the same cache_dir: must hit the disk, not HTTP
        second = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path).route(*ORIGIN, *DEST)
    get.assert_called_once()
    assert second == first


def test_throttle_respected_for_public_not_local(tmp_path, monkeypatch):
    clock = {"t": 0.0}
    sleeps = []

    def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += s

    monkeypatch.setattr(routing, "sleep", fake_sleep)
    monkeypatch.setattr(routing, "monotonic", lambda: clock["t"])
    payload = {"code": "Ok", "routes": [{"distance": 1.0, "duration": 1.0, "geometry": []}]}
    with patch("mobility.routing.requests.get", return_value=_mock_response(payload)):
        public = OsrmClient(base_url=PUBLIC_BASE, cache_dir=tmp_path)
        public.route(*ORIGIN, *DEST)
        public.route(ORIGIN[0] + 0.001, ORIGIN[1], *DEST)  # distinct origin -> 2nd HTTP call
        local = OsrmClient(base_url="http://localhost:5000", cache_dir=tmp_path / "local")
        local.route(*ORIGIN, *DEST)  # HTTP call, but local base -> no throttle
        local.route(*ORIGIN, *DEST)  # cache hit anyway
    assert len(sleeps) == 2  # only the two public calls throttled
    assert all(s == pytest.approx(1.0, abs=1e-6) for s in sleeps)


def test_is_local_available_true_and_false():
    with patch("mobility.routing.requests.get", return_value=_mock_response({"code": "Ok"})) as get:
        assert OsrmClient(base_url="http://localhost:5000").is_local_available() is True
        url = get.call_args.args[0]
        assert url == "http://localhost:5000/route/v1/driving/116.4,39.9;116.5,39.9"
        assert get.call_args.kwargs["timeout"] == 2.0
    with patch("mobility.routing.requests.get", return_value=_mock_response({"code": "NoRoute"})):
        assert OsrmClient(base_url="http://localhost:5000").is_local_available() is False
    with patch(
        "mobility.routing.requests.get",
        side_effect=requests_lib.Timeout("down"),
    ):
        assert OsrmClient(base_url="http://localhost:5000").is_local_available() is False


def test_local_classmethod_base_url():
    assert OsrmClient.local().base_url == "http://localhost:5000"


def test_fallback_straight_line_plausible():
    fb = fallback_straight_line(ORIGIN, DEST)
    assert 11000 < fb["distance_m"] < 13000  # ~0.1 deg lat + lon at Beijing latitude
    assert fb["duration_s"] == pytest.approx(fb["distance_m"] / 8.3)
    assert fb["geometry"] == [ORIGIN, DEST]


def test_make_route_map_writes_html(tmp_path):
    route = {"distance_m": 1.0, "duration_s": 1.0, "geometry": [ORIGIN, (39.95, 116.44), DEST]}
    out = tmp_path / "maps" / "route.html"
    m = make_route_map(ORIGIN, DEST, route, out, routine={"cell": "r8:abc", "p_routine": 0.83})
    assert out.exists()
    html = out.read_text()
    assert "folium" in html.lower() or "leaflet" in html.lower()
    assert "39.9042" in html and "116.4074" in html  # coordinates embedded
    assert "p_routine" in html and "0.83" in html  # routine evidence popup
    assert m is not None
