<script>
  import { loadDemoData } from "./lib/data.js";
  import Hero from "./scenes/Hero.svelte";
  import DataGallery from "./scenes/DataGallery.svelte";
  import Funnel from "./scenes/Funnel.svelte";
  import HexMap from "./scenes/HexMap.svelte";
  import BucketClock from "./scenes/BucketClock.svelte";
  import Discretize from "./scenes/Discretize.svelte";
  import GzipWalk from "./scenes/GzipWalk.svelte";
  import GuessGame from "./scenes/GuessGame.svelte";
  import PatternBars from "./scenes/PatternBars.svelte";
  import TriggerDial from "./scenes/TriggerDial.svelte";
  import Punchline from "./scenes/Punchline.svelte";


  const SECTIONS = [
    ["hero", "Intro"],
    ["data", "Data"],
    ["funnel", "Noise → places"],
    ["hex", "Hexagons"],
    ["buckets", "Time slots"],
    ["discretize", "Continuous → discrete"],
    ["lz", "The gzip trick"],
    ["entropy", "Guessing game"],
    ["patterns", "Results"],
    ["trigger", "Triggers"],
    ["punchline", "Punchline"],
  ];

  let d = $state(null);
  let error = $state(null);
  loadDemoData().then((data) => (d = data)).catch((e) => (error = e));

  let active = $state(0);
  let observer = null;
  $effect(() => {
    if (!d) return; // sections only exist once data has loaded
    observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            const idx = SECTIONS.findIndex(([id]) => id === e.target.id);
            if (idx >= 0) active = idx;
          }
        }
      },
      { rootMargin: "-40% 0px -50% 0px" },
    );
    for (const [id] of SECTIONS) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  });
</script>

{#if error}
  <div class="wrap err">
    <p>Could not load <code>demo/public/data.json</code> — build it first:</p>
    <pre>uv run python scripts/build_demo.py</pre>
  </div>
{:else if !d}
  <div class="wrap loading">loading the story…</div>
{:else}
  <nav class="dots">
    {#each SECTIONS as [id, label], i (id)}
      <a
        href="#{id}"
        class:active={active === i}
        title={label}
        aria-label={label}
      ></a>
    {/each}
  </nav>

  <Hero {d} />
  <DataGallery {d} />
  <Funnel {d} />
  <HexMap {d} />
  <BucketClock {d} />
  <Discretize {d} />
  <GzipWalk {d} />
  <GuessGame {d} />
  <PatternBars {d} />
  <TriggerDial {d} />
  <Punchline {d} />

  <footer>
    <div class="wrap">
      <p>
        Built from <b>{(d.hero.records / 1e6).toFixed(0)}M raw records</b> of
        GeoLife, YJMob100K, Foursquare (NYC/Tokyo), Gowalla and Brightkite.
        Every number on this page is computed by <code>scripts/build_demo.py</code>
        from the processed parquets — nothing hand-typed. The research dashboard
        with full model comparisons lives in <code>dashboard/</code>.
      </p>
      <p class="fine">
        Prediction: next-place forecasting under the limits measured by Song et
        al. (2010). H3 grid © Uber.
      </p>
    </div>
  </footer>
{/if}

<style>
  .loading, .err {
    padding: 20vh 24px; color: var(--muted); text-align: center;
  }
  .dots {
    position: fixed; right: 16px; top: 50%; transform: translateY(-50%);
    display: grid; gap: 10px; z-index: 50;
  }
  .dots a {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--line); display: block; transition: all 0.25s;
  }
  .dots a.active { background: var(--accent); transform: scale(1.35); }
  .dots a:hover { background: var(--muted); }
  footer {
    border-top: 1px solid var(--line); padding: 40px 0 60px;
    color: var(--muted); font-size: 14px; background: var(--bg-2);
  }
  footer .fine { color: var(--faint); font-size: 12px; }
  code {
    background: var(--panel-2); border: 1px solid var(--line);
    border-radius: 5px; padding: 1px 6px; font-size: 0.85em;
  }
  @media (max-width: 720px) { .dots { display: none; } }
</style>
