<script>
  import Section from "../components/Section.svelte";
  import { cellColor, fmtInt } from "../lib/data.js";
  import { onEnter } from "../lib/anim.js";
  import { onDestroy } from "svelte";

  let { d } = $props();
  const trio = $derived(d.lz_trio);
  const LZ = $derived(d.user022.lz);
  const PI = $derived(d.user022.pi);

  // toy-diary chips (letters in lz_trio.diary)
  const CHIP = { h: "#5eead4", w: "#f0abfc", c: "#fbbf24", g: "#a3e635" };
  const CHIP_NAME = { h: "home", w: "work", c: "café", g: "gym" };
  const trioWords = {
    "the routine": "the book is known by heart — every hour free",
    "the drum beat": "a beat: new only until you've heard the pattern",
    "the free rein": "every hour a fresh card",
  };

  // ---- the real 96-hour walk ------------------------------------------------
  const phraseOf = $derived.by(() => {
    const of = new Array(LZ.cells.length).fill(0);
    LZ.phrases.forEach((ph, p) => ph.forEach((i) => (of[i] = p)));
    return of;
  });
  const starts = $derived(new Set(LZ.phrases.map((p) => p[0])));

  let step = $state(0); // phrases revealed so far
  let timer = null;
  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }
  function start() {
    stop();
    step = 0;
    timer = setInterval(() => {
      step += 1;
      if (step >= LZ.phrases.length) stop();
    }, 450);
  }
  onDestroy(stop);

  const longest = $derived(
    Math.max(1, ...LZ.phrases.slice(0, step).map((p) => p.length)),
  );
  const doneWalk = $derived(step >= LZ.phrases.length);

  // ---- the budget tiles -----------------------------------------------------
  const qNaive = $derived(Math.log2(PI.N)); // yes/no questions per hour, no memory
  const totalNaive = $derived(LZ.n_hours * qNaive);
  const totalReal = $derived(totalNaive / PI.S_actual);
</script>

<Section
  id="lz"
  kicker="The gzip trick"
  title="A diary is a file you can compress"
  lede="Zip programs shrink files by noticing repeats and saying “same as
  before”. Run the same idea on a diary of places and what's left over — the
  parts no memory of the past could have guessed — is that person's leftover
  surprise, measured in bits. The authors of the 2010 paper used exactly this
  family of compressor to measure it; we count repeated blocks the same way.
  First on three toy lives, then on 96 real hours."
>
  <div class="grid two">
    <div class="panel toy" data-reveal>
      <h3>Three toy lives, four hours each</h3>
      {#each trio as t (t.name)}
        <div class="trow">
          <div class="chips">
            {#each t.diary as ch, i (i)}
              <span class="chip" style="background: {CHIP[ch]}" title={CHIP_NAME[ch]}></span>
            {/each}
          </div>
          <div class="tnum">
            <span class="ts">{Math.abs(t.S_actual).toFixed(2)} bits</span>
            <span class="tw">{trioWords[t.name]}</span>
          </div>
        </div>
      {/each}
      <p class="tnote">
        New information per hour, with memory: <b>0 bits</b> for the routine,
        <b>1.14</b> for the drum beat (barely more than its 1.0 without memory —
        you must learn the beat once), <b>2.0</b> for the free rein — the
        maximum, every hour genuinely new. Nobody zips an actual file here:
        “gzip” is the analogy, the block-counting is real.
      </p>
    </div>

    <div class="panel walk" data-reveal>
      <h3>96 real hours of volunteer 022, cut into blocks</h3>
      <div class="strip" use:onEnter={start}>
        {#each LZ.cells as c, i (i)}
          {@const p = phraseOf[i]}
          <span
            class="cell"
            class:cut={starts.has(i) && p < step}
            class:live={p === step - 1}
            style="background: {cellColor(c)}"
          ></span>
        {/each}
      </div>
      <div class="wstats">
        <div class="stat">
          <span class="num">{step}</span>
          <span>blocks cut<br />(of {LZ.phrases.length})</span>
        </div>
        <div class="stat">
          <span class="num">{longest}</span>
          <span>hours in the<br />longest block</span>
        </div>
        <div class="replay">
          <button class:primary={doneWalk || step === 0} onclick={start}>
            {doneWalk ? "replay the 96 hours" : step > 0 ? "restart" : "▶ play"}
          </button>
        </div>
      </div>
      <p class="wnote">
        A block starts only where <em>something never seen before</em> happens;
        inside a block, history repeats and costs nothing. His hours pile onto
        very few cells, with long runs of the same one — so 96 hours cut into
        just {LZ.phrases.length} blocks, the longest {Math.max(...LZ.phrases.map((p) => p.length))} hours.
      </p>
    </div>
  </div>

  <div class="grid tiles" data-reveal>
    <div class="panel tile">
      <div class="num">{PI.N} places</div>
      <p>his diary's vocabulary — so naming an hour costs up to
      <b>{qNaive.toFixed(1)} yes/no questions</b> if you must guess blind.</p>
    </div>
    <div class="panel tile">
      <div class="num">{PI.S_actual} bits</div>
      <p>what's left per hour once memory is free: about
      <b>one and a half questions</b> — measured on all {fmtInt(LZ.n_hours)}
      known hours, same block-counting as above.</p>
    </div>
    <div class="panel tile">
      <div class="num">{fmtInt(Math.round(totalReal))}</div>
      <p>total questions for the whole diary — down from
      {fmtInt(Math.round(totalNaive))}. A life, zipped to two-thirds.
      <b>Lower leftover = more predictable.</b></p>
    </div>
  </div>

  <p class="caption" data-reveal>
    <span class="words">Read aloud: surprise is what compression can't remove.
    The routine zips to nothing, the wanderer barely zips at all — and our
    volunteer sits near the routine end: 1.48 bits left out of a possible 6.7
    per hour. This doubles as a filter: a diary that zips well belongs to
    someone worth trying to predict; one that barely zips does not. The next
    scene turns those leftover bits into a hard ceiling — per person.</span>
  </p>
</Section>

<style>
  .two { grid-template-columns: 1fr 1.2fr; margin-top: 24px; }
  .panel h3 { margin: 0 0 14px; font-size: 17px; color: var(--ink); }
  .toy, .walk { padding: 20px; }

  .trow { display: flex; align-items: center; gap: 14px; padding: 9px 0;
          border-bottom: 1px dashed var(--line); }
  .trow:last-of-type { border-bottom: none; }
  .chips { display: flex; gap: 5px; min-width: 130px; }
  .chip { width: 24px; height: 24px; border-radius: 6px; display: inline-block; }
  .tnum { display: grid; gap: 2px; }
  .ts { font-size: 20px; font-weight: 700; color: var(--accent); }
  .tw { font-size: 12.5px; color: var(--muted); }
  .tnote { font-size: 13.5px; color: var(--muted); line-height: 1.5; margin: 12px 0 0; }
  .tnote b { color: var(--ink); }

  .strip {
    display: grid; grid-template-columns: repeat(16, 1fr); gap: 3px;
    background: var(--bg-2); border: 1px solid var(--line); border-radius: 8px;
    padding: 12px;
  }
  .cell { aspect-ratio: 1; border-radius: 4px; opacity: 0.55; }
  .cell.cut { opacity: 1; }
  .cell.live { box-shadow: 0 0 0 2px var(--ink); opacity: 1; }
  .wstats { display: flex; gap: 28px; align-items: center; margin-top: 14px; }
  .stat { display: grid; gap: 3px; }
  .stat .num { font-size: 26px; color: var(--accent); font-weight: 700; }
  .stat span:last-child { font-size: 12px; color: var(--muted); line-height: 1.35; }
  .replay { margin-left: auto; }
  .replay button {
    background: var(--panel-2); border: 1px solid var(--line); color: var(--muted);
    padding: 9px 16px; border-radius: 8px; cursor: pointer; font-size: 14px;
  }
  .replay button.primary { border-color: var(--accent); color: var(--accent); }
  .wnote { font-size: 13.5px; color: var(--muted); line-height: 1.5; margin: 12px 0 0; }
  .wnote em { color: var(--ink); font-style: normal; font-weight: 600; }

  .tiles { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); margin-top: 22px; }
  .tile { padding: 18px; }
  .tile .num { font-size: 30px; color: var(--accent-2); font-weight: 700; margin-bottom: 6px; }
  .tile p { color: var(--muted); font-size: 14px; margin: 0; line-height: 1.5; }
  .tile p b { color: var(--ink); }

  @media (max-width: 860px) { .two { grid-template-columns: 1fr; } }
</style>
