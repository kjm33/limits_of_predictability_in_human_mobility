// Shared MapLibre factory. Two looks:
//  - offline (default): dark background + our own vector layers only — no
//    tile server, no API keys, works with zero network.
//  - HERE underlay: raster tiles from the HERE Raster Tile API v3 when an API
//    key is available (see hereApiKey below). Streets appear under the data.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export function darkStyle() {
  return {
    version: 8,
    sources: {},
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0b0f14" } },
    ],
  };
}

// HERE Raster Tile API v3 (needs a HERE *platform* account key, not the old
// developer key). explore.night is the dark basemap style.
export function hereStyle(apiKey) {
  return {
    version: 8,
    sources: {
      here: {
        type: "raster",
        tiles: [
          "https://maps.hereapi.com/v3/base/mc/{z}/{x}/{y}/png8" +
            "?size=512&ppi=400&style=explore.night&apiKey=" +
            encodeURIComponent(apiKey),
        ],
        tileSize: 512,
        maxzoom: 20,
        attribution: "© HERE",
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0b0f14" } },
      { id: "here", type: "raster", source: "here" },
    ],
  };
}

// Resolve the HERE API key: ?here_key=... URL param wins (and is remembered in
// localStorage, then stripped from the address bar), then localStorage from an
// earlier visit, then the build-time VITE_HERE_API_KEY. Keys are never written
// into the repo. Returns null when absent → fully offline map.
export function hereApiKey() {
  try {
    const q = new URLSearchParams(location.search).get("here_key");
    if (q) {
      localStorage.setItem("here_key", q);
      history.replaceState(null, "", location.pathname);
      return q;
    }
    return localStorage.getItem("here_key") ?? import.meta.env.VITE_HERE_API_KEY ?? null;
  } catch {
    return null;
  }
}

export function makeMap(container, opts = {}) {
  const hereKey = opts.hereKey !== undefined ? opts.hereKey : hereApiKey();
  const map = new maplibregl.Map({
    container,
    style: hereKey ? hereStyle(hereKey) : darkStyle(),
    center: opts.center ?? [116.345, 39.968],
    zoom: opts.zoom ?? 11.8,
    interactive: opts.interactive !== false,
    attributionControl: { compact: true },
  });
  if (opts.nav !== false) {
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
  }
  return map;
}

// Zoom/fit helper: bounds of the *main cluster* of a hex FeatureCollection —
// drops far outliers (a vacation 900 km away should not shrink the view).
export function clusterBounds(geojson) {
  const pts = [];
  for (const f of geojson.features) {
    for (const [lng, lat] of f.geometry.coordinates[0]) pts.push([lng, lat]);
  }
  const lngs = [...pts.map((p) => p[0])].sort((a, b) => a - b);
  const lats = [...pts.map((p) => p[1])].sort((a, b) => a - b);
  const med = (arr) => arr[Math.floor(arr.length / 2)];
  const [mx, my] = [med(lngs), med(lats)];
  const near = pts.filter(([x, y]) => Math.abs(x - mx) < 1.2 && Math.abs(y - my) < 0.8);
  const xs = near.map((p) => p[0]);
  const ys = near.map((p) => p[1]);
  return [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ];
}

// Bounds of the core of the activity, anchored on a "home" point: keep stops
// within `maxKm` of the anchor (drops a vacation 900 km away — a distance cap,
// not a percentile, because a long trip can be >10% of all stops and sneak
// back into any fraction cut), then keep the closest `frac` of what remains
// (drops sporadic far corners of town). Far cells stay on the map — the user
// can still pan to them — they just don't stretch the initial view.
export function coreBounds(points, anchor, maxKm = 25, frac = 0.7) {
  if (!points.length) return null;
  const R = 6371;
  const dist = (p) => {
    const toRad = (x) => (x * Math.PI) / 180;
    const [ax, ay] = anchor;
    const dl = toRad(p[0] - ax);
    const dp = toRad(p[1] - ay);
    const a =
      Math.sin(dp / 2) ** 2 +
      Math.cos(toRad(ay)) * Math.cos(toRad(p[1])) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };
  let keep = points.filter((p) => dist(p) <= maxKm);
  if (keep.length < 20) keep = points.filter((p) => dist(p) <= 100);
  if (keep.length < 20) keep = points;
  const sorted = [...keep].sort((a, b) => dist(a) - dist(b));
  const core = sorted.slice(0, Math.max(20, Math.floor(sorted.length * frac)));
  const xs = core.map((p) => p[0]);
  const ys = core.map((p) => p[1]);
  return [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ];
}

export function addHexes(map, id, geojson, color, opacity = 0.35) {
  map.addSource(id, { type: "geojson", data: geojson });
  map.addLayer({
    id,
    type: "fill",
    source: id,
    paint: {
      "fill-color": color,
      "fill-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        Math.min(0.85, opacity + 0.35),
        opacity,
      ],
      "fill-outline-color": "rgba(94, 234, 212, 0.35)",
    },
  });
  map.addLayer({
    id: `${id}-line`,
    type: "line",
    source: id,
    paint: { "line-color": "rgba(233, 240, 247, 0.25)", "line-width": 0.6 },
  });
}

export function addDots(map, id, geojson) {
  map.addSource(id, { type: "geojson", data: geojson });
  map.addLayer({
    id,
    type: "circle",
    source: id,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2.5, 14, 6],
      "circle-color": ["get", "color"],
      "circle-stroke-color": "rgba(11,15,20,0.9)",
      "circle-stroke-width": 1,
    },
  });
}
