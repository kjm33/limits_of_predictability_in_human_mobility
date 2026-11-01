<script>
  import Section from "../components/Section.svelte";
  import { onEnter, gsap } from "../lib/anim.js";
  import { makeMap, addDots } from "../lib/map.js";
  import maplibregl from "maplibre-gl";
  import { cellColor, WEEKDAYS } from "../lib/data.js";

  let { d } = $props();
  const u = $derived(d.user022);

  let weekday = $state(0);
  let bucketIdx = $state(60); // 15:00 — the card fires on load
  let mapEl = $state(null);
  let statusEl = $state(null);

  const g15 = $derived(u.grids["15"]);
  const sel = $derived(weekday * 96 + bucketIdx);
  const timeLabel = $derived(
    `${String(Math.floor((bucketIdx * 15) / 60)).padStart(2, "0")}:${String((bucketIdx * 15) % 60).padStart(2, "0")}`,
  );

  function cardBucket(c) {
    const [hh, mm] = c.bucket_str.split("-")[0].split(":").map(Number);
    return hh * 4 + Math.floor(mm / 15);
  }
  const card = $derived(
    u.cards.find((c) => c.weekday === weekday && cardBucket(c) === bucketIdx) ?? null,
  );
  const guessCell = $derived(g15.cells[sel]);
  const guessSup = $derived(g15.support[sel]);

  let map = null; // plain object — never wrap MapLibre in $state

  $effect(() => {
    if (!mapEl) return;
    let killed = false;
    const m = makeMap(mapEl, { center: [116.345, 39.968], zoom: 12.2 });
    m.on("load", () => {
      if (killed) return;

      const placesGeo = {
        type: "FeatureCollection",
        features: u.places.map((p, i) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [p.mean_lon, p.mean_lat] },
          properties: { color: cellColor(i), label: p.label || `place ${p.place_id}` },
        })),
      };
      addDots(m, "places", placesGeo);
      m.on("click", "places", (e) => {
        const p = e.features[0].properties;
        new maplibregl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(`<b>${p.label}</b>`)
          .addTo(m);
      });

      m.addSource("focus", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      m.addLayer({
        id: "focus-hex",
        type: "fill",
        source: "focus",
        paint: { "fill-color": "#5eead4", "fill-opacity": 0.25 },
      });
      m.addLayer({
        id: "focus-line",
        type: "line",
        source: "focus",
        paint: { "line-color": "#5eead4", "line-width": 1.5 },
      });

      m.addSource("route", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      m.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#f0abfc",
          "line-width": 3,
          "line-dasharray": [0, 4, 3],
        },
      });
      m.addSource("od", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      m.addLayer({
        id: "od-dots",
        type: "circle",
        source: "od",
        paint: {
          "circle-radius": 7,
          "circle-color": ["get", "color"],
          "circle-stroke-color": "#0b0f14",
          "circle-stroke-width": 2,
        },
      });
      map = m;
      render();
    });
    return () => {
      killed = true;
      m.remove();
      map = null;
    };
  });

  function render() {
    if (!map || !map.getLayer("focus-hex")) return;
    if (card) {
      const feats = [];
      const oFeat = {
        type: "Feature",
        geometry: { type: "Point", coordinates: [card.o_lon, card.o_lat] },
        properties: { color: "#5eead4" },
      };
      const dFeat = {
        type: "Feature",
        geometry: { type: "Point", coordinates: [card.d_lon, card.d_lat] },
        properties: { color: "#f0abfc" },
      };
      map.getSource("route").setData({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: [[card.o_lon, card.o_lat], [card.d_lon, card.d_lat]],
        },
        properties: {},
      });
      map.getSource("od").setData({
        type: "FeatureCollection",
        features: [oFeat, dFeat],
      });
      map.getSource("focus").setData({ type: "FeatureCollection", features: [] });
      map.fitBounds(
        [
          [Math.min(card.o_lon, card.d_lon), Math.min(card.o_lat, card.d_lat)],
          [Math.max(card.o_lon, card.d_lon), Math.max(card.o_lat, card.d_lat)],
        ],
        { padding: 120, duration: 600, maxZoom: 13.5 },
      );
      if (statusEl) {
        gsap.fromTo(statusEl, { scale: 0.97 }, { scale: 1, duration: 0.4 });
      }
    } else {
      map.getSource("route").setData({ type: "FeatureCollection", features: [] });
      map.getSource("od").setData({ type: "FeatureCollection", features: [] });
      map.getSource("focus").setData({
        type: "FeatureCollection",
        features:
          guessCell !== -1 && guessCell != null ? [u.hexes.r8.features[guessCell]] : [],
      });
    }
  }

  $effect(() => {
    // re-render whenever the selection changes (card/sel/guess read here)
    card, sel, guessCell;
    render();
  });
</script>

<Section
  id="trigger"
  kicker="The payoff"
  title="Rules that fire on Monday at 15:00"
  lede="Every routine card is a tiny prediction rule: IF weekday and IF you are
  seen leaving place X inside this quarter-hour, THEN you are going to Y. Pick a
  weekday and time — watch what fires for our Beijing volunteer."
>
  <div class="grid two">
    <div class="ctrlcol" data-reveal>
      <div class="days">
        {#each WEEKDAYS as wd, i (wd)}
          <button class:active={weekday === i} onclick={() => (weekday = i)}>{wd}</button>
        {/each}
      </div>
      <div class="sliderrow">
        <input
          type="range" min="0" max="95" bind:value={bucketIdx} step="1"
          aria-label="time of day"
        />
        <span class="tlab num">{timeLabel}</span>
      </div>

      <div class="status" bind:this={statusEl} class:fire={card} data-reveal>
        {#if card}
          <div class="shead">⚡ rule fires</div>
          <p class="sbody">
            <b>{WEEKDAYS[card.weekday]} {card.bucket_str}</b> — leaving
            <b>{card.o_label || "home"}</b>, this person went to the same
            destination <b>{card.n_trips} times</b> across <b>{card.support} different weeks</b>
            (confidence {Math.round(card.confidence * 100)}%).
          </p>
          <p class="sverdict">
            Prediction: <b>going to {card.d_label || "the same place again"}</b> —
            and in GeoLife overall such fired predictions were right
            <b>9 times out of 10</b>.
          </p>
        {:else if guessCell !== -1 && guessCell != null}
          <div class="shead soft">no hard rule — soft guess instead</div>
          <p class="sbody">
            Nothing repeats here strongly enough to become a card. The weekly
            grid's fallback: usually at <b>{u.cells[guessCell].label ?? `cell ${guessCell}`}</b>
            in this slot, seen in <b>{guessSup} different weeks</b>.
          </p>
        {:else}
          <div class="shead soft">silence</div>
          <p class="sbody">
            No rule, no recurring cell — on the move, or the logger was off.
            55% of analyzable GeoLife people never produce a single card; gaps are normal.
          </p>
        {/if}
      </div>

      <p class="note" data-reveal>
        The rule fires only when the person is actually seen leaving the origin
        in that window — a trigger, not a horoscope. Across GeoLife the trigger
        fired 190 times in the held-out test period and was right 170 times.
      </p>
    </div>

    <div class="mapcol" data-reveal>
      <div class="map" bind:this={mapEl}></div>
    </div>
  </div>
</Section>

<style>
  .two {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
    margin-top: 24px; align-items: start;
  }
  .days { display: flex; gap: 6px; flex-wrap: wrap; }
  .days button { padding: 7px 0; flex: 1; min-width: 52px; text-align: center; }
  .sliderrow { display: flex; align-items: center; gap: 14px; margin: 18px 0; }
  .sliderrow input { flex: 1; }
  .tlab { font-size: 26px; color: var(--accent); min-width: 3.6ch; text-align: right; }
  .status {
    background: var(--panel); border: 1px solid var(--line);
    border-radius: 14px; padding: 18px 20px; min-height: 150px;
  }
  .status.fire {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 7%, var(--panel));
  }
  .shead {
    font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase;
    font-size: 13px; color: var(--accent); margin-bottom: 8px;
  }
  .shead.soft { color: var(--warn); }
  .sbody { color: var(--muted); }
  .sbody b { color: var(--ink); }
  .sverdict { color: var(--accent); font-size: 15px; }
  .map {
    height: 64vh; min-height: 440px;
    border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
  }
  @media (max-width: 880px) {
    .two { grid-template-columns: 1fr; }
    .map { height: 50vh; min-height: 360px; }
  }
</style>
