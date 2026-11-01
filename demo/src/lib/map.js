// Shared MapLibre factory: custom dark style, fully offline — no tile server,
// no API keys. Our own vector layers (hexes, dots, routes) are the whole map.
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

export function makeMap(container, opts = {}) {
  const map = new maplibregl.Map({
    container,
    style: darkStyle(),
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
