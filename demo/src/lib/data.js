// Single loader for the built data payload (demo/public/data.json).
let cache = null;

export function loadDemoData() {
  if (!cache) {
    cache = fetch(`${import.meta.env.BASE_URL}data.json`).then((r) => {
      if (!r.ok) throw new Error(`data.json ${r.status}`);
      return r.json();
    });
  }
  return cache;
}

export const fmtInt = (n) =>
  n == null ? "—" : Math.round(n).toLocaleString("en-US");

export const fmtM = (n) => {
  if (n == null) return "—";
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return `${n}`;
};

export const fmtPct = (x, digits = 1) =>
  x == null ? "—" : `${(100 * x).toFixed(digits)}%`;

export const fmtDays = (d) => {
  if (d == null) return "—";
  if (d >= 365) return `${(d / 365).toFixed(d >= 730 ? 0 : 1)} yr`;
  if (d >= 60) return `${Math.round(d / 30)} mo`;
  return `${d} d`;
};

// Deterministic distinct color per cell index (golden-angle hue walk).
export const cellColor = (i, s = 62, l = 56) =>
  `hsl(${(i * 137.508) % 360} ${s}% ${l}%)`;

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
