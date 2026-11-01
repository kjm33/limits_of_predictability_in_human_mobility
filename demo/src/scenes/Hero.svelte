<script>
  import Count from "../components/Count.svelte";
  import { fmtPct } from "../lib/data.js";

  let { d } = $props();
  const h = $derived(d.hero);
</script>

<section class="scene hero" id="hero">
  <div class="wrap">
    <p class="kicker" data-reveal>A visual story · human mobility</p>
    <h1 data-reveal>How regular<br />are we?</h1>
    <p class="lede" data-reveal>
      We collected <strong>{(h.records / 1e6).toFixed(0)} million</strong> location
      records from <strong>{h.people.toLocaleString("en-US")}</strong> people across
      six datasets — then taught a computer to learn their weekly routines.
      This page walks through every step: raw noise → places → hexagons →
      time slots → the rules that fire on “Monday, 15:00”.
    </p>

    <div class="grid stats" data-reveal>
      <div class="panel stat">
        <div class="big"><Count value={h.people} /></div>
        <div>people</div>
      </div>
      <div class="panel stat">
        <div class="big"><Count value={h.records / 1e6} digits={0} suffix="M" /></div>
        <div>location records</div>
      </div>
      <div class="panel stat">
        <div class="big"><Count value={h.share_geolife * 100} digits={0} suffix="%" /></div>
        <div>of analyzable GPS users<br />have weekly routines</div>
      </div>
      <div class="panel stat">
        <div class="big"><Count value={h.trigger_precision_geolife * 100} digits={0} suffix="%" /></div>
        <div>of fired rules were right</div>
      </div>
    </div>

    <p class="caption" data-reveal>
      <span class="words">In words: about one in two GPS-logged people has a
      schedule regular enough to detect automatically — and when the system says
      “this person will do X now”, it is right roughly 9 times out of 10.</span>
    </p>

    <div class="scrollhint" data-reveal>scroll to begin ↓</div>
  </div>
</section>

<style>
  .hero {
    min-height: 92vh;
    display: flex;
    align-items: center;
    border-top: none;
    padding-top: 7vh;
  }
  h1 {
    font-size: clamp(46px, 8vw, 88px);
    margin-bottom: 18px;
  }
  .stats {
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    margin: 34px 0 6px;
  }
  .stat {
    text-align: center;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.45;
  }
  .big {
    font-size: clamp(30px, 4.2vw, 44px);
    color: var(--accent);
  }
  .scrollhint {
    margin-top: 40px;
    color: var(--faint);
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
</style>
