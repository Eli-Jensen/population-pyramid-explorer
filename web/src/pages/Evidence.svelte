<script lang="ts">
  // /evidence (PLAN §7 J11): the question stated neutrally; the four evidence links with effect sizes and citations; the
  // China 1990 row; this site's own pre-registered backtest (primary growth row with N_eff / CI / nulls, the returns row
  // with its investability counts beside VT, the equal-weight basket vs VT, the decision levels and the only sentences
  // the UI may render); the investability table (live / liquidated with dates and issuer notices, MSCI Nigeria
  // deletion); the vintage caveat; sources & licences; what this site never does. Every number comes from
  // web/src/data/evidence.json (scripts/export_econ_ui.py) — nothing is typed in by hand. Units: wherever this page
  // says %/yr the figure is a CAGR (the L0.vs_vt unit; the export carries both units, nothing is converted here);
  // pp/yr marks differences of annualised log returns (RESULTS §4/§6). Interpretive words ("includes 0", "did not
  // beat", the partial-window years, the Spearman range) are derived from the JSON, not typed.
  import { evidence as ev, ci, ciCovers0, logToCagr, logToTotal, multiple, num, p, pct, pp, STATUS_LABEL, topShare } from '../lib/econ/evidence.ts';
  import { byId, meta } from '../lib/entities.ts';
  import { app } from '../lib/state.svelte.ts';
  import { href } from '../lib/url.ts';
  import { countryQuery } from '../lib/router.ts';

  const bt = ev.backtest;
  const g = bt.growth;
  const g20 = bt.growth_20;
  const r = bt.returns;
  const dec = ev.decision;
  const china = ev.china.row;
  const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const nameOf = (id: string) => byId(id)?.short_name ?? id;
  const link = (id: string, year: number) => (byId(id) ? href(countryQuery(id, year, { lens: 'econ' })) : null);
  const vintageB = ev.vintage.rows.filter((x) => x.query === 'B' && x.k === 10).sort((a, b) => a.T - b.T);
  const vintageA = ev.vintage.rows.filter((x) => x.query !== 'B' && x.k === 10).sort((a, b) => a.T - b.T || a.query.localeCompare(b.query));
  const singles = ev.investability.rows.filter((x) => x.role === 'single_country');
  const benchmarks = ev.investability.rows.filter((x) => x.role !== 'single_country');
  const liquidated = singles.filter((x) => x.status !== 'live');
  const conditionRows = Object.entries(dec.conditions);
  const noteFor = (sentence: string) => dec.rendered_notes.find((n) => n.sentence === sentence) ?? null;
  const chinaFundLater = china?.fund.inception ? Number(china.fund.inception.slice(0, 4)) > china.year : false;
  const waAccounted = dec.conditions.p2_met?.available && dec.conditions.p2_met.ok;
  const ewBeatVt = bt.predictions.P3b ? !bt.predictions.P3b.met : null;
  const readYear = $derived(app.currentYear);
  const fmtValue = (v: unknown): string => {
    if (v === null || v === undefined) return 'n/a';
    if (typeof v === 'number') return num(v, 3);
    if (Array.isArray(v)) return `[${v.map((x) => (typeof x === 'number' ? num(x, 2) : String(x))).join(', ')}]`;
    if (typeof v === 'object') return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} = ${typeof x === 'number' ? num(x, 3) : x === null ? 'n/a' : String(x)}`).join('; ');
    return String(v);
  };
  const SECTIONS = [
    ['question', 'The question'],
    ['links', 'What the literature found'],
    ['china', 'China 1990'],
    ['backtest', "This site's backtest: growth"],
    ['returns', 'Returns beside VT'],
    ['decision', 'Decision levels and allowed language'],
    ['investability', 'Investability'],
    ['vintage', 'Vintage caveat'],
    ['sources', 'Sources & licences'],
    ['never', 'What this site never does'],
  ] as const;
</script>

<article class="mx-auto max-w-3xl py-6 leading-relaxed">
  <h1 class="text-3xl font-semibold tracking-tight">Evidence</h1>
  <p class="mt-2 text-fg-2">
    Past figures, sources and this site's own pre-registered test, read in {readYear}. Backtest run {ev.built.slice(0, 10)} (code {ev.backtest_git_rev}, PREREG
    <code class="text-xs">{ev.prereg_commit.slice(0, 8)}</code>); literature notes transcribed {ev.transcribed ?? 'n/a'}. Nothing on this page is a forecast.
  </p>
  <nav aria-label="On this page" class="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-sm">
    {#each SECTIONS as [id, label] (id)}
      <a class="underline decoration-border underline-offset-2 hover:decoration-fg" href="#{id}">{label}</a>
    {/each}
  </nav>

  <!-- ============================================================ question -->
  <section id="question" class="mt-10 space-y-3">
    <h2 class="text-xl font-semibold tracking-tight">The question</h2>
    <p>{ev.question}</p>
    <p class="text-sm text-fg-2">
      Levels granted by the pre-registered decision rules: <strong>{dec.levels_granted.join(', ')}</strong> ({dec.levels[dec.levels_granted[0] ?? 'L0']?.name}).
      {#each Object.entries(dec.levels) as [id, lv] (id)}{#if !lv.granted}<span class="mr-1">{id} ({lv.name}) was not granted{lv.failed.length ? ` — failed: ${lv.failed.join(', ')}` : ''}.</span>{/if}{/each}
    </p>
  </section>

  <!-- ============================================================ links -->
  <section id="links" class="mt-10 space-y-6">
    <h2 class="text-xl font-semibold tracking-tight">What the literature found</h2>
    <p class="text-sm text-fg-2">Four links, each with its effect size, sample and citation. <strong>V</strong> = the primary source was read on {ev.transcribed ?? 'the transcription day'}; <strong>M</strong> = from memory or secondary reporting, not verified.</p>
    {#each ev.links as l (l.id)}
      <div class="card">
        <h3 class="font-semibold">{l.title} <span class="chip ml-1 font-normal">{l.strength}</span></h3>
        <p class="mt-1 text-sm text-fg-2">{l.summary}</p>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">finding</th><th class="py-1 pr-2 font-medium">effect</th><th class="py-1 pr-2 font-medium">sample</th><th class="py-1 pr-2 font-medium">citation</th><th class="py-1 font-medium">flag</th></tr></thead>
            <tbody>
              {#each l.findings as f, i (i)}
                <tr class="border-t border-border align-top">
                  <td class="py-1 pr-2">{f.claim}</td>
                  <td class="py-1 pr-2 tabular-nums text-fg-2">{f.effect ?? ''}</td>
                  <td class="py-1 pr-2 text-fg-2">{f.sample ?? ''}</td>
                  <td class="py-1 pr-2 text-fg-2">{#if f.url}<a class="underline" href={f.url} rel="noopener" target="_blank">{f.citation}</a>{:else}{f.citation ?? ''}{/if}{#if f.companion_url} · <a class="underline" href={f.companion_url} rel="noopener" target="_blank">companion</a>{/if}</td>
                  <td class="py-1 font-mono text-muted" title={f.verified ? 'primary source read' : 'from memory / secondary reporting'}>{f.verified ? 'V' : 'M'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/each}
  </section>

  <!-- ============================================================ china -->
  <section id="china" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">China 1990 — and who looked like it in 2024</h2>
    {#if china}
      <p>
        <a class="underline" href={link('CHN', 1990)}>China 1990</a>: age split {pct(china.pyramid.u15, 1)} / {pct(china.pyramid.wa, 1)} / {pct(china.pyramid.o65, 1)} (0–14 / 15–64 / 65+), median age {num(china.pyramid.median_age, 1)}, TFR {num(china.pyramid.tfr, 2)}.
        GDP per capita {china.levels.y_t !== null ? `$${money.format(china.levels.y_t)}` : 'n/a'}{china.levels.source ? ` (${china.levels.source})` : ''} → {multiple(china.levels.multiples?.['10'])} in 10 years, {multiple(china.levels.multiples?.['20'])} in 20, {multiple(china.levels.multiples?.['30'])} in 30
        {#if china.levels.mult_last !== null}({multiple(china.levels.mult_last)} by {china.levels.y_last_year}){/if}.
        {#if china.levels.source && !/Maddison/.test(china.levels.source)}<span class="text-sm text-fg-2">The country page's economic context prints Maddison 2011 $ for the same year and the table below WDI 2021 $; the three differ by source and base year, the multiples do not depend on it.</span>{/if}
      </p>
      {#if china.msci.state === 'ok'}
        <p>
          {china.msci.index_name}: {pp(china.msci.ann_pct_gross_since)} %/yr (USD, gross) since {china.msci.since}, maximum drawdown {num(china.msci.max_drawdown_pct_gross, 1)} %
          {#if china.msci.max_drawdown_period_gross}({china.msci.max_drawdown_period_gross[0]} → {china.msci.max_drawdown_period_gross[1]}){/if};
          net {pp(china.msci.ann_pct_net_since)} %/yr since {china.msci.net_since}.
          <a class="underline" href={china.msci.url_gross ?? '#'} rel="noopener" target="_blank">MSCI factsheet</a> as of {china.msci.as_of}, accessed {china.msci.accessed}; facts transcribed, no series downloaded.
        </p>
      {/if}
      {#if china.fund.state === 'ok' && china.fund.ticker}
        <p class="text-sm text-fg-2">
          {china.fund.ticker} ({china.fund.name}) {china.fund.entry_used} → {china.fund.exit_used} ({num(china.fund.window_years, 1)} y): {pp(china.fund.cagr_pct)} %/yr, maximum drawdown {pct(china.fund.max_dd, 0)}
          · VT over the same window {pp(china.fund.vt_cagr_pct)} %/yr{china.fund.vt_benchmark === 'vt_proxy' ? ' (VT proxy before 2008-06-24)' : ''} · SPY {pp(china.fund.spy_cagr_pct)} · EEM {pp(china.fund.eem_cagr_pct)} %/yr.
          The fund began {china.fund.inception}{#if chinaFundLater}; in {china.year} {bt.no_etf_rows[String(china.year)] ?? 'no US-listed single-country fund existed'}{/if}.
        </p>
      {/if}
    {/if}
    {#each dec.rendered['L0.disconnect'] ?? [] as s, i (i)}
      <p class="text-sm text-fg-2">{s}</p>
    {/each}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <caption class="text-left text-xs text-muted">2024 age structures nearest China 1990, and the two structures China had; {ev.china.source}</caption>
        <thead class="text-left text-xs text-muted"><tr><th class="py-1 pr-3 font-medium">economy & year</th><th class="py-1 pr-3 font-medium">15–64 %</th><th class="py-1 pr-3 font-medium">dependency</th><th class="py-1 pr-3 font-medium">median age</th><th class="py-1 pr-3 font-medium">TFR</th><th class="py-1 font-medium">GDP/cap PPP (2021 $)</th></tr></thead>
        <tbody>
          {#each ev.china.rows as row (row.label)}
            <tr class="border-t border-border tabular-nums"><td class="py-1 pr-3">{row.label}</td><td class="py-1 pr-3">{row.wa_pct}</td><td class="py-1 pr-3">{row.dependency}</td><td class="py-1 pr-3">{row.median_age}{row.note?.includes('median') ? ' (2026)' : ''}</td><td class="py-1 pr-3">{row.tfr}</td><td class="py-1">{money.format(row.gdppc_ppp_2021usd)}{row.note && !row.note.includes('median') ? ` (${row.note})` : ''}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-sm text-fg-2">{ev.china.reading}</p>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <caption class="text-left text-xs text-muted">Disconnect table (RESULTS §6): historical booms and the 2024 lookalikes, GDP multiples beside the cited index facts and the fund window beside VT</caption>
        <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">country · year</th><th class="py-1 pr-2 font-medium">d to CHN 1990</th><th class="py-1 pr-2 font-medium">GDP/cap multiples</th><th class="py-1 pr-2 font-medium">MSCI (cited)</th><th class="py-1 font-medium">fund vs VT</th></tr></thead>
        <tbody>
          {#each ev.disconnect.rows as d (d.iso3 + d.year)}
            <tr class="border-t border-border align-top">
              <td class="py-1 pr-2">{#if link(d.iso3, d.year)}<a class="underline" href={link(d.iso3, d.year)}>{d.name} {d.year}</a>{:else}{d.name} {d.year}{/if} <span class="text-muted">({d.kind})</span></td>
              <td class="py-1 pr-2 tabular-nums">{num(d.distance.d_blend_chn1990, 3)} <span class="text-muted">({d.distance.pct_band})</span></td>
              <td class="py-1 pr-2 tabular-nums">{#if d.levels.multiples}{Object.entries(d.levels.multiples).map(([h, m]) => `${h}y ${multiple(m)}`).join(' / ')}{:else}{d.levels.state ?? 'n/a'}{/if}</td>
              <td class="py-1 pr-2 tabular-nums">{#if d.msci.state === 'ok'}{pp(d.msci.ann_pct_gross_since)} %/yr since {d.msci.since}, max DD {num(d.msci.max_drawdown_pct_gross, 1)} %{:else}no MSCI figure transcribed{/if}</td>
              <td class="py-1 tabular-nums">
                {#if d.fund.state === 'ok' && d.fund.ticker}
                  {d.fund.ticker} {d.fund.entry_used?.slice(0, 4)}→{d.fund.exit_used?.slice(0, 4)}:
                  {#if d.fund.too_short_to_annualise}
                    {pct(d.fund.total_return, 1)} total over {num(d.fund.window_years, 2)} y (not annualised)
                    · VT {pct(logToTotal(d.fund.vt_total_log), 1)} total over the same span (not annualised){d.fund.vt_benchmark === 'vt_proxy' ? ' (proxy)' : ''}
                  {:else}
                    {pp(d.fund.cagr_pct)} %/yr · VT {pp(d.fund.vt_cagr_pct)} %/yr{d.fund.vt_benchmark === 'vt_proxy' ? ' (proxy)' : ''}
                  {/if}
                {:else}
                  {d.fund.state === 'none_in_window' ? `no fund inside the window${d.fund.ticker ? ` (${d.fund.ticker} since ${d.fund.inception})` : ''}` : 'no US-listed single-country fund'}
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>

  <!-- ============================================================ backtest -->
  <section id="backtest" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">This site's backtest: did lookalikes of the pre-boom prototypes grow faster?</h2>
    <p class="text-sm text-fg-2">
      Pre-registered before any result was seen (PREREG commit <code class="text-xs">{ev.prereg_commit.slice(0, 8)}</code>). At each T ∈ {bt.T_grid.join(', ')} the {g.k} countries (population ≥ {money.format(bt.minpop_thousands * 1000)}) whose pyramid was closest to the
      {topShare(bt.prototype_rule.decile)} growth windows that had ended by T ("pre-boom prototypes"; {bt.prototype_rule.max_per_country} per country, ≥ {bt.prototype_rule.min_gap_years} years apart) were selected, and their GDP-per-capita growth over the following {g.h} years was compared with the median of all candidates.
      B = {bt.B} bootstrap draws, seed {bt.seed}. This is the confirmatory row; every other row in RESULTS.md is secondary.
    </p>
    <div class="card text-sm">
      <h3 class="font-semibold">{g.query_name} — k = {g.k}, h = {g.h}, growth</h3>
      <dl class="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-2 tabular-nums">
        <div><dt class="text-xs text-muted">lookalike-windows n / N_eff</dt><dd>{g.n} / <strong>{g.n_eff}</strong> {g.n_partial ? `(${g.n_partial} partial, T = 2015)` : ''}</dd></div>
        <div><dt class="text-xs text-muted">mean excess growth vs the candidate median</dt><dd><strong>{pp(g.mean_excess, 2)} pp/yr</strong></dd></div>
        <div><dt class="text-xs text-muted">headline 95 % CI (wider of country-cluster / T-block bootstrap)</dt><dd>{ci(g.ci_headline)} pp/yr — {ciCovers0(g.ci_headline)}</dd></div>
        <div><dt class="text-xs text-muted">hit rate (e &gt; 0; chance .5) · top-quartile rate (chance .25)</dt><dd>{num(g.hit_rate)} · {num(g.top_quartile_rate)}</dd></div>
        <div><dt class="text-xs text-muted">p, Hansen–Hodrick · Newey–West L2 · L4 · country cluster</dt><dd>{p(g.hh_p)} · {p(g.nw2_p)} · {p(g.nw4_p)} · {p(g.cluster_p)}</dd></div>
        <div><dt class="text-xs text-muted">null N1 (random countries), one-sided p · share of draws ≥ observed</dt><dd>{p(g.nulls.N1.p)} · {pct(g.nulls.N1.share)} of {g.nulls.N1.B}</dd></div>
        <div><dt class="text-xs text-muted">null N2 (income-matched, caliper {num(g.nulls.N2.caliper ?? 0)}), one-sided p</dt><dd>{p(g.nulls.N2.p)} · {pct(g.nulls.N2.share)} of {g.nulls.N2.B}</dd></div>
        <div><dt class="text-xs text-muted">vs N4 (prior-10-year growth momentum): Δ, CI, p</dt><dd>{pp(g.nulls.N4.delta, 2)} pp/yr {ci(g.nulls.N4.ci)} · p {p(g.nulls.N4.p)}</dd></div>
      </dl>
      <div class="mt-3 overflow-x-auto">
        <table class="w-full text-xs">
          <caption class="text-left text-muted">Per T: the {g.k} lookalikes and their excess growth vs the candidate median (pp/yr)</caption>
          <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">T</th><th class="py-1 pr-2 font-medium">candidates</th><th class="py-1 pr-2 font-medium">median growth</th><th class="py-1 pr-2 font-medium">mean excess</th><th class="py-1 pr-2 font-medium">hit rate</th><th class="py-1 font-medium">lookalikes (excess)</th></tr></thead>
          <tbody>
            {#each g.per_T as t (t.T)}
              <tr class="border-t border-border align-top tabular-nums">
                <td class="py-1 pr-2">{t.T}{t.partial ? '†' : ''}</td><td class="py-1 pr-2">{t.n_candidates}</td><td class="py-1 pr-2">{pp(t.median_g)} %/yr</td><td class="py-1 pr-2">{pp(t.mean_excess, 2)}</td><td class="py-1 pr-2">{num(t.hit_rate, 2)}</td>
                <td class="py-1">{#each t.members as pk, i (pk.iso3)}{#if i}, {/if}{#if link(pk.iso3, t.T)}<a class="underline decoration-dotted" href={link(pk.iso3, t.T)}>{nameOf(pk.iso3)}</a>{:else}{nameOf(pk.iso3)}{/if} ({pp(100 * pk.eg)}){/each}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="mt-1 text-xs text-muted">† partial window{bt.partial_note ? ` (${bt.partial_note})` : ''}.</p>
      </div>
      <p class="mt-3 text-xs text-fg-2">
        h = 20 (T ≤ 2000): mean excess {pp(g20.mean_excess, 2)} pp/yr, CI {ci(g20.ci_headline)}, N_eff {g20.n_eff}, p vs N1 {p(g20.nulls.N1.p)} · the three-band comparator (u15 / wa / o65 z-scored) differed from the 42-vector by {pp(bt.n3.delta, 2)} pp/yr (CI {ci(bt.n3.ci_headline)}, p {p(bt.n3.p_one_sided)}){' '}{#if waAccounted}— within the pre-registered margin: the working-age share alone accounted for what there was (condition p2_met){:else}— outside the pre-registered margin (condition p2_met not met){/if}.
      </p>
    </div>
    <div class="text-sm">
      <h3 class="font-semibold">The sentences the decision allows about growth</h3>
      <ul class="mt-1 list-disc space-y-1 pl-5 text-fg-2">
        {#each dec.rendered['L0.what_happened'] ?? [] as s, i (i)}<li>{s}</li>{/each}
        {#each dec.rendered['L0.null'] ?? [] as s, i (i)}<li>{s}</li>{/each}
      </ul>
    </div>
    <div class="text-sm">
      <h3 class="font-semibold">Pre-registered predictions, observed</h3>
      <ul class="mt-1 space-y-1 text-fg-2">
        {#each Object.entries(bt.predictions) as [id, pr] (id)}
          <li><span class="font-mono">{id}</span> <span class="chip ml-1">{pr.met ? 'met' : 'not met'}</span> <span class="ml-1">{pr.statement}</span></li>
        {/each}
      </ul>
    </div>
  </section>

  <!-- ============================================================ returns -->
  <section id="returns" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">Returns beside VT</h2>
    <p class="text-sm text-fg-2">
      For T ∈ {bt.returns_T.join(', ')} the same lookalikes were scored on a US-listed single-country fund's total return over the following {r.h} years (entry = last NYSE trading day of T),
      against <strong>VT</strong> (Vanguard Total World Stock ETF) over the identical window — the VT proxy SPY/EFA/EEM at the PREREG §3.5 weights before VT's first bar (2008-06-24).
      A country without a fund at entry scores no return; a fund liquidated inside the window compounds to its last NAV and is held at 0 % afterwards, never dropped.
    </p>
    <div class="card text-sm">
      <h3 class="font-semibold">{r.query_name} — k = {r.k}, h = {r.h}, returns</h3>
      <dl class="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-2 tabular-nums">
        <div><dt class="text-xs text-muted">lookalike-windows with a fund at entry n / N_eff</dt><dd><strong>{r.n} / {r.n_eff}</strong> of {r.per_T.reduce((a, t) => a + t.members.length, 0)}</dd></div>
        <div><dt class="text-xs text-muted">status counts</dt><dd>{Object.entries(r.status_counts).map(([k, v]) => `${STATUS_LABEL[k] ?? k} ${v}`).join(' · ')}</dd></div>
        <div><dt class="text-xs text-muted">mean excess vs VT</dt><dd>{pp(r.mean_excess_vs_vt, 2)} pp/yr {r.ci_degenerate ? '(a single fund: no interval)' : ci(r.ci_headline)}</dd></div>
        <div><dt class="text-xs text-muted">vs the equal-weight investable basket · SPY · EFA · EEM</dt><dd>{pp(r.vs.ew?.mean_excess, 2)} · {pp(r.vs.spy?.mean_excess, 2)} · {pp(r.vs.efa?.mean_excess, 2)} · {pp(r.vs.eem?.mean_excess, 2)} pp/yr</dd></div>
        <div><dt class="text-xs text-muted">null N1 (random investable countries), one-sided p</dt><dd>{p(r.nulls.N1_investable.p)} (null mean {pp(r.nulls.N1_investable.null_mean, 2)} pp/yr)</dd></div>
        <div><dt class="text-xs text-muted">vs N4 momentum (investable), p</dt><dd>{p(r.nulls.N4_investable.p)}</dd></div>
      </dl>
      <div class="mt-3 overflow-x-auto">
        <table class="w-full text-xs">
          <caption class="text-left text-muted">Per T: VT (or proxy) and the equal-weight basket of every fund that existed at entry, CAGR %/yr; who had a fund (fund and VT over the identical window, same unit)</caption>
          <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">T</th><th class="py-1 pr-2 font-medium">VT / proxy</th><th class="py-1 pr-2 font-medium">EW basket (n)</th><th class="py-1 pr-2 font-medium">investable candidates</th><th class="py-1 font-medium">lookalikes</th></tr></thead>
          <tbody>
            {#each r.per_T as t (t.T)}
              <tr class="border-t border-border align-top tabular-nums">
                <td class="py-1 pr-2">{t.T}</td>
                <td class="py-1 pr-2">{pp(t.r_vt_cagr)} %/yr <span class="text-muted">({t.benchmark}; {pp(t.r_vt, 2)} pp/yr log)</span></td>
                <td class="py-1 pr-2">{pp(t.r_ew_cagr)} %/yr ({t.ew_n})</td>
                <td class="py-1 pr-2">{t.investable_candidates} of {t.n_candidates}</td>
                <td class="py-1">{#each t.members as pk, i (pk.iso3)}{#if i}, {/if}{nameOf(pk.iso3)}{#if pk.ticker} ({pk.ticker} {pp(pk.r_cagr)} vs VT {pp(pk.r_vt_cagr)} %/yr{pk.status === 'liquidated_in_window' ? `, last trading day ${pk.last_trading_day ?? pk.delisted_universe ?? 'n/a'}${pk.delisted_universe && pk.last_trading_day && pk.delisted_universe !== pk.last_trading_day ? ` (universe file said ${pk.delisted_universe})` : ''}` : ''}){:else} ({STATUS_LABEL[pk.status] ?? pk.status}){/if}{/each}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if r.ladder_incomplete.length}
        <p class="mt-2 text-xs text-muted">NAV-ladder gaps held at 0 %, never dropped: {r.ladder_incomplete.map((x) => `${x.iso3} ${x.T} ${x.ticker} [${x.spans}]`).join('; ')}.</p>
      {/if}
      <p class="mt-2 text-xs text-fg-2">Out-of-sample block T ≥ 2010 (VT itself, no proxy): n = {r.oos_block_T_ge_2010.n}, mean excess vs VT {pp(r.oos_block_T_ge_2010.mean_excess_vs_vt, 2)} pp/yr, same sign as pooled: {r.oos_block_T_ge_2010.same_sign_as_pooled ? 'yes' : 'no'}.</p>
    </div>
    <div class="text-sm">
      <h3 class="font-semibold">The equal-weight basket of every fund that existed, beside VT{#if ewBeatVt === false}{' '}— it did not beat VT either (prediction P3b met){:else if ewBeatVt === true}{' '}— prediction P3b not met{/if}</h3>
      <div class="mt-1 overflow-x-auto">
        <table class="w-full text-xs">
          <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">T</th><th class="py-1 pr-2 font-medium">window</th><th class="py-1 pr-2 font-medium">VT / proxy</th><th class="py-1 pr-2 font-medium">EW basket (n)</th><th class="py-1 pr-2 font-medium">SPY · EFA · EEM</th><th class="py-1 font-medium">proxy legs</th></tr></thead>
          <tbody>
            {#each bt.benchmarks as b (b.T)}
              <tr class="border-t border-border align-top tabular-nums">
                <td class="py-1 pr-2">{b.T}</td><td class="py-1 pr-2">{b.entry} → {b.exit}</td><td class="py-1 pr-2">{pp(b.r_vt_cagr)} %/yr <span class="text-muted">({b.benchmark})</span></td>
                <td class="py-1 pr-2">{pp(b.ew.r_cagr)} %/yr ({b.ew.n}{b.ew.incomplete.length ? `; ${b.ew.incomplete.join(', ')} incomplete` : ''})</td>
                <td class="py-1 pr-2">{pp(b.spy_cagr)} · {pp(b.efa_cagr)} · {pp(b.eem_cagr)} %/yr</td>
                <td class="py-1 text-muted">{b.legs.map((l) => `${l.from}→${l.to}: ${Object.entries(l.weights).map(([k, w]) => `${k} ${Math.round(100 * w)} %`).join(', ')}`).join(' · ')}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if bt.ew_minus_vt}
        <p class="mt-1 text-xs text-fg-2">EW basket minus VT, log pp/yr: {Object.entries(bt.ew_minus_vt).map(([T, v]) => `T = ${T}: ${pp(v, 2)}`).join(' · ')} (prediction P3b, {bt.predictions.P3b?.met ? 'met' : 'not met'}).</p>
      {/if}
    </div>
    <div class="text-sm">
      <h3 class="font-semibold">The only market sentence the decision allows</h3>
      <ul class="mt-1 list-disc space-y-1 pl-5 text-fg-2">
        {#each dec.rendered['L0.vs_vt'] ?? [] as s, i (i)}<li>{s}</li>{/each}
        {#each dec.rendered['L0.investability'] ?? [] as s, i (i)}
          {@const n = noteFor(s)}
          <li>{s}{#if n}<span class="text-muted">{' '}— the frozen universe file's date; SEC filings put {n.ticker}'s last trading day at {n.last_trading_day}, the date the window arithmetic and the badge use (deviation recorded in RESULTS §10).</span>{/if}</li>
        {/each}
      </ul>
      <p class="mt-1 text-xs text-muted">Units: {ev.units_note}</p>
    </div>
  </section>

  <!-- ============================================================ decision -->
  <section id="decision" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">Decision levels and allowed language</h2>
    <p class="text-sm text-fg-2">
      Three pre-registered levels gate what the interface may claim. Each requires every listed condition; a growth or market claim renders only if its level was granted, through the templates of <code>evals/econ/ui_sentences.yaml</code> (<code>lib/econ/lang.ts</code> refuses every other id). Table cells and chips print numbers with their window and VT beside them without a template; every string on the site is scanned against the deny list.
    </p>
    <div class="grid gap-3 sm:grid-cols-3 text-sm">
      {#each Object.entries(dec.levels) as [id, lv] (id)}
        <div class="card">
          <div class="flex items-baseline gap-2"><span class="font-mono">{id}</span><span class="chip">{lv.granted ? 'granted' : 'not granted'}</span></div>
          <div class="mt-1 font-medium">{lv.name}</div>
          {#if lv.requires.length}<div class="mt-1 text-xs text-muted">requires {lv.requires.join(', ')}</div>{:else}<div class="mt-1 text-xs text-muted">always allowed: past tense, numeric, N_eff shown, null result shown, VT beside every market number</div>{/if}
          {#if lv.failed.length}<div class="mt-1 text-xs text-fg-2">failed: {lv.failed.join(', ')}</div>{/if}
          {#if lv.unavailable.length}<div class="mt-1 text-xs text-fg-2">unavailable: {lv.unavailable.join(', ')}</div>{/if}
          {#if lv.note}<div class="mt-1 text-xs text-fg-2">{lv.note}</div>{/if}
        </div>
      {/each}
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <caption class="text-left text-muted">Every condition, observed</caption>
        <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">condition</th><th class="py-1 pr-2 font-medium">observed</th><th class="py-1 pr-2 font-medium">holds</th><th class="py-1 font-medium">read from</th></tr></thead>
        <tbody>
          {#each conditionRows as [k, c] (k)}
            <tr class="border-t border-border align-top"><td class="py-1 pr-2 font-mono">{k}</td><td class="py-1 pr-2 tabular-nums">{c.available ? fmtValue(c.value) : 'n/a'}</td><td class="py-1 pr-2">{c.available ? (c.ok ? 'yes' : 'no') : 'n/a'}</td><td class="py-1 text-muted">{c.detail}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-sm text-fg-2">Allowed sentence ids: <code class="text-xs">{dec.allowed_sentence_ids.join(', ')}</code>. No other growth or market claim can be composed by the interface; the numbers it prints outside these sentences are past figures with their window, VT over the identical window beside every market one.</p>
  </section>

  <!-- ============================================================ investability -->
  <section id="investability" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">Investability</h2>
    <p class="text-sm text-fg-2">
      The frozen universe of {singles.length} US-listed single-country funds and {benchmarks.length} benchmarks, curated before any price was fetched (as of {ev.investability.as_of}); liveness comes only from the issuer's own status and a fresh bar, never from a quote. Liquidated funds carry the issuer's last trading day and notice; dates the frozen file got wrong were corrected from SEC filings and are listed as deviations.
    </p>
    <div class="card text-sm">
      <h3 class="font-semibold">Liquidated and liquidating</h3>
      <ul class="mt-1 space-y-1 text-xs">
        {#each liquidated as f (f.ticker)}
          <li class="tabular-nums">
            <span class="font-mono">{f.ticker}</span> {f.name} ({f.issuer}) — {f.status}; last trading day {f.last_trading_day ?? f.delisted_universe ?? 'n/a'}{f.liquidation_date ? `, liquidation ${f.liquidation_date}` : ''}{f.delisted_universe && f.last_trading_day && f.delisted_universe !== f.last_trading_day ? ` (universe file said ${f.delisted_universe})` : ''}
            {#if f.status_url}· <a class="underline" href={f.status_url} rel="noopener" target="_blank">issuer notice</a>{/if}
            {#if f.liquidation_source_url}· <a class="underline" href={f.liquidation_source_url} rel="noopener" target="_blank">liquidation source</a>{/if}
          </li>
        {/each}
      </ul>
      {#each ev.links.find((l) => l.id === 'investability')?.findings.filter((f) => /MSCI deleted/.test(f.claim)) ?? [] as f, i (i)}
        <p class="mt-2 text-xs text-fg-2">{f.claim} {#if f.url}<a class="underline" href={f.url} rel="noopener" target="_blank">MSCI announcement</a>{/if}</p>
      {/each}
    </div>
    <details class="card p-0 text-sm">
      <summary class="cursor-pointer px-4 py-2 font-semibold">All {ev.investability.n} instruments</summary>
      <div class="overflow-x-auto border-t border-border px-4 py-2">
        <table class="w-full text-xs">
          <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">ticker</th><th class="py-1 pr-2 font-medium">country</th><th class="py-1 pr-2 font-medium">issuer</th><th class="py-1 pr-2 font-medium">inception</th><th class="py-1 pr-2 font-medium">status</th><th class="py-1 pr-2 font-medium">last trading day</th><th class="py-1 font-medium">MSCI class</th></tr></thead>
          <tbody>
            {#each ev.investability.rows as f (f.ticker)}
              <tr class="border-t border-border tabular-nums">
                <td class="py-1 pr-2 font-mono">{#if f.source_url}<a class="underline decoration-dotted" href={f.source_url} rel="noopener" target="_blank">{f.ticker}</a>{:else}{f.ticker}{/if}</td>
                <td class="py-1 pr-2">{f.iso3 ? nameOf(f.iso3) : f.role}</td><td class="py-1 pr-2">{f.issuer}</td><td class="py-1 pr-2">{f.inception}{f.inception_verified === 'yes' ? '' : ' (unverified)'}</td><td class="py-1 pr-2">{f.status}</td><td class="py-1 pr-2">{f.last_trading_day ?? f.delisted_universe ?? '—'}</td><td class="py-1">{f.msci_class ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>
    {#if ev.investability.manual_deviations.length}
      <div class="text-sm">
        <h3 class="font-semibold">Deviations recorded while transcribing</h3>
        <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-fg-2">{#each ev.investability.manual_deviations as d, i (i)}<li>{d}</li>{/each}</ul>
      </div>
    {/if}
    <div class="text-sm">
      <h3 class="font-semibold">Deviations from the pre-registration (RESULTS §10)</h3>
      <ul class="mt-1 list-disc space-y-1 pl-5 text-xs text-fg-2">{#each ev.deviations as d, i (i)}<li>{d}</li>{/each}</ul>
    </div>
  </section>

  <!-- ============================================================ vintage -->
  <section id="vintage" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">Vintage caveat</h2>
    <p class="text-sm text-fg-2">
      The pyramids that select lookalikes as of T are WPP 2024 back-series — today's estimate of what the age structure <em>was</em>, not what was known at T. The selection is hindsight-free with respect to the outcome, not with respect to the demographic input.
      Re-running the selection on the UN's archived revisions ({ev.vintage.revision_rule}) gave the overlaps below; the pre-registered expectation ({ev.vintage.expectation}) held in {ev.vintage.cells_met} of {ev.vintage.cells} cells and Query B met it at every T: {ev.vintage.B_k10_met_at_every_T ? 'yes' : 'no'}. Small revisions reshuffle a k = 10 set{#if ev.vintage.spearman}; the rank ordering of the selection statistic stays closer (Spearman ρ {num(ev.vintage.spearman.min, 2)}–{num(ev.vintage.spearman.max, 2)} over the {ev.vintage.spearman.n} query × T cells){/if}. Self-check on the WPP 2024 vectors reproduced the recorded sets: {ev.vintage.self_check_passed ? 'yes' : 'no'}.
    </p>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <caption class="text-left text-muted">Jaccard overlap of the WPP 2024 and archive lookalike sets, k = 10</caption>
        <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">T</th><th class="py-1 pr-2 font-medium">archive</th><th class="py-1 pr-2 font-medium">rule</th><th class="py-1 pr-2 font-medium">common</th><th class="py-1 pr-2 font-medium">Jaccard</th><th class="py-1 font-medium">≥ {ev.vintage.threshold}</th></tr></thead>
        <tbody>
          {#each [...vintageB, ...vintageA] as v (v.T + v.query)}
            <tr class="border-t border-border tabular-nums"><td class="py-1 pr-2">{v.T}</td><td class="py-1 pr-2">WPP {v.revision}</td><td class="py-1 pr-2">{v.query === 'B' ? 'B (primary)' : v.query}</td><td class="py-1 pr-2">{v.common} / {v.wpp2024.length}</td><td class="py-1 pr-2">{num(v.jaccard, 2)}</td><td class="py-1">{v.jaccard >= ev.vintage.threshold ? 'met' : 'not met'}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <ul class="list-disc space-y-1 pl-5 text-xs text-fg-2">{#each ev.vintage.caveats as c, i (i)}<li>{c}</li>{/each}</ul>
    <p class="text-xs text-fg-2">The GDP series behind the prototypes are likewise revised back-series (PWT 11.0 / Maddison 2023), and every "as of T" quantity uses the GDP of calendar year T, which was not published on the entry date — roughly one year of look-ahead a real-time selector would not have had.</p>
  </section>

  <!-- ============================================================ sources -->
  <section id="sources" class="mt-10 space-y-4">
    <h2 class="text-xl font-semibold tracking-tight">Sources & licences</h2>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <caption class="text-left text-muted">Data vintages of the backtest run (RESULTS §1){ev.data_vintages_note ? ` — ${ev.data_vintages_note}` : ''}</caption>
        <thead class="text-left text-muted"><tr><th class="py-1 pr-2 font-medium">source</th><th class="py-1 pr-2 font-medium">vintage</th><th class="py-1 pr-2 font-medium">licence</th><th class="py-1 pr-2 font-medium">shipped</th><th class="py-1 font-medium">fetched</th></tr></thead>
        <tbody>
          {#each ev.data_vintages as v (v.source)}
            <tr class="border-t border-border"><td class="py-1 pr-2">{v.source}</td><td class="py-1 pr-2">{v.vintage}</td><td class="py-1 pr-2">{v.licence}</td><td class="py-1 pr-2">{v.shipped}</td><td class="py-1 tabular-nums">{v.fetched}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <ul class="space-y-1 text-sm">
      {#each ev.licences.shipped as l (l.name)}
        <li><a class="underline" href={l.url} rel="noopener" target="_blank">{l.name}</a> — {l.cite} · {l.licence} · shipped</li>
      {/each}
      {#each ev.licences.cited_only as l (l.name)}
        <li>{l.name} — {l.terms}</li>
      {/each}
    </ul>
    <p class="text-sm text-fg-2">
      GDP per capita on the site is Maddison 2011 international $, extended past 2022 with WDI / PWT growth; 10-year growth is the mean of annual PWT real GDP growth (WDI for 2024); income groups are the World Bank's historical classification by fiscal year; the dividend stage applies the Ahmed–Cruz / GMR 2015 typology to every year. Fund statistics are derived from daily adjusted closes and issuer NAV returns (a CAGR, a drawdown, a date) — no price series is shipped. Pyramids: {meta.attribution[0]}
    </p>
    <details class="text-xs">
      <summary class="cursor-pointer text-muted">NOTICE (evals/econ)</summary>
      <pre class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-surface p-3">{ev.notice}</pre>
    </details>
  </section>

  <!-- ============================================================ never -->
  <section id="never" class="mt-10 space-y-3">
    <h2 class="text-xl font-semibold tracking-tight">What this site never does</h2>
    <ul class="list-disc space-y-1 pl-5 text-sm text-fg-2">{#each ev.never_does as n, i (i)}<li>{n}</li>{/each}</ul>
    <p class="text-sm"><a class="underline" href={href({ kind: 'static', page: 'about' })}>← About: how similarity works</a></p>
  </section>
</article>
