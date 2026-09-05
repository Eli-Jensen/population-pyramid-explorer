<script lang="ts">
  // Econ context strip (PLAN §7 tier 1, always on): GDP/cap with its year and source label, 10-year real growth, the
  // income group THEN, the dividend-stage chip — every number with an "evidence" link. With the lens on, the
  // investability badge + mobility flag join it. Skeleton while the econ file loads; explicit "no GDP series" state.
  import { gdppc, growth10, hasEcon, income, incomeNote, stage, tfr, type EconData } from '../../econ.ts';
  import { fmtPctYr } from '../../econ/outcomes.ts';
  import type { EconStatus } from '../../state.svelte.ts';
  import EvidenceLink from './EvidenceLink.svelte';
  import InstrumentBadge from './InstrumentBadge.svelte';

  interface Props {
    econ: EconData | null;
    status: EconStatus;
    error?: string | null;
    iso3: string;
    year: number;
    lens: boolean;
    isAggregate: boolean;
  }
  let { econ, status, error = null, iso3, year, lens, isAggregate }: Props = $props();

  const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  /** Econ series stop at the file's last year (2024): a later query year reads the last available value, labelled. */
  const yEcon = $derived(econ ? Math.min(year, econ.yearMax) : year);
  const has = $derived(!!econ && !isAggregate && hasEcon(econ, iso3));
  const g = $derived(econ && has ? gdppc(econ, iso3, yEcon) : null);
  /** The latest year ≤ yEcon with a GDP value (for the label when the exact year is missing). */
  const gYear = $derived.by(() => {
    if (!econ || !has) return null;
    for (let y = yEcon; y >= econ.yearMin; y--) if (gdppc(econ, iso3, y) !== null) return y;
    return null;
  });
  const gShown = $derived(econ && gYear !== null ? gdppc(econ, iso3, gYear) : g);
  const gr = $derived(econ && has ? growth10(econ, iso3, yEcon) : null);
  const inc = $derived(econ && has ? income(econ, iso3, yEcon) : null);
  const st = $derived(econ && has ? stage(econ, iso3, yEcon) : null);
  const fert = $derived(econ && has ? tfr(econ, iso3, yEcon) : null);
</script>

<section class="card p-3" aria-label="Economic context">
  <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-xs font-medium uppercase tracking-wide text-muted">Economic context{#if econ && year > econ.yearMax}<span class="ml-1 normal-case">· as of {econ.yearMax}</span>{/if}</h2>
    <EvidenceLink anchor="sources" title="Sources, licences and how the series were spliced" />
  </div>
  {#if isAggregate}
    <p class="mt-1 text-xs text-fg-2">Economic series are shipped for countries only.</p>
  {:else if status === 'idle' || status === 'loading'}
    <div class="mt-2 grid grid-cols-2 gap-2" aria-busy="true" aria-label="loading the economic context">
      {#each [0, 1, 2, 3] as i (i)}<div class="h-10 animate-pulse rounded bg-surface-2"></div>{/each}
    </div>
  {:else if status === 'absent'}
    <p class="mt-1 text-xs text-fg-2">This build shipped no economic series.</p>
  {:else if status === 'error'}
    <p class="mt-1 text-xs text-fg-2" role="alert">Could not load the economic series{error ? `: ${error}` : ''}.</p>
  {:else if !has}
    <p class="mt-1 text-xs text-fg-2">no GDP series for this country (Maddison 2023, PWT 11.0 and WDI carry none)</p>
  {:else}
    <dl class="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
      <div>
        <dt class="text-xs text-muted">GDP per capita, PPP<EvidenceLink anchor="sources" title="Maddison Project Database 2023 (2011 international $), extended past 2022 with WDI / PWT growth" /></dt>
        <dd class="tabular-nums">
          {#if gShown !== null}<span class="font-semibold">${money.format(gShown)}</span> <span class="text-xs text-fg-2">{gYear !== null && gYear !== year ? `(${gYear})` : ''} Maddison 2011$</span>{:else}<span class="text-fg-2">n/a in {yEcon}</span>{/if}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-muted">10-y real GDP growth<EvidenceLink anchor="sources" title="Mean annual real GDP growth over the ten years to this year (PWT 11.0 rgdpna; WDI for 2024), log points per year" /></dt>
        <dd class="tabular-nums">{#if gr !== null}<span class="font-semibold">{fmtPctYr(gr)}</span> <span class="text-xs text-fg-2">{yEcon - 9}–{yEcon}</span>{:else}<span class="text-fg-2">n/a</span>{/if}</dd>
      </div>
      <div>
        <dt class="text-xs text-muted">Income group then<EvidenceLink anchor="sources" title="World Bank historical classification (OGHIST) for that fiscal year; n/a before 1987" /></dt>
        <dd>{#if inc}<span class="chip" title={inc.label}>{inc.label}</span>{:else}<span class="text-xs text-fg-2">{incomeNote(yEcon)}</span>{/if}</dd>
      </div>
      <div>
        <dt class="text-xs text-muted">Dividend stage<EvidenceLink anchor="links" title="Ahmed–Cruz / GMR 2015 typology applied to every year (pipeline/typology.yaml); a demographic descriptor, not a growth claim" /></dt>
        <dd>
          {#if st}<span class="chip" title={st.hint}>{st.label}</span>{:else}<span class="text-xs text-fg-2">n/a</span>{/if}
          {#if fert !== null}<span class="ml-1 text-xs text-fg-2 tabular-nums" title="total fertility rate (WPP 2024)">TFR {fert.toFixed(2)}</span>{/if}
        </dd>
      </div>
    </dl>
    {#if lens}
      <div class="mt-3 border-t border-border pt-2">
        <div class="text-xs text-muted">Investability (US-listed single-country funds, as recorded {econ?.header.as_of ?? '2026-09-04'})</div>
        <div class="mt-1"><InstrumentBadge econ={econ!} {iso3} /></div>
      </div>
    {/if}
  {/if}
</section>
