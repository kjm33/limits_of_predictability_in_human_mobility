<script>
  import Count from "../components/Count.svelte";

  let { d } = $props();
  const h = $derived(d.hero);
</script>

<section class="scene hero" id="hero">
  <div class="wrap">
    <p class="kicker" data-reveal>The inspiration · Song et al., Science 2010</p>
    <h1 data-reveal>Monday, 15:04 —<br />Your Agent Speaks First</h1>
    <p class="lede" data-reveal>
      In 2010, four physicists asked a question navigation apps had quietly
      given up on: <strong>is your next location predictable at all — and by
      how much, at best?</strong> Their answer started this project. This page
      re-asks it with <strong>{h.people.toLocaleString("en-US")}</strong>
      people across {h.n_datasets} datasets, then spends the answer on one
      idea: an agent that offers your route before you ask.
    </p>

    <div class="panel paper" data-reveal>
      <div class="phead">
        <span class="ptitle">Limits of Predictability in Human Mobility</span>
        <span class="pauth">Song, Qu, Blumm &amp; Barabási · Science 327, 1018 (2010)</span>
      </div>
      <div class="pgrid">
        <div class="pcol">
          <h3>What they did</h3>
          <p>Studied <b>45,000</b> anonymized mobile-phone users (screened
          from ~10 million) over <b>3 months</b>. Each person became a
          sequence: the tower area they used, one entry per hour. Then they
          measured each sequence's <b>entropy</b> — its leftover surprise —
          and converted it with <b>Fano's inequality</b> into a ceiling on
          prediction accuracy.</p>
        </div>
        <div class="pcol">
          <h3>What they found</h3>
          <p>The ceiling averaged <b>93%</b> — and varied remarkably little:
          in their data nobody sat below 80%, whether someone covered a few
          kilometres a week or hundreds. Regularity looked intrinsic to us,
          not imposed by commute distance.</p>
        </div>
        <div class="pcol">
          <h3>What it is not</h3>
          <p>93% is <em>potential</em>: the best any algorithm <em>could</em>
          reach on tower-scale locations, not what any app achieved — the
          paper built no predictor. On our finer, sparser data the ceilings
          come out lower, and honest gaps remain. That tension is this
          story.</p>
        </div>
      </div>
    </div>

    <div class="grid stats" data-reveal>
      <div class="panel stat">
        <div class="big"><Count value={h.people} /></div>
        <div>people, re-asking the question</div>
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
      schedule regular enough to detect automatically — and when the system
      says “this person will do X now”, it is right roughly 9 times out of 10.
      Whether that is enough for a proactive agent, and for whom, is what
      follows.</span>
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
  .paper { margin-top: 30px; padding: 22px 24px; }
  .phead { margin-bottom: 14px; }
  .ptitle { display: block; font-size: 20px; font-weight: 700; }
  .pauth {
    font-size: 13px; color: var(--faint);
  }
  .pgrid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
  }
  .pcol h3 {
    margin: 0 0 8px; font-size: 13px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--accent);
  }
  .pcol p { color: var(--muted); font-size: 14px; line-height: 1.55; margin: 0; }
  .pcol p b { color: var(--ink); }
  .pcol p em { color: var(--ink); font-style: italic; }
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
  @media (max-width: 860px) { .pgrid { grid-template-columns: 1fr; } }
</style>
