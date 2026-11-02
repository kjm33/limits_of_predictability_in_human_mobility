<script>
  import Section from "../components/Section.svelte";

  let { d } = $props();

  const M = $derived(d.user022.markov);
  const ROWLAB = ["at favourite place", "at 2nd place", "at 3rd place", "at 4th place", "everywhere else"];
  const COLLAB = ["→ favourite", "→ 2nd", "→ 3rd", "→ 4th", "→ elsewhere"];

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

  {#if M && M.rows}
    <div class="panel mkpanel" data-reveal>
      <div class="mkgrid">
        <div class="mkrow mkhead">
          <span></span>
          {#each COLLAB as c (c)}<span class="mkcol">{c}</span>{/each}
        </div>
        {#each M.rows as row, i (ROWLAB[i])}
          <div class="mkrow">
            <span class="mkrowlab">{ROWLAB[i]}</span>
            {#each row as p, j (j)}
              <div
                class="mkcell"
                class:diag={i === j}
                style="background: rgba(94, 234, 212, {(p * 0.88).toFixed(3)})"
              >
                {#if p >= 0.05}{Math.round(p * 100)}%{/if}
              </div>
            {/each}
          </div>
        {/each}
      </div>
      <div class="mktext">
        <h3>The honest check: “where → next” for volunteer 022</h3>
        <p>
          Each row asks: <em>he's at this place now — where is he next hour?</em>
          Dark teal = likely. From his favourite place he stays put
          {Math.round(M.rows[0][0] * 100)}% of hours; almost everything else is
          “elsewhere”, because 100 other places share the leftovers.
        </p>
        <p>
          Counted this way, the simple table scores
          <b>{Math.round(M.acc * 100)}%</b> — <em>higher</em> than his
          {Math.round(d.user022.pi.Pi_actual * 100)}% ceiling. No contradiction:
          the table only answers the <b>{Math.round((M.n_eval / M.n_pairs) * 100)}%
          of hour-to-hour jumps</b> that start at a favourite place he'd been
          seen at before ({M.n_eval} of {M.n_pairs} testable pairs); the ceiling
          prices <em>every</em> hour, gaps and one-offs included. Condition on
          the easy hours and any method looks brilliant — that conditioning, not
          magic, is what “where were you just now” methods exploit.
        </p>
      </div>
    </div>
  {/if}

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
      and that gap is measurable, not mysterious. Enough to act on — the last
      scene shows what an agent does with it.</p>
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
  .mkpanel {
    margin: 26px 0 6px; padding: 22px;
    display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 26px;
  }
  .mkgrid { display: grid; gap: 4px; align-content: start; }
  .mkrow { display: grid; grid-template-columns: 128px repeat(5, 1fr); gap: 4px; }
  .mkrowlab { font-size: 12px; color: var(--muted); align-self: center; text-align: right;
              padding-right: 6px; }
  .mkcol { font-size: 10.5px; color: var(--faint); text-align: center; align-self: end; }
  .mkhead { margin-bottom: 2px; }
  .mkcell {
    aspect-ratio: 1.55; border-radius: 5px; display: grid; place-items: center;
    font-size: 12px; font-weight: 700; color: var(--bg); border: 1px solid var(--line);
  }
  .mkcell.diag { outline: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
                 outline-offset: -4px; }
  .mktext h3 { margin: 0 0 10px; font-size: 17px; color: var(--ink); }
  .mktext p { color: var(--muted); font-size: 13.5px; line-height: 1.6; margin: 0 0 10px; }
  .mktext p:last-child { margin-bottom: 0; }
  .mktext em { color: var(--ink); font-style: normal; font-weight: 600; }
  .mktext b { color: var(--accent); }
  .threes { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); margin-top: 28px; }
  .panel h3 { font-size: 17px; color: var(--accent); }
  .panel p { color: var(--muted); font-size: 14px; margin: 0; }
  @media (max-width: 820px) {
    .brow { grid-template-columns: 1fr 64px; }
    .bname { text-align: left; grid-column: 1; }
    .btrack { grid-column: 1; }
    .bmodel { grid-column: 1 / -1; }
    .mkpanel { grid-template-columns: 1fr; }
    .mkrow { grid-template-columns: 92px repeat(5, 1fr); }
    .mkrowlab { font-size: 10px; }
  }
</style>
