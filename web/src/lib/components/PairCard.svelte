<script lang="ts">
  // Pair card (PLAN §7 J4/J5): headline against the null, d under the pair's metric, band by |Δy| (or the `best`
  // null), the blend decomposition (bin-by-bin share vs age-shift share + the top bins, DiffBars sparkline), the
  // W1-years sentence, the IDENTICAL "similar because / differs in" sentences the country-page card shows
  // (lib/explain.ts via the engine), a feature table with both members z-scored against A's year country set,
  // swap, "B → best year" (lit while the URL says from=best) and links back to both country pages. `tools` is the
  // slot where the export menu mounts. M5 (lens on): an economic-context table — log GDP/cap, 10-y growth, income group,
  // stage, TFR — both members z-scored against the A-year country cross-section (n printed), raw values labelled with
  // their own years; computed through `econLib` (the dynamically loaded lib/econ.ts), never a static import here.
  import type { Snippet } from 'svelte';
  import type { EconData, EconField } from '../econ.ts';
  import type { EconLib, EconStatus } from '../state.svelte.ts';
  import { fmtPctYr } from '../econ/fmt.ts';
  import { evidenceHref } from '../econ/ui.ts';
  import type { Entity } from '../types.ts';
  import type { PairData } from '../compare.ts';
  import { bandChip, formatTableFeature, formatZ, pairHeadline } from '../compare.ts';
  import { countryQuery, type Metric } from '../router.ts';
  import { href } from '../url.ts';
  import { flagEmoji } from '../entities.ts';
  import { METRIC_LABEL, BAND_HINT } from '../restate.ts';
  import { binLabel } from '../explain.templates.ts';
  import DiffBars from './DiffBars.svelte';

  interface SideRef {
    entity: Entity;
    year: number | null;
  }
  interface Props {
    pair: PairData | null;
    a: SideRef & { year: number };
    b: SideRef;
    metric: Metric;
    bestLit: boolean;
    canBest: boolean; // false while yb is unresolved
    bestNote?: string | null; // e.g. "best year sits on the era edge"
    loadingText: string | null;
    error: string | null;
    onswap: () => void;
    onbest: () => void;
    tools?: Snippet;
    econ?: EconData | null;
    econLib?: EconLib | null;
    econStatus?: EconStatus;
    lens?: boolean;
  }
  let { pair, a, b, metric, bestLit, canBest, bestNote = null, loadingText, error, onswap, onbest, tools, econ = null, econLib = null, econStatus = 'idle', lens = false }: Props = $props();

  const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  interface EconRow {
    field: EconField;
    label: string;
    rawA: string;
    rawB: string;
    zA: number | null;
    zB: number | null;
    n: number;
  }
  const ECON_FIELDS: Array<[EconField, string]> = [
    ['log_gdppc', 'GDP per capita (log; shown in 2011$)'],
    ['growth10', '10-y real GDP growth'],
    ['income', 'income group then'],
    ['stage', 'dividend stage'],
    ['tfr', 'total fertility rate'],
  ];
  const econRows = $derived.by<EconRow[] | null>(() => {
    if (!lens || !econ || !econLib || b.year === null) return null;
    const e = econ;
    const L = econLib;
    if (!L.hasEcon(e, a.entity.id) && !L.hasEcon(e, b.entity.id)) return [];
    const ya = Math.min(a.year, e.yearMax);
    const yb = Math.min(b.year, e.yearMax);
    const raw = (id: string, y: number, f: EconField): string => {
      switch (f) {
        case 'log_gdppc': {
          const v = L.gdppc(e, id, y);
          return v === null ? 'n/a' : `$${money.format(v)}`;
        }
        case 'growth10':
          return fmtPctYr(L.growth10(e, id, y));
        case 'income':
          return L.income(e, id, y)?.label ?? L.incomeNote(y);
        case 'stage':
          return L.stage(e, id, y)?.label ?? 'n/a';
        case 'tfr': {
          const v = L.tfr(e, id, y);
          return v === null ? 'n/a' : v.toFixed(2);
        }
      }
    };
    return ECON_FIELDS.map(([f, label]) => {
      const cs = L.crossSection(e, ya, f);
      return { field: f, label, rawA: raw(a.entity.id, ya, f), rawB: raw(b.entity.id, yb, f), zA: L.zScore(L.econFieldValue(e, a.entity.id, ya, f), cs), zB: L.zScore(L.econFieldValue(e, b.entity.id, yb, f), cs), n: cs.n };
    });
  });
  const econYearNote = $derived(econ && (a.year > econ.yearMax || (b.year ?? 0) > econ.yearMax) ? `economic series end in ${econ.yearMax}; later years read the ${econ.yearMax} values` : null);

  const headline = $derived(pair && b.year !== null ? pairHeadline({ name: a.entity.short_name, year: a.year }, { name: b.entity.short_name, year: b.year }, pair.band, pair.bandKind) : null);
  const chip = $derived(pair ? bandChip(pair.band, pair.bandKind) : null);
  const dec = $derived(pair?.explanation.decomposition ?? null);
  const l2Share = $derived(dec && dec.d > 0 ? dec.l2Part / dec.d : 0.5);
  const highlight = $derived.by(() => {
    if (!dec) return [];
    const bins = [...dec.topBinsL2.map(([k]) => k), ...dec.topBinsW1.map(([k]) => k)];
    return dec.sex === '2' ? bins : bins.flatMap((k) => [k, k + 21]);
  });
  // the two smallest and the largest |Δz| — the rows the sentences name
  const alike = $derived(new Set(pair?.explanation.deltas.alike.map((f) => f.name) ?? []));
  const differs = $derived(new Set(pair?.explanation.deltas.differs.map((f) => f.name) ?? []));
  const decomposable = $derived(metric === 'blend' || metric === 'l2' || metric === 'w1' || metric === 'w1sex');
</script>

<section class="card" aria-labelledby="pair-h">
  <div class="flex flex-wrap items-start gap-2">
    <div class="min-w-0 flex-1">
      <h2 id="pair-h" class="text-base font-semibold tracking-tight sm:text-lg">
        {#if headline}{headline}{:else if error}The pair could not be computed{:else}{a.entity.short_name} {a.year} vs {b.entity.short_name} {b.year ?? '…'}{/if}
      </h2>
      {#if pair && chip}
        <div class="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
          <span class="chip band-{pair.band.label}" title="{chip.title} ({BAND_HINT[pair.band.label]})">{chip.text}</span>
          <span class="chip tabular-nums" title="distance under {METRIC_LABEL[metric]}">d {pair.d.toFixed(3)} · {METRIC_LABEL[metric]}</span>
          <span class="chip tabular-nums" title="B's year minus A's year">Δy {pair.dy === 0 ? '±0' : pair.dy > 0 ? `+${pair.dy}` : `−${Math.abs(pair.dy)}`} y</span>
          {#if pair.bandKind === 'best'}<span class="chip" title="banded against the best-year null (PLAN §3.4a): the distribution of min-over-years distances">best-year match</span>{/if}
        </div>
      {/if}
    </div>
    <div class="flex flex-wrap items-center gap-1.5">
      <button type="button" class="btn" onclick={onswap} disabled={b.year === null} title="Swap A and B (years too)">⇄ swap</button>
      <button
        type="button"
        class="btn best"
        aria-pressed={bestLit}
        onclick={onbest}
        disabled={!canBest && !bestLit}
        title="Move B to the year that best matches A's pyramid (searched over the allowed era, like the time-shift table)"
      >
        B → best year
      </button>
      {#if tools}{@render tools()}{/if}
    </div>
  </div>
  {#if bestNote}<p class="mt-1 text-xs text-muted">{bestNote}</p>{/if}

  {#if error}
    <p class="mt-3 text-sm text-fg-2" role="alert">{error}</p>
  {:else if !pair}
    <p class="mt-3 text-sm text-muted" aria-busy="true">{loadingText ?? 'computing the pair…'}</p>
  {:else}
    {@const ex = pair.explanation}
    <!-- decomposition -->
    <div class="mt-4 grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div class="min-w-0 text-sm">
        <h3 class="text-xs font-medium uppercase tracking-wide text-muted">Why this distance</h3>
        {#if dec}
          <div class="mt-2 flex h-3 overflow-hidden rounded-full border border-border" role="img" aria-label="{Math.round(100 * l2Share)} % bin-by-bin, {Math.round(100 * (1 - l2Share))} % age-shift">
            <div class="bg-accent" style="width: {100 * l2Share}%"></div>
            <div class="bg-o65" style="width: {100 * (1 - l2Share)}%"></div>
          </div>
          <p class="mt-1.5 text-fg-2 tabular-nums">
            {#if dec.metric === 'blend'}
              Shape distance <strong class="text-fg">{dec.d.toFixed(2)}</strong> = bin-by-bin {dec.l2Part.toFixed(2)} ({Math.round(100 * l2Share)} %) + age-shift {dec.w1Part.toFixed(2)} ({Math.round(100 * (1 - l2Share))} %)
            {:else}
              {ex.decompositionSentence}
            {/if}
          </p>
          {#if !decomposable}
            <p class="mt-0.5 text-xs text-muted">d above is under {METRIC_LABEL[metric]}; the split is stated for Shape (blend).</p>
          {/if}
          <div class="mt-2 flex flex-wrap items-center gap-3">
            <DiffBars delta={pair.delta} {highlight} width={126} />
            <div class="text-xs text-fg-2">
              <div><span class="text-muted">largest bin gaps</span> {dec.topBinsL2.map(([k, f]) => `${binLabel(k, dec.sex)} ${Math.round(100 * f)} %`).join(', ')}</div>
              <div><span class="text-muted">most age movement</span> {dec.topBinsW1.map(([k, y]) => `${binLabel(k, dec.sex)} ${y.toFixed(2)} y`).join(', ')}</div>
            </div>
          </div>
          <p class="mt-2 text-xs text-muted">{ex.w1Sentence}</p>
        {/if}
        <p class="mt-3 text-sm text-fg-2"><span class="text-muted">similar because</span> {ex.because}</p>
        <p class="mt-0.5 text-sm text-fg-2"><span class="text-muted">differs in</span> {ex.differsIn}</p>
      </div>

      <!-- feature table -->
      <div class="min-w-0 overflow-x-auto">
        <h3 class="text-xs font-medium uppercase tracking-wide text-muted">Summary features</h3>
        <table class="mt-2 w-full text-xs">
          <caption class="sr-only">Summary features of both pyramids; z-scores are against the {pair.referenceYear} country set ({pair.nReference} countries)</caption>
          <thead class="text-left text-muted">
            <tr>
              <th scope="col" class="py-1 pr-2 font-medium">feature</th>
              <th scope="col" class="py-1 pr-2 font-medium tabular-nums">A · {a.year}</th>
              <th scope="col" class="py-1 pr-2 font-medium tabular-nums">B · {b.year}</th>
              <th scope="col" class="py-1 pr-2 font-medium" title="standard deviations from the {pair.referenceYear} country mean">z A</th>
              <th scope="col" class="py-1 font-medium">z B</th>
            </tr>
          </thead>
          <tbody>
            {#each pair.features as f (f.name)}
              <tr class="border-t border-border" class:alike={alike.has(f.name as never)} class:differs={differs.has(f.name as never)}>
                <th scope="row" class="py-1 pr-2 text-left font-normal text-fg-2">
                  {f.label}
                  {#if alike.has(f.name as never)}<span class="chip ml-1 alike-chip">alike</span>{:else if differs.has(f.name as never)}<span class="chip ml-1 differs-chip">differs</span>{/if}
                </th>
                <td class="py-1 pr-2 tabular-nums">{formatTableFeature(f.name, f.rawA)}</td>
                <td class="py-1 pr-2 tabular-nums">{formatTableFeature(f.name, f.rawB)}</td>
                <td class="py-1 pr-2 tabular-nums text-fg-2">{formatZ(f.zA)}</td>
                <td class="py-1 tabular-nums text-fg-2">{formatZ(f.zB)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="mt-1 text-[11px] text-muted">z-scores for both against the {pair.referenceYear} country set ({pair.nReference} countries ≥ 100k), whatever B's year — so “alike” means alike by {pair.referenceYear} standards.</p>
      </div>
    </div>
  {/if}

  {#if lens}
    <div class="mt-4 border-t border-border pt-3">
      <h3 class="text-xs font-medium uppercase tracking-wide text-muted">
        Economic context
        <a class="ml-1 text-[10px] font-normal normal-case text-muted underline decoration-dotted underline-offset-2 hover:text-fg" href={evidenceHref('sources')} title="Sources, splicing and licences; what the literature found">evidence</a>
      </h3>
      {#if econStatus === 'idle' || econStatus === 'loading'}
        <p class="mt-1 text-xs text-muted" aria-busy="true">loading the economic series…</p>
      {:else if econStatus === 'absent'}
        <p class="mt-1 text-xs text-fg-2">This build shipped no economic series.</p>
      {:else if econStatus === 'error'}
        <p class="mt-1 text-xs text-fg-2" role="alert">Could not load the economic series.</p>
      {:else if econRows && econRows.length === 0}
        <p class="mt-1 text-xs text-fg-2">no GDP series for either member (countries only)</p>
      {:else if econRows}
        <div class="overflow-x-auto">
          <table class="mt-2 w-full text-xs">
            <caption class="sr-only">Economic context of both members; z-scores are against the {a.year} country cross-section</caption>
            <thead class="text-left text-muted">
              <tr>
                <th scope="col" class="py-1 pr-2 font-medium">series</th>
                <th scope="col" class="py-1 pr-2 font-medium tabular-nums">A · {Math.min(a.year, econ?.yearMax ?? a.year)}</th>
                <th scope="col" class="py-1 pr-2 font-medium tabular-nums">B · {Math.min(b.year ?? 0, econ?.yearMax ?? 0)}</th>
                <th scope="col" class="py-1 pr-2 font-medium" title="standard deviations from the {a.year} country mean">z A</th>
                <th scope="col" class="py-1 pr-2 font-medium">z B</th>
                <th scope="col" class="py-1 font-medium" title="countries with a value in {a.year}">n</th>
              </tr>
            </thead>
            <tbody>
              {#each econRows as r (r.field)}
                <tr class="border-t border-border">
                  <th scope="row" class="py-1 pr-2 text-left font-normal text-fg-2">{r.label}</th>
                  <td class="py-1 pr-2 tabular-nums">{r.rawA}</td>
                  <td class="py-1 pr-2 tabular-nums">{r.rawB}</td>
                  <td class="py-1 pr-2 tabular-nums text-fg-2">{formatZ(r.zA ?? NaN)}</td>
                  <td class="py-1 pr-2 tabular-nums text-fg-2">{formatZ(r.zB ?? NaN)}</td>
                  <td class="py-1 tabular-nums text-muted">{r.n}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <p class="mt-1 text-[11px] text-muted">Maddison 2023 (2011 international $, spliced past 2022 with WDI / PWT growth), PWT 11.0, WB OGHIST, WPP 2024; both members z-scored against the {a.year} country cross-section, whatever B's year.{econYearNote ? ` ${econYearNote}.` : ''}</p>
      {/if}
    </div>
  {/if}

  <p class="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm">
    <a class="underline" href={href(countryQuery(a.entity.id, a.year))}><span aria-hidden="true">{flagEmoji(a.entity)}</span> {a.entity.short_name} {a.year} page</a>
    {#if b.year !== null}
      <a class="underline" href={href(countryQuery(b.entity.id, b.year))}><span aria-hidden="true">{flagEmoji(b.entity)}</span> {b.entity.short_name} {b.year} page</a>
    {/if}
  </p>
</section>

<style>
  .band-very_close,
  .band-close {
    border-color: color-mix(in srgb, var(--wa) 60%, transparent);
  }
  .band-far,
  .band-extreme {
    border-color: color-mix(in srgb, var(--u15) 60%, transparent);
  }
  .best[aria-pressed='true'] {
    background: color-mix(in srgb, var(--accent) 16%, var(--surface));
    border-color: var(--accent);
    color: var(--fg);
    font-weight: 500;
  }
  tr.alike th,
  tr.alike td {
    background: color-mix(in srgb, var(--wa) 8%, transparent);
  }
  tr.differs th,
  tr.differs td {
    background: color-mix(in srgb, var(--u15) 8%, transparent);
  }
  .alike-chip {
    border-color: color-mix(in srgb, var(--wa) 60%, transparent);
  }
  .differs-chip {
    border-color: color-mix(in srgb, var(--u15) 60%, transparent);
  }
</style>
