"""OSRM routing client, polyline decoding, and folium route maps."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlparse

import folium
import requests

from . import config

USER_AGENT = "mobility-study/0.1"
MIN_INTERVAL_S = 1.0  # public demo server: max ~1 req/s
CITY_SPEED_MS = 8.3  # ~30 km/h average used for straight-line fallback

_LAST_REQUEST_AT = 0.0
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode an encoded polyline string into [(lat, lon), ...]."""
    coords: list[tuple[float, float]] = []
    factor = 10.0**precision
    index = 0
    lat = lon = 0
    n = len(encoded)
    while index < n:
        for axis in range(2):
            result = 0
            shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return coords


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in meters between two (lat, lon) points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2.0 * 6371000.0 * math.asin(math.sqrt(h))


def fallback_straight_line(
    o: tuple[float, float], d: tuple[float, float]
) -> dict:
    """Route-shaped dict for the direct line between o and d (OSRM unavailable)."""
    dist = haversine_m(o, d)
    return {
        "distance_m": dist,
        "duration_s": dist / CITY_SPEED_MS,
        "geometry": [tuple(o), tuple(d)],
    }


def _throttle(min_interval: float) -> None:
    """Ensure at least `min_interval` seconds between outgoing requests."""
    global _LAST_REQUEST_AT
    wait = min_interval - (monotonic() - _LAST_REQUEST_AT)
    if wait > 0:
        sleep(wait)
    _LAST_REQUEST_AT = monotonic()


class OsrmClient:
    """Thin OSRM /route client with a disk cache; never raises on failure."""

    def __init__(
        self,
        base_url: str = "http://router.project-osrm.org",
        cache_dir: Path | None = None,
        timeout: float = 10.0,
        min_interval_s: float = MIN_INTERVAL_S,
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = (
            Path(cache_dir) if cache_dir else config.ROOT / "data" / "cache" / "osrm"
        )
        self.timeout = timeout
        self.min_interval_s = min_interval_s
        host = urlparse(self.base_url).hostname or ""
        self.is_local_base = host in _LOCAL_HOSTS

    @classmethod
    def local(cls) -> OsrmClient:
        """Client pointed at a local OSRM docker instance."""
        return cls(base_url="http://localhost:5000")

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    @staticmethod
    def _cache_key(
        o: tuple[float, float], d: tuple[float, float], profile: str, geometries: str
    ) -> str:
        raw = f"{o[0]},{o[1]},{d[0]},{d[1]},{profile},{geometries}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_read(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        data["geometry"] = [(la, lo) for la, lo in data["geometry"]]
        return data

    def _cache_write(self, key: str, result: dict) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(key).write_text(json.dumps(result))
        except OSError:
            pass  # cache is best-effort

    def route(
        self,
        o_lat: float,
        o_lon: float,
        d_lat: float,
        d_lon: float,
        profile: str = "driving",
        geometries: str = "geojson",
    ) -> dict | None:
        """Route between (o_lat, o_lon) and (d_lat, d_lon).

        Returns {"distance_m", "duration_s", "geometry": [(lat, lon), ...]}
        or None on any failure (bad code, network error, parse error).
        """
        o, d = (o_lat, o_lon), (d_lat, d_lon)
        key = self._cache_key(o, d, profile, geometries)
        cached = self._cache_read(key)
        if cached is not None:
            return cached

        url = f"{self.base_url}/route/v1/{profile}/{o_lon},{o_lat};{d_lon},{d_lat}"
        if not self.is_local_base:
            _throttle(self.min_interval_s)
        try:
            resp = requests.get(
                url,
                params={"overview": "full", "geometries": geometries},
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
            data = resp.json()
        except Exception:
            return None
        if not isinstance(data, dict) or data.get("code") != "Ok" or not data.get("routes"):
            return None

        first = data["routes"][0]
        coords = self._parse_geometry(first.get("geometry"), geometries)
        if coords is None:
            return None
        result = {
            "distance_m": float(first["distance"]),
            "duration_s": float(first["duration"]),
            "geometry": coords,
        }
        self._cache_write(key, result)
        return result

    @staticmethod
    def _parse_geometry(geometry, geometries: str) -> list[tuple[float, float]] | None:
        """OSRM geometry (geojson LineString or encoded polyline) -> [(lat, lon), ...]."""
        if isinstance(geometry, dict):
            try:
                return [(float(c[1]), float(c[0])) for c in geometry["coordinates"]]
            except (KeyError, TypeError, IndexError, ValueError):
                return None
        if isinstance(geometry, str):
            precision = 6 if geometries == "polyline6" else 5
            try:
                return decode_polyline(geometry, precision)
            except (IndexError, ValueError):
                return None
        return None

    def is_local_available(self) -> bool:
        """Probe {base_url} with a tiny route request (2s timeout)."""
        url = f"{self.base_url}/route/v1/driving/116.4,39.9;116.5,39.9"
        try:
            resp = requests.get(
                url,
                params={"overview": "false"},
                headers={"User-Agent": USER_AGENT},
                timeout=2.0,
            )
            return resp.json().get("code") == "Ok"
        except Exception:
            return False


def make_route_map(
    o: tuple[float, float],
    d: tuple[float, float],
    route: dict,
    out_html: Path,
    routine: dict | None = None,
) -> folium.Map:
    """Render a route as a folium map (green origin, red destination, blue polyline)."""
    geometry = list(route.get("geometry", []))
    lats = [p[0] for p in geometry] + [o[0], d[0]]
    lons = [p[1] for p in geometry] + [o[1], d[1]]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=12)
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)

    popup = None
    if routine:
        evidence = "<br>".join(f"{k}: {v}" for k, v in routine.items())
        popup = folium.Popup(evidence, max_width=300)
    folium.PolyLine(
        [(p[0], p[1]) for p in geometry],
        color="blue",
        weight=4,
        opacity=0.8,
        name="Route",
        popup=popup,
    ).add_to(m)
    folium.Marker(o, popup="Origin", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(d, popup="Destination", icon=folium.Icon(color="red")).add_to(m)
    folium.LayerControl().add_to(m)

    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    m.save(out_html)
    return m
