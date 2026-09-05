<script lang="ts">
  // Cohort outcomes (PLAN §7, lens on, cross-year modes): every pyramid that resembled the focal one in its own year →
  // a dot strip of the following h-year GDP/cap CAGR with the focal country highlighted, median / IQR, the focal rank,
  // n printed; an index-return strip only for members that had a fund at their year, each beside VT over the identical
  // window, captioned "n = k with a fund; too few to conclude" below 10. Never a score; the list order is the shape
  // rank passed in, never return — the focal's rank among the cohort's growth rates is a statistic, not a sort.
  import type { EconData } from '../../econ.ts';
  import { cohortOutcomes, fmtPctYr, fundCaption, type Match } from '../../econ/outcomes.ts';
  import EvidenceLink from './EvidenceLink.svelte';

  interface Props {
    econ: EconData;
    matches: Match[]; // in shape-rank order
    focal: Match;
    focalName: string;
    nameOf: (iso3: string) => string;
    h?: number;
  }
  let { econ, matches, focal, focalName, nameOf, h = 20 }: Props = $props();

  const o = $derived(cohortOutcomes(econ, matches, focal, { h }));
  const W = 320;
  const PAD = 10;
  const domain = $derived.by(() => {
    const vals = [...o.points.map((p) => p.pctPerYear), ...(o.focal ? [o.focal.pctPerYear] : [])];
    if (!vals.length) return { lo: -5, hi: 10 };
    const lo = Math.min(-2, Math.floor(Math.min(...vals)) - 1);
    const hi = Math.max(5, Math.ceil(Math.max(...vals)) + 1);
    return { lo, hi };
  });
  const x = (v: number) => PAD + ((v - domain.lo) / (domain.hi - domain.lo)) * (W - 2 * PAD);
  const ticks = $derived.by(() => {
    const out: number[] = [];
    const step = domain.hi - domain.lo > 20 ? 5 : domain.hi - domain.lo > 10 ? 2 : 1;
    for (let v = Math.ceil(domain.lo / step) * step; v <= domain.hi; v += step) out.push(v);
    return out;
  });
</script>

<section class="card mt-4 p-3" aria-labelledby="cohort-h">
  <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h3 id="cohort-h" class="text-sm font-semibold tracking-tight">
      What happened next to the lookalikes
      <span class="ml-1 text-xs font-normal text-muted">GDP per capita over the {h} years after each member's own year · n = {o.n}{o.nNoWindow ? ` (${o.nNoWindow} without a full window yet)` : ''}</span>
    </h3>
    <EvidenceLink anchor="backtest" title="This site's pre-registered backtest ran the same question over 1990–2015 cohorts; its numbers and null results" />
  </div>

  {#if o.n === 0}
    <p class="mt-2 text-xs text-fg-2">No member has {o.minYears}+ years of GDP data after its year — nothing to report.</p>
  {:else}
    <svg viewBox="0 0 {W} 64" class="mt-2 w-full max-w-md" role="img" aria-label="Dot strip of {o.n} cohort growth rates, median {fmtPctYr(o.median)}{o.focal ? `, ${focalName} ${fmtPctYr(o.focal.pctPerYear)}` : ''}">
      <line x1={PAD} x2={W - PAD} y1="32" y2="32" stroke="var(--axis)" />
      {#each ticks as t (t)}
        <line x1={x(t)} x2={x(t)} y1="29" y2="35" stroke="var(--axis)" />
        <text x={x(t)} y="48" font-size="8" text-anchor="middle" fill="var(--muted)">{t > 0 ? '+' : ''}{t}</text>
      {/each}
      <text x={W - PAD} y="60" font-size="8" text-anchor="end" fill="var(--muted)">%/yr</text>
      {#if o.q1 !== null && o.q3 !== null}
        <rect x={x(o.q1)} y="26" width={Math.max(1, x(o.q3) - x(o.q1))} height="12" fill="var(--accent)" opacity="0.15" />
      {/if}
      {#if o.median !== null}<line x1={x(o.median)} x2={x(o.median)} y1="22" y2="42" stroke="var(--accent)" stroke-width="2" />{/if}
      {#each o.points as p (p.iso3 + p.year)}
        <circle cx={x(p.pctPerYear)} cy="32" r="4" fill="var(--fg-2)" opacity="0.6"><title>{nameOf(p.iso3)} {p.year}→{p.toYear}: {fmtPctYr(p.pctPerYear)}{p.clipped ? ' (clipped)' : ''}</title></circle>
      {/each}
      {#if o.focal}
        <circle cx={x(o.focal.pctPerYear)} cy="32" r="5.5" fill="var(--u15)" stroke="var(--bg)" stroke-width="1.5"><title>{focalName} {o.focal.year}→{o.focal.toYear}: {fmtPctYr(o.focal.pctPerYear)}</title></circle>
      {/if}
    </svg>
    <p class="mt-1 text-xs text-fg-2 tabular-nums">
      median <span class="text-fg">{fmtPctYr(o.median)}</span> · IQR {fmtPctYr(o.q1)} to {fmtPctYr(o.q3)}
      {#if o.focal}
        · <span class="text-fg">{focalName} {o.focal.year}→{o.focal.toYear}: {fmtPctYr(o.focal.pctPerYear)}</span> (rank {o.focalRank} of {o.n + 1}, 1 = highest growth)
      {:else}
        · {focalName} {focal.year}: no {o.minYears}+-year window yet
      {/if}
    </p>
    <ul class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted tabular-nums">
      {#each o.points as p (p.iso3 + p.year)}
        <li>#{p.rank} {nameOf(p.iso3)} {p.year}: {fmtPctYr(p.pctPerYear)}{p.clipped ? ` (→ ${p.toYear})` : ''}</li>
      {/each}
    </ul>
  {/if}

  <div class="mt-3 border-t border-border pt-2">
    <div class="text-xs text-muted">Index returns where a US-listed single-country fund existed at the member's year <span class="text-fg-2">— {fundCaption(o)}</span><EvidenceLink anchor="returns" /></div>
    {#if o.nWithFund > 0}
      <ul class="mt-1 space-y-0.5 text-xs tabular-nums">
        {#each o.funds as f (f.iso3 + f.year)}
          <li>
            <span class="text-fg-2">#{f.rank} {nameOf(f.iso3)} {f.year}</span>
            <span class="font-mono">{f.ticker}</span>
            {f.window.y1}–{f.window.y2}: <span class="text-fg">{fmtPctYr(f.window.r)}</span>
            · VT over the same window: <span class="text-fg">{fmtPctYr(f.window.rVt)}</span>
            {#if f.window.vt === 'vt_proxy'}<span class="text-muted">(VT proxy before 2008-06-24)</span>{:else if f.window.vt === 'none'}<span class="text-muted">(VT did not exist for this window)</span>{/if}
            {#if f.status !== 'live'}<span class="chip ml-1">{f.status}</span>{/if}
            {#if f.window.label === 'since_inception'}<span class="text-muted">· the fund's own window</span>{/if}
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</section>
