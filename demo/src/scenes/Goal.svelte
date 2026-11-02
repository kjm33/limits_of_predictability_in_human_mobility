<script>
  // Static scene: the project's goal — a proactive, local-first navigation
  // agent. No data.json payload needed; copy only.
  let { d } = $props();
  const n = $derived(d.hero.n_datasets);
</script>

<section class="scene" id="goal">
  <div class="wrap">
    <span class="kicker" data-reveal>The goal</span>
    <h2 data-reveal>A navigator that offers help before you ask</h2>
    <p class="lede" data-reveal>
      The paper measured a limit. We want to spend it: a navigation agent that
      notices <em>where you are, what day it is, and what time it is</em>,
      recognizes a trip you have made before, and has the route ready before
      you reach for the phone.
    </p>

    <div class="grid two">
      <div class="panel phone" data-reveal>
        <div class="notch"></div>
        <div class="statusbar">
          <span>Mon 15:04</span>
          <span>on-device</span>
        </div>
        <div class="notif">
          <div class="nhead">⚡ usual trip starting?</div>
          <p class="nbody">
            Mondays around 15:00 you head to <b>the same place</b> —
            seen in 3 different weeks. Want the route ready?
          </p>
          <div class="nbtns">
            <span class="nbtn yes">prepare route</span>
            <span class="nbtn">not now</span>
          </div>
        </div>
        <p class="pfoot">
          The offer names a destination and shows its evidence — the number of
          weeks behind it — because a suggestion you can check is a suggestion
          you can trust.
        </p>
      </div>

      <div class="panel priv" data-reveal>
        <h3>Why this can stay on your device</h3>
        <p>
          Everything the agent needs is <b>counting</b>: how often you were in
          each place at this weekday × time, and where those trips ended.
          No servers, no training runs on your data — the location history the
          agent learns from <b>never needs to leave the device</b>.
        </p>
        <p>
          The counting methods are simple and cheap by design — the kind of
          work a phone or another edge device can do on its own. That
          simplicity is not a compromise: later scenes show that on
          diary-sized data, counting is already close to the theoretical
          ceiling.
        </p>
        <p class="fine">
          What we evaluate here is the method (on {n} public research
          datasets), not a phone app — on-device operation is the design goal,
          not a benchmarked result. And one thing may still leave the device:
          if you accept a route, a routing service receives the
          origin → destination pair to calculate it.
        </p>
      </div>
    </div>

    <p class="caption" data-reveal>
      <span class="words">In words: the rest of this page is the evidence
      chain for that one notification — from raw location noise to a rule with
      weeks of history behind it, and the measured limits of how well any such
      agent can ever call your next move.</span>
    </p>
  </div>
</section>

<style>
  .two {
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
    margin-top: 26px;
    align-items: stretch;
  }
  .phone {
    background: var(--bg-2);
    border-radius: 26px;
    padding: 26px 22px 18px;
    display: flex;
    flex-direction: column;
  }
  .notch {
    width: 90px; height: 6px; border-radius: 999px;
    background: var(--line); margin: 0 auto 14px;
  }
  .statusbar {
    display: flex; justify-content: space-between;
    font-size: 12px; color: var(--faint);
    font-variant-numeric: tabular-nums; margin-bottom: 14px;
  }
  .notif {
    background: color-mix(in srgb, var(--accent) 7%, var(--panel));
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    border-radius: 16px; padding: 16px 18px;
  }
  .nhead {
    font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase;
    font-size: 12.5px; color: var(--accent); margin-bottom: 6px;
  }
  .nbody { color: var(--muted); font-size: 15.5px; margin: 0 0 12px; }
  .nbody b { color: var(--ink); }
  .nbtns { display: flex; gap: 8px; }
  .nbtn {
    font-size: 13px; font-weight: 600; color: var(--muted);
    border: 1px solid var(--line); border-radius: 999px; padding: 5px 14px;
  }
  .nbtn.yes {
    color: var(--bg); background: var(--accent); border-color: var(--accent);
  }
  .pfoot {
    margin: auto 0 0; padding-top: 14px;
    font-size: 13px; color: var(--faint); line-height: 1.5;
  }
  .priv h3 { margin: 0 0 10px; font-size: 19px; }
  .priv p { color: var(--muted); font-size: 15px; line-height: 1.6; }
  .priv p b { color: var(--ink); }
  .priv .fine {
    font-size: 12.5px; color: var(--faint);
    border-top: 1px dashed var(--line); padding-top: 10px; margin-bottom: 0;
  }
  @media (max-width: 860px) { .two { grid-template-columns: 1fr; } }
</style>
