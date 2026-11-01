<script>
  import Section from "../components/Section.svelte";
  import { fmtInt, fmtM, fmtDays } from "../lib/data.js";

  let { d } = $props();

  // Merge the two YJMob100K sub-datasets into one gallery card.
  const cards = $derived.by(() => {
    const rows = [...d.datasets];
    const yj = rows.filter((r) => r.key.startsWith("yjmob"));
    const rest = rows.filter((r) => !r.key.startsWith("yjmob"));
    if (yj.length) {
      rest.splice(1, 0, {
        ...yj[0],
        key: "yjmob",
        label: "YJMob100K",
        n_users: yj.reduce((a, r) => a + r.n_users, 0),
        records: null,
        unit: "grid pings",
        note: `${yj.length} sub-datasets · 500 m grid`,
      });
    }
    return rest;
  });
</script>

<Section
  id="data"
  kicker="The evidence"
  title="Six datasets, one question"
  lede="Some people carried a GPS logger that woke up every few seconds. Others
  only left a trace when they chose to 'check in'. That difference — how you were
  watched — will decide everything you see below."
>
  <div class="grid cards">
    {#each cards as r, i (r.key)}
      <div class="panel card" data-reveal>
        <div class="row1">
          <span class="name">{r.label}</span>
          <span class="badge" class:vol="{r.volunteered}">
            {r.volunteered ? "check-ins" : "logged"}
          </span>
        </div>
        <div class="city">{r.city} · {r.country}</div>
        <p class="watch">{r.watch}</p>
        <div class="nums">
          <div><b>{fmtInt(r.n_users)}</b><span>people</span></div>
          <div><b>{r.records != null ? fmtM(r.records) : "112M"}</b><span>{r.unit}</span></div>
          <div><b>{fmtDays(r.span_days)}</b><span>time span</span></div>
          <div>
            <b>{r.median_user_days != null ? `${r.median_user_days} d` : "—"}</b>
            <span>median days w/ data</span>
          </div>
        </div>
      </div>
    {/each}
  </div>

  <p class="caption" data-reveal>
    <span class="words">How long is “long enough”? For the best-studied GPS
    people (GeoLife) the median analyzable person was seen on 75 different days.
    Check-in apps span years, but a typical Gowalla person only ever checks in
    11 times — a diary with most pages torn out.</span>
  </p>
</Section>

<style>
  .cards {
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    margin-top: 26px;
  }
  .card { padding: 18px 20px; }
  .row1 { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .name { font-size: 20px; font-weight: 700; }
  .badge {
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; padding: 3px 9px; border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--accent); white-space: nowrap;
  }
  .badge.vol {
    background: color-mix(in srgb, var(--accent-2) 15%, transparent);
    color: var(--accent-2);
  }
  .city { color: var(--muted); font-size: 14px; margin: 2px 0 8px; }
  .watch { color: var(--ink); font-size: 15px; min-height: 44px; }
  .nums {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
    border-top: 1px solid var(--line); padding-top: 12px; margin-top: 6px;
  }
  .nums b { font-size: 17px; color: var(--accent); display: block; }
  .nums span { font-size: 11px; color: var(--faint); line-height: 1.3; display: block; }
  @media (max-width: 520px) { .nums { grid-template-columns: repeat(2, 1fr); } }
</style>
