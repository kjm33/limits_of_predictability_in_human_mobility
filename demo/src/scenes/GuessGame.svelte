<script>
  import Section from "../components/Section.svelte";

  let { d } = $props();
  const g = $derived(d.game);

  const palette = {
    home: "#5eead4", work: "#f0abfc", gym: "#fbbf24", shop: "#7dd3fc",
    pub: "#fb7185", park: "#a3e635",
    a: "#7dd3fc", b: "#f0abfc", c: "#fbbf24", d: "#fb7185",
    e: "#a3e635", f: "#5eead4", g: "#c4b5fd", h: "#f9a8d4",
  };

  let revealed = $state(false);

  const personas = $derived([
    { key: "regular", name: "Diary A", who: "the commuter" },
    { key: "wanderer", name: "Diary B", who: "the wanderer" },
  ]);
</script>

<Section
  id="entropy"
  kicker="The betting game"
  title="How predictable is a life? Guess first."
  lede="No formulas — just a game. Two people, one week each, shown as colored
  dots (one dot = one place per part of the day). Before we reveal anything:
  which diary could a clever bettor call correctly more often?"
>
  <div class="grid two">
    {#each personas as p (p.key)}
      {@const who = g[p.key]}
      <div class="panel diary" data-reveal>
        <div class="dhead">
          <h3>{p.name}</h3>
          <span class="tag">{revealed ? p.who : "??"}</span>
        </div>
        <div class="dots">
          {#each who.diary.slice(0, 84) as name, i (i)}
            <span class="dot" style="background: {palette[name] ?? '#5c7085'}"
              title={name}></span>
          {/each}
        </div>
        <p class="dsub">first two weeks shown · {who.diary.length} observations total</p>

        {#if revealed}
          <div class="verdict">
            <div class="vrow">
              <span>different places visited</span>
              <b>{who.N}</b>
            </div>
            <div class="vrow">
              <span>surprise per step, ignoring order</span>
              <b>{who.S_unc} bits</b>
            </div>
            <div class="vrow">
              <span>surprise per step, using history</span>
              <b>{who.S_actual} bits</b>
            </div>
            <div class="vrow big">
              <span>best possible guesser's accuracy</span>
              <b>{Math.round(who.Pi_actual * 100)}%</b>
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <div class="ctrl" data-reveal>
    {#if !revealed}
      <button class="primary" onclick={() => (revealed = true)}>reveal the numbers</button>
    {:else}
      <p class="after">
        Diary A is the commuter: history cuts its surprise from 1.61 to 0.09 bits
        per step — a perfect guesser could be right <b>99 times in 100</b>.
        Diary B is the wanderer: history barely helps (2.98 → 2.72), capping
        anyone at <b>~37 in 100</b>. The gap between those two numbers — surprise
        with vs without memory — is the entire reason “where will you be next”
        is learnable at all. Real people sit in between; where exactly, the next
        section shows.
      </p>
    {/if}
  </div>
</Section>

<style>
  .two { grid-template-columns: 1fr 1fr; margin-top: 24px; }
  .diary { padding: 20px; }
  .dhead { display: flex; justify-content: space-between; align-items: baseline; }
  .dhead h3 { margin: 0; font-size: 20px; }
  .tag {
    font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--accent-2);
  }
  .dots {
    display: grid; grid-template-columns: repeat(21, 1fr); gap: 3px;
    margin: 16px 0 8px;
  }
  .dot { width: 100%; aspect-ratio: 1; border-radius: 50%; }
  .dsub { font-size: 12px; color: var(--faint); margin: 0; }
  .verdict { border-top: 1px solid var(--line); margin-top: 14px; padding-top: 10px; }
  .vrow {
    display: flex; justify-content: space-between; padding: 5px 0;
    color: var(--muted); font-size: 15px;
  }
  .vrow b { color: var(--ink); }
  .vrow.big { font-size: 17px; }
  .vrow.big b { color: var(--accent); font-size: 22px; }
  .ctrl { margin-top: 22px; }
  .primary {
    background: color-mix(in srgb, var(--accent) 22%, var(--panel-2));
    border-color: var(--accent); font-weight: 600;
  }
  .after { color: var(--muted); max-width: 60ch; }
  .after b { color: var(--accent); }
  @media (max-width: 720px) { .two { grid-template-columns: 1fr; } }
</style>
