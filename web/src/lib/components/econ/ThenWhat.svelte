<script lang="ts">
  // "Then what happened" (PLAN §7 J10, lens on): GDP/cap at y → +10/+20/+30 as multiples and %/yr with the horizon
  // length (clipped horizons say so), the working-age-share peak year from the entity shard ("dividend window"), and the
  // market row per the plan's rules — every market number beside VT over the identical window, rendered ONLY through the
  // granted L0 sentence templates (lib/econ/lang.ts). Past tense throughout; nothing here is a forecast.
  import { marketRow, thenWhat, type EconData } from '../../econ.ts';
  import { investability, vsVt } from '../../econ/lang.ts';
  import { fmtMultiple, fmtPctYr } from '../../econ/outcomes.ts';
  import { waPeak } from '../../econ/wa.ts';
  import { loadEntityShard } from '../../data.ts';
  import type { EntityShard } from '../../types.ts';
  import EvidenceLink from './EvidenceLink.svelte';
  import InstrumentBadge from './InstrumentBadge.svelte';

  interface Props {
    econ: EconData;
    iso3: string;
    year: number;
    name: string;
    /** The candidate's entity shard when loaded (for the working-age peak); null → the line is skipped. */
    shard?: EntityShard | null;
    currentYear: number;
    compact?: boolean;
  }
  let { econ, iso3, year, name, shard = null, currentYear, compact = false }: Props = $props();

  const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const tw = $derived(thenWhat(econ, iso3, year));
  // Two horizons clipped to the same last data year are one window — show it once (under the shorter label).
  const horizons = $derived(tw.horizons.filter((h, i) => i === 0 || h.toYear !== tw.horizons[i - 1].toYear));
  const row = $derived(marketRow(econ, iso3, year));
  // the working-age peak needs the candidate's own entity shard (13 KB, memoised); fetched on open when not passed
  let fetched = $state<EntityShard | null>(null);
  $effect(() => {
    if (shard || fetched?.id === iso3) return;
    let live = true;
    loadEntityShard(iso3).then((s) => live && (fetched = s), () => {});
    return () => {
      live = false;
    };
  });
  const useShard = $derived(shard && shard.id === iso3 ? shard : fetched?.id === iso3 ? fetched : null);
  const wa = $derived(useShard ? waPeak(useShard, year, currentYear) : null);
  const asOf = $derived(row.instrument?.asOf ?? econ.header.as_of ?? null);

  /** The L0 sentences for the market row (null entries are skipped). */
  const marketLines = $derived.by<string[]>(() => {
    const out: string[] = [];
    const inst = row.instrument;
    const w = row.window;
    const vt = (r: number | null, rVt: number | null, y1: number, y2: number, flag: 'vt' | 'vt_proxy' | 'none') => (inst ? vsVt({ ticker: inst.ticker, y1, y2, r, r_vt: rVt }, flag) : null);
    switch (row.kind) {
      case 'existed':
        if (inst && w) out.push(vt(w.r, w.rVt, w.y1, w.y2, w.vt) ?? '');
        break;
      case 'later':
        out.push(investability('none_at_T', { T: year }) ?? '');
        if (inst && w) out.push(vt(w.r, w.rVt, w.y1, w.y2, w.vt) ?? '');
        break;
      case 'liquidated':
        if (inst) out.push(investability('liquidated', { ticker: inst.ticker, delisted: inst.delisted ?? inst.liquidationDate ?? 'n/a' }) ?? '');
        if (inst && w) out.push(vt(w.r, w.rVt, w.y1, w.y2, w.vt) ?? '');
        break;
      case 'none':
        break; // the InstrumentBadge below carries the "no US-listed single-country fund" sentence (+ MSCI class)
    }
    return out.filter((s) => s.length > 0);
  });
  const windowNote = $derived.by(() => {
    const w = row.window;
    if (!w || !row.instrument) return null;
    const bits: string[] = [];
    if (w.label === 'since_inception') bits.push(`the fund's own window since inception, not ${year}→${year + 10}`);
    if (w.label === '10y' && w.y1 !== year) bits.push(`the backtest's ${w.y1}–${w.y2} window, not ${year}→${year + 10}`);
    if (row.kind === 'liquidated') bits.push('return to the last full year before liquidation');
    if (w.incomplete) bits.push(`NAV ladder gap held at 0 %: ${w.incomplete}`);
    if (w.maxDd !== null) bits.push(`maximum drawdown ${w.maxDd.toFixed(0)} %`);
    if (asOf) bits.push(`derived from daily adjusted closes / issuer NAV returns, as of ${asOf}`);
    return bits.join(' · ');
  });
</script>

<div class="text-xs text-fg-2 {compact ? '' : 'space-y-2'}">
  <div>
    <div class="flex flex-wrap items-baseline gap-x-2">
      <span class="text-muted">GDP per capita in {year}</span>
      {#if tw.gdppcThen !== null}<span class="tabular-nums text-fg">${money.format(tw.gdppcThen)}</span><span class="text-muted">Maddison 2011$</span>{:else}<span>n/a</span>{/if}
      <EvidenceLink anchor="backtest" title="What GDP per capita did afterwards, from Maddison 2023 / PWT 11.0 / WDI; this site's backtest on the same series" />
    </div>
    {#if tw.horizons.length}
      <ul class="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 tabular-nums">
        {#each horizons as h (h.h)}
          <li title="{year} → {h.toYear}{h.clipped ? ' (clipped to the last data year)' : ''}">
            <span class="text-muted">+{h.h} y</span>
            {#if h.clipped}<span class="text-muted"> (→ {h.toYear}, {h.years} y)</span>{/if}
            <span class="text-fg"> {fmtMultiple(h.multiple)}</span>
            <span> · {fmtPctYr(h.pctPerYear)}</span>
          </li>
        {/each}
      </ul>
    {:else if tw.gdppcThen !== null}
      <p class="mt-0.5 text-muted">fewer than 5 years of data after {year} — nothing to report yet</p>
    {/if}
    {#if tw.unavailable.length && tw.horizons.length}
      <p class="mt-0.5 text-muted">+{tw.unavailable.join(' / +')} y: not reached by {tw.lastYear}</p>
    {/if}
  </div>

  {#if wa}
    <p>
      <span class="text-muted">Working-age share (15–64)</span>
      <span class="tabular-nums text-fg">{(100 * wa.shareAt).toFixed(1)} %</span> in {year};
      peak <span class="tabular-nums text-fg">{(100 * wa.share).toFixed(1)} %</span> in {wa.year}{wa.projected ? ' (projected)' : ''}
      <span class="text-muted">— the dividend window is the run-up to that peak (WPP 2024)</span>
    </p>
  {/if}

  <div>
    <div class="text-muted">Market <span class="normal-case">(US-listed single-country fund, if any; every figure beside VT over the identical window)</span><EvidenceLink anchor="returns" title="The returns row of this site's backtest, the investability table and the VT / VT-proxy rule" /></div>
    {#each marketLines as line, i (i)}
      <p class="mt-0.5 text-fg">{line}</p>
    {/each}
    {#if windowNote}<p class="mt-0.5 text-muted">{windowNote}</p>{/if}
    <div class="mt-1"><InstrumentBadge {econ} {iso3} detail={!compact} /></div>
  </div>
  <p class="text-[10px] text-muted">{name}: what the published series say happened after {year}. No forecast is made from it.</p>
</div>
