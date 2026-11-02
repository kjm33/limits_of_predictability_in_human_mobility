<script>
  import Section from "../components/Section.svelte";

  let { d } = $props();

  // Real anchor card (GeoLife user 022) — same shape as the toy example below.
  const real = $derived(d.user022.cards[0]);

  let tallied = $state(false);

  // Illustrative diary: one person, four Mondays, all in the 15:00–15:15 slot.
  const rows = [
    { week: "week 1", time: "15:04", from: "A", to: "B" },
    { week: "week 2", time: "15:09", from: "A", to: "B" },
    { week: "week 3", time: "15:02", from: "A", to: "C" },
    { week: "week 4", time: "15:11", from: "A", to: "B" },
  ];

  const chipColor = { A: "#7dd3fc", B: "#f0abfc", C: "#fbbf24" };
</script>

<Section
  id="tally"
  kicker="The counter"
  title="How a routine gets counted"
  lede="The scenes above proved prediction can work in principle. This is the
  actual arithmetic: turn trips into rows, group the matching ones, and tally
  where they went. No model is trained anywhere in this step."
>
  <div class="panel recs" data-reveal>
    <div class="rhead">
      <h3>Every trip becomes one row</h3>
      <span class="rill">illustrative diary</span>
    </div>
    <p class="rsub">
      One person, four Mondays, every departure inside the same quarter-hour
      slot — 15:00 to 15:15:
    </p>
    <div class="trows">
      <div class="thead">
        <span>week</span><span>departure</span><span>trip</span>
      </div>
      {#each rows as r, i (i)}
        <div class="trow" data-reveal>
          <span class="rwk">{r.week}</span>
          <span class="rtm">Mon {r.time}</span>
          <span class="rtrip">
            <span class="chip" style="background: {chipColor[r.from]}"></span>
            {r.from}
            <span class="arr">→</span>
            <span class="chip" style="background: {chipColor[r.to]}"></span>
            <b>{r.to}</b>
          </span>
        </div>
      {/each}
    </div>
    <p class="rnote">
      A, B and C are <em>places</em>, not points — the clusters the
      “Noise → places” scene built. One trip is one row no matter how many GPS
      fixes it contains: a nine-hour workday is one visit, not thirty
      thousand votes.
    </p>
  </div>

  <div class="ctrl" data-reveal>
    {#if !tallied}
      <button class="primary" onclick={() => (tallied = true)}>
        tally the Monday 15:00–15:15 departures
      </button>
    {:else}
      <p class="after">
        Same person, same weekday, same quarter-hour, same origin — so the four
        rows form <b>one group</b>. Now count where they went.
      </p>
    {/if}
  </div>

  {#if tallied}
    <div class="panel tally" data-reveal>
      <div class="qleft">
        <h3>The question</h3>
        <p class="qsub">
          Leaving <b>A</b> on a Monday, 15:00–15:15 — where does this person
          go?
        </p>
        <div class="votes">
          {#each [{ to: "B", votes: 3, weeks: 3 }, { to: "C", votes: 1, weeks: 1 }] as v (v.to)}
            <div class="vrow">
              <span class="vlab">
                <span class="chip" style="background: {chipColor[v.to]}"></span>
                {v.to}
              </span>
              <div class="vtrack">
                <div class="vfill" style="width: {v.votes / 3 * 100}%; background: {chipColor[v.to]}"></div>
              </div>
              <span class="vval">{v.votes} {v.votes === 1 ? "vote" : "votes"}</span>
              <span class="vwk">{v.weeks} different {v.weeks === 1 ? "week" : "weeks"}</span>
            </div>
          {/each}
        </div>
        <p class="qword">
          B gets three marks, C gets one — that is the entire tally.
        </p>
      </div>
      <div class="mright">
        <h3>What the tally becomes</h3>
        {#each [
          {
            n: "3 weeks", name: "SUPPORT",
            v: "B recurred in three separate weeks — repeats crammed into one week still count as one week.",
          },
          {
            n: "75%", name: "CONFIDENCE",
            v: "three of the four matching departures went to B; the fourth went elsewhere.",
          },
          {
            n: "75%", name: "STABILITY",
            v: "B appeared in three of the four weeks that had any such departure — weeks with no departure don't count against it.",
          },
        ] as m (m.name)}
          <div class="met">
            <span class="mnum num">{m.n}</span>
            <div class="mtxt">
              <span class="mname">{m.name}</span>
              <span class="mword">{m.v}</span>
            </div>
          </div>
        {/each}
      </div>
    </div>

    <div class="panel verdict" data-reveal>
      <div class="vhead">
        <h3>Three gates, then a card</h3>
        <div class="gates">
          <span class="gate ok">support ≥ 3 weeks ✓</span>
          <span class="gate ok">confidence ≥ 50% ✓</span>
          <span class="gate ok">score 0.75 × 0.75 ≈ 0.56 ≥ 0.5 ✓</span>
        </div>
      </div>
      <div class="card">
        <div class="cwhen">
          <span class="chip" style="background: {chipColor.A}"></span>
          Monday · 15:00–15:15 · leaving A
        </div>
        <div class="cgo">
          usual destination
          <b><span class="chip" style="background: {chipColor.B}"></span> B</b>
        </div>
        <div class="cev">evidence: 3 weeks · 3 of 4 trips</div>
      </div>
      <p class="vnote">
        The first two gates decide the rule exists at all; the score
        (confidence × stability) is what the agent uses later to rank and act —
        this card clears all three.
      </p>
    </div>

    {#if real}
      <div class="panel forreal" data-reveal>
        <h3>For real</h3>
        <p>
          Volunteer 022's top card is exactly this shape — real numbers now:
          <b>Mondays {real.bucket_str}</b>, leaving
          {real.o_label || "his most-visited place"}: {real.n_trips} trips
          across {real.support} different weeks, and every one of them to the
          same place (confidence 100%). The finale's offer quotes this card.
        </p>
      </div>
    {/if}
  {/if}

  <p class="caption" data-reveal>
    <span class="words">Read aloud: that's the whole method — group each
    person's trips by origin, weekday and quarter-hour, then count. Grouping
    and tallying, simple enough to run on a phone; nothing is fitted or
    learned. The next scene runs this one counter on all six datasets and asks
    a different question: how many people have such rules at all?</span>
  </p>
</Section>

<style>
  .recs { padding: 20px 22px; }
  .rhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .rhead h3 { margin: 0 0 6px; font-size: 17px; color: var(--ink); }
  .rill {
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--warn); white-space: nowrap;
  }
  .rsub { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
  .trows { display: grid; gap: 6px; }
  .thead, .trow {
    display: grid; grid-template-columns: 90px 130px 1fr; gap: 12px;
    align-items: center;
  }
  .thead {
    font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--faint); padding: 0 12px;
  }
  .trow {
    background: var(--bg-2); border: 1px solid var(--line);
    border-radius: 8px; padding: 9px 12px; font-variant-numeric: tabular-nums;
  }
  .rwk, .rtm { color: var(--muted); font-size: 14.5px; }
  .rtrip { display: flex; align-items: center; gap: 7px; font-size: 15px; }
  .rtrip b { color: var(--ink); }
  .arr { color: var(--faint); }
  .chip {
    width: 12px; height: 12px; border-radius: 4px; display: inline-block;
    flex: none;
  }
  .rnote {
    color: var(--muted); font-size: 13px; line-height: 1.5; margin: 14px 0 0;
    border-top: 1px dashed var(--line); padding-top: 10px;
  }
  .rnote em { color: var(--ink); font-style: normal; font-weight: 600; }

  .ctrl { margin-top: 22px; }
  .primary {
    background: color-mix(in srgb, var(--accent) 22%, var(--panel-2));
    border-color: var(--accent); font-weight: 600;
  }
  .after { color: var(--muted); max-width: 60ch; }
  .after b { color: var(--accent); }

  .tally {
    margin-top: 22px; padding: 22px;
    display: grid; grid-template-columns: 1fr 1.15fr; gap: 26px;
  }
  .tally h3 { margin: 0 0 10px; font-size: 17px; color: var(--ink); }
  .qsub { color: var(--muted); font-size: 14.5px; }
  .qsub b { color: var(--ink); }
  .votes { display: grid; gap: 10px; margin: 14px 0 10px; }
  .vrow {
    display: grid; grid-template-columns: 44px 1fr 70px; gap: 10px;
    align-items: center;
  }
  .vlab {
    display: flex; align-items: center; gap: 6px; font-weight: 700;
    font-size: 15px;
  }
  .vtrack {
    height: 22px; background: var(--bg-2); border: 1px solid var(--line);
    border-radius: 6px; overflow: hidden;
  }
  .vfill { height: 100%; border-radius: 5px 0 0 5px; transition: width 0.6s ease; }
  .vval { font-size: 13px; color: var(--ink); text-align: right; }
  .vwk {
    grid-column: 2 / 4; font-size: 12px; color: var(--faint); margin-top: -6px;
  }
  .qword { color: var(--muted); font-size: 13.5px; margin: 8px 0 0; }
  .mright { display: grid; gap: 12px; align-content: start; }
  .met {
    display: grid; grid-template-columns: 86px 1fr; gap: 12px;
    align-items: center; border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 14px; background: var(--bg-2);
  }
  .mnum { font-size: 21px; color: var(--accent-2); }
  .mname {
    display: block; font-size: 11px; letter-spacing: 0.1em; color: var(--faint);
    font-weight: 700;
  }
  .mword { font-size: 12.5px; color: var(--muted); line-height: 1.45; }

  .verdict { margin-top: 16px; padding: 20px 22px; }
  .vhead h3 { margin: 0 0 10px; font-size: 17px; color: var(--ink); }
  .gates { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
  .gate {
    font-size: 13px; font-weight: 600; padding: 6px 12px;
    border-radius: 999px; border: 1px solid var(--line); color: var(--muted);
  }
  .gate.ok {
    color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
    background: color-mix(in srgb, var(--accent) 10%, var(--panel));
  }
  .card {
    background: var(--bg-2); border: 1px solid
    color-mix(in srgb, var(--accent) 45%, var(--line));
    border-radius: 12px; padding: 16px 18px; display: grid; gap: 6px;
  }
  .cwhen {
    display: flex; align-items: center; gap: 8px; font-size: 11px;
    letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint);
    font-weight: 700;
  }
  .cgo { font-size: 19px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
  .cgo b { color: var(--ink); display: flex; align-items: center; gap: 7px; }
  .cev { font-size: 13px; color: var(--faint); }
  .vnote {
    color: var(--muted); font-size: 13.5px; margin: 14px 0 0;
    border-top: 1px dashed var(--line); padding-top: 10px;
  }

  .forreal { margin-top: 16px; padding: 18px 22px; }
  .forreal h3 { margin: 0 0 8px; font-size: 16px; color: var(--ink); }
  .forreal p { color: var(--muted); font-size: 14.5px; margin: 0; }
  .forreal b { color: var(--accent); }

  @media (max-width: 860px) {
    .tally { grid-template-columns: 1fr; }
    .thead { display: none; }
    .trow { grid-template-columns: 70px 96px 1fr; gap: 8px; }
  }
</style>
