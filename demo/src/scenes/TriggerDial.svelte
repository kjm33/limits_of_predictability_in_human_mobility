<script>
  import Section from "../components/Section.svelte";
  import { gsap } from "../lib/anim.js";
  import { WEEKDAYS } from "../lib/data.js";

  let { d } = $props();
  const u = $derived(d.user022);

  let weekday = $state(0);
  let bucketIdx = $state(60); // 15:00 — the card fires on load
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

  $effect(() => {
    // pulse the status panel whenever the fired rule changes
    card;
    if (statusEl) gsap.fromTo(statusEl, { scale: 0.985 }, { scale: 1, duration: 0.4 });
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
  <div class="ctrl" data-reveal>
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

    <div class="status" bind:this={statusEl} class:fire={card}>
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
</Section>

<style>
  .ctrl { max-width: 880px; margin: 24px auto 0; }
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
</style>
