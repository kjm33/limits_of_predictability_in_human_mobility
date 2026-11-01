<script>
  import Section from "../components/Section.svelte";

  let { d } = $props();

  const rows = $derived(
    d.datasets
      .map((r) => ({
        key: r.key,
        label: r.key.startsWith("yjmob") ? (r.key === "yjmob1" ? "YJMob 100K" : "YJMob 25K") : r.label,
        pi: r.pi_mean,
        model: r.best_model,
        top1: r.best_top1,
        markov: String(r.best_model).startsWith("markov"),
      }))
      .sort((a, b) => b.pi - a.pi),
  );

  const MODEL_NAMES = {
    markov1: "Markov-1 (where → next)",
    markov2_col: "Markov-2, collective",
    markov1_col: "Markov-1, collective",
    freq: "frequency (most visited)",
    time: "time-of-week",
  };
  const modelName = (m) => MODEL_NAMES[m] ?? m;
</script>

<Section
  id="punchline"
  kicker="The honest punchline"
  title="Predictability tracks how you were watched"
  lede="“How predictable is a person?” has no single number. The ceiling — the
  best accuracy any algorithm could ever reach — and even which simple method
  wins both flip with the sensing regime."
>
  <div class="bars">
    {#each rows as r (r.key)}
      <div class="brow" data-reveal>
        <span class="bname">{r.label}</span>
        <div class="btrack">
          <div
            class="bfill"
            class:mk="{r.markov}"
            style="width: {r.pi * 100}%"
          ></div>
        </div>
        <span class="bpi num">{Math.round(r.pi * 100)}%</span>
        <span class="bmodel">{modelName(r.model)}</span>
      </div>
    {/each}
  </div>

  <div class="legend" data-reveal>
    <span class="dot mk"></span> ceiling + “where were you just now” methods win
    (dense logging)&nbsp;&nbsp;
    <span class="dot tw"></span> ceiling + “what time of week is it” methods win
    (sparse check-ins)
  </div>

  <p class="caption" data-reveal>
    <span class="words">Brightkite check-ins cap at ~68% predictability while
    Gowalla's sparser diary caps at 43% — same kind of app, same era, half the
    ceiling. GeoLife's dense GPS sits at 55% and rewards memory of your last
    move; Tokyo check-ins sit at 59% and reward knowing the weekly clock. The
    “enigma” that appears when you add datasets isn't noise in the science — it
    is the finding.</span>
  </p>

  <div class="grid threes" data-reveal>
    <div class="panel">
      <h3>What we built</h3>
      <p>A pipeline that turns raw location noise into weekday × quarter-hour
      rules — stays, places, hexagons, weekly grids — plus the betting-game
      bounds on how far any method could ever get.</p>
    </div>
    <div class="panel">
      <h3>What surprised us</h3>
      <p>No neural network beat the counting methods. With diary-sized data,
      “remember where this person usually is at this hour” is close to the
      theoretical ceiling already.</p>
    </div>
    <div class="panel">
      <h3>What it means</h3>
      <p>Regularity is common but not universal: about half of well-watched
      people have machine-detectable weekly rhythms, and when the rules fire,
      they are right ~9 times in 10. The rest of us are genuinely harder —
      and that gap is measurable, not mysterious.</p>
    </div>
  </div>
</Section>

<style>
  .bars { display: grid; gap: 12px; margin: 26px 0 12px; }
  .brow {
    display: grid;
    grid-template-columns: 130px minmax(0, 1fr) 64px 230px;
    gap: 12px; align-items: center;
  }
  .bname { font-weight: 600; font-size: 15px; text-align: right; }
  .btrack {
    height: 22px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 6px; overflow: hidden;
  }
  .bfill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-2), color-mix(in srgb, var(--accent-2) 55%, var(--warn)));
  }
  .bfill.mk {
    background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, #7dd3fc));
  }
  .bpi { font-size: 20px; color: var(--ink); }
  .bmodel { font-size: 12px; color: var(--faint); }
  .legend { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
  .legend .dot {
    display: inline-block; width: 11px; height: 11px; border-radius: 3px;
    vertical-align: -1px;
  }
  .dot.mk { background: var(--accent); }
  .dot.tw { background: var(--accent-2); }
  .threes { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); margin-top: 28px; }
  .panel h3 { font-size: 17px; color: var(--accent); }
  .panel p { color: var(--muted); font-size: 14px; margin: 0; }
  @media (max-width: 820px) {
    .brow { grid-template-columns: 1fr 64px; }
    .bname { text-align: left; grid-column: 1; }
    .btrack { grid-column: 1; }
    .bmodel { grid-column: 1 / -1; }
  }
</style>
