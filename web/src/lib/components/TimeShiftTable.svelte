<script lang="ts">
  // Time-shift panel (PLAN §6, J5): "{Name} {year} across time" — for every other country in scope the year
  // that best matches the focal pyramid, Δy, d and the band against the `best` null. Collapsed <details>;
  // opening fetches the corpus (tier 3) once. First 10 rows + "show all"; a best year sitting on the era edge
  // reads "not reached by {year}" instead of posing as a match. Rows link to the compare page
  // /compare/{focal}/{year}/{c}/{y*}?from=best (M3, PLAN §7 J5) — the pair IS a best-year match, so the compare
  // page bands it against the same `best` null and its "B → best year" button starts lit.
  // M5 (lens on): three econ columns — GDP/cap then · next 20 y · index vs VT — computed through `econLib` (the
  // dynamically loaded lib/econ.ts) so this first-paint component carries no static import of the decoder.
  import type { TimeShiftRow } from '../engine.ts';
  import type { CorpusStatus, EconLib } from '../state.svelte.ts';
  import type { EconData } from '../econ.ts';
  import { fmtMultiple, fmtPctYr } from '../econ/fmt.ts';
  import { byId, flagEmoji } from '../entities.ts';
  import { compareQuery, type Metric, type Sex } from '../router.ts';
  import { href } from '../url.ts';
  import { BAND_LABEL, dyLabel } from '../restate.ts';

  interface Props {
    rows: TimeShiftRow[] | null;
    open: boolean;
    ontoggle: (open: boolean) => void;
    status: CorpusStatus;
    error: string | null;
    focal: { id: string; name: string; year: number; metric?: Metric; sex?: Sex };
    eraEdge: number; // upper edge of the allowed years (2026 for observed, 2100 for all)
    corpusBytes: number;
    currentYear: number;
    econ?: EconData | null;
    econLib?: EconLib | null;
    lens?: boolean;
  }
  let { rows, open, ontoggle, status, error, focal, eraEdge, corpusBytes, currentYear, econ = null, econLib = null, lens = false }: Props = $props();
  const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const econCols = $derived(lens && !!econ && !!econLib);
  interface EconCells {
    gdp: string;
    next: string;
    nextTitle: string;
    index: string;
    indexTitle: string;
  }
  function econCells(r: TimeShiftRow): EconCells | null {
    if (!econ || !econLib) return null;
    const tw = econLib.thenWhat(econ, r.id, r.bestYear, [20]);
    const h = tw.horizons[0];
    const mr = econLib.marketRow(econ, r.id, r.bestYear);
    const w = mr.window;
    const hasFund = (mr.kind === 'existed' || mr.kind === 'liquidated') && !!w && !!mr.instrument;
    return {
      gdp: tw.gdppcThen === null ? '—' : `$${money.format(tw.gdppcThen)}`,
      next: h ? `${fmtMultiple(h.multiple)} · ${fmtPctYr(h.pctPerYear)}${h.clipped ? ` (→ ${h.toYear})` : ''}` : tw.gdppcThen === null ? '—' : 'not reached',
      nextTitle: h ? `GDP per capita ${r.bestYear} → ${h.toYear} (${h.years} y)${h.clipped ? ', clipped to the last data year' : ''}` : 'fewer than 5 years of data after this year',
      index: hasFund ? `${mr.instrument!.ticker} ${w!.y1}–${w!.y2}: ${fmtPctYr(w!.r)} · VT ${fmtPctYr(w!.rVt)}` : mr.kind === 'later' ? `no fund in ${r.bestYear}` : 'no fund',
      indexTitle: hasFund
        ? `${mr.instrument!.ticker} total return over ${w!.y1}–${w!.y2} beside VT over the identical window${w!.vt === 'vt_proxy' ? ' (VT proxy before 2008-06-24)' : w!.vt === 'none' ? ' (VT did not exist for this window)' : ''}${w!.label === 'since_inception' ? ' — the fund\'s own window since inception' : ''}${mr.kind === 'liquidated' ? ` — ${mr.instrument!.status} ${mr.note ?? ''}` : ''}`
        : mr.kind === 'later'
          ? `No US-listed single-country fund existed in ${r.bestYear}; ${mr.instrument?.ticker ?? 'one'} since ${mr.instrument?.inceptionYear ?? ''}`
          : 'No US-listed single-country fund exists for this country',
    };
  }
  const link = (r: TimeShiftRow) => href(compareQuery(focal.id, focal.year, r.id, r.bestYear, { from: 'best', metric: focal.metric, sex: focal.sex, era: eraEdge >= 2100 ? 'all' : 'obs' }, currentYear));

  let showAll = $state(false);
  const visible = $derived(rows ? (showAll ? rows : rows.slice(0, 10)) : []);
  const mb = $derived((corpusBytes / 1e6).toFixed(1));

  function edgeNote(r: TimeShiftRow): string | null {
    if (!r.boundaryHit || r.bestYear === focal.year) return null;
    return r.bestYear >= eraEdge ? `not reached by ${r.bestYear}` : `not reached before ${r.bestYear}`;
  }
</script>

<details class="card mt-8 p-0" {open} ontoggle={(e) => ontoggle((e.currentTarget as HTMLDetailsElement).open)}>
  <summary class="cursor-pointer px-4 py-3 text-base font-semibold tracking-tight">
    {focal.name} {focal.year} across time
    <span class="ml-2 text-xs font-normal text-muted">which year of every other country looks most like this one</span>
  </summary>
  <div class="border-t border-border px-4 py-3">
    {#if status === 'error'}
      <p class="text-sm text-fg-2" role="alert">Could not load the corpus: {error}</p>
    {:else if !rows}
      <p class="text-sm text-muted" aria-busy="true">loading all years… {mb} MB</p>
    {:else if rows.length === 0}
      <p class="text-sm text-fg-2">No other country in scope.</p>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-xs text-muted">
            <tr>
              <th scope="col" class="py-1 pr-3 font-medium">Country</th><th scope="col" class="py-1 pr-3 font-medium">Best year</th><th scope="col" class="py-1 pr-3 font-medium">Δy</th><th scope="col" class="py-1 pr-3 font-medium">d</th><th scope="col" class="py-1 pr-3 font-medium">Band</th>
              {#if econCols}
                <th scope="col" class="py-1 pr-3 font-medium" title="GDP per capita in the best year (Maddison 2011$)">GDP/cap then</th>
                <th scope="col" class="py-1 pr-3 font-medium" title="GDP per capita over the 20 years after the best year: multiple and %/yr (past figures)">next 20 y</th>
                <th scope="col" class="py-1 font-medium" title="US-listed single-country fund total return beside VT over the identical window; sortable by d / Δy only">index vs VT</th>
              {/if}
            </tr>
          </thead>
          <tbody>
            {#each visible as r (r.id)}
              {@const e = byId(r.id)}
              {@const note = edgeNote(r)}
              <tr class="border-t border-border">
                <td class="py-1 pr-3"><span class="inline-block w-5" aria-hidden="true">{e ? flagEmoji(e) : ''}</span><a class="hover:underline" href={link(r)} title="Compare {focal.name} {focal.year} with {e?.short_name ?? r.id} {r.bestYear} (overlay)">{e?.short_name ?? r.id}</a></td>
                <td class="py-1 pr-3 tabular-nums">{#if note}<span class="text-muted" title="the best match sits on the edge of the allowed years — the true best may lie beyond">{note}</span>{:else}{r.bestYear}{/if}</td>
                <td class="py-1 pr-3 tabular-nums text-fg-2">{r.dy === 0 ? '±0 y' : dyLabel(r.dy).slice(1, -1)}</td>
                <td class="py-1 pr-3 tabular-nums">{r.d.toFixed(3)}</td>
                <td class="py-1 pr-3"><span class="chip">{BAND_LABEL[r.band]}</span></td>
                {#if econCols}
                  {@const c = econCells(r)}
                  {#if c}
                    <td class="py-1 pr-3 tabular-nums text-fg-2">{c.gdp}</td>
                    <td class="py-1 pr-3 tabular-nums text-fg-2" title={c.nextTitle}>{c.next}</td>
                    <td class="py-1 text-xs tabular-nums text-fg-2" title={c.indexTitle}>{c.index}</td>
                  {/if}
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if econCols}
        <p class="mt-2 text-[11px] text-muted">Econ columns: past figures from Maddison 2023 / PWT 11.0 / WDI and derived fund statistics; every index number stands beside VT over the identical window. Rows stay ordered by d.</p>
      {/if}
      {#if rows.length > 10}
        <button type="button" class="btn mt-2" onclick={() => (showAll = !showAll)} aria-expanded={showAll}>
          {showAll ? 'show first 10' : `show all ${rows.length}`}
        </button>
      {/if}
    {/if}
  </div>
</details>
