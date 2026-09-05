<script lang="ts">
  // /compare/{a}/{ya}/{b}/{yb|best} — the compare page (PLAN §7 J4/J5/J6). A filled, B outlined on one fixed axis
  // (max of the pair, caption when widened); views overlay / diff / side; two scrubbers with lock-offset; the pair
  // card; swap; "B → best year" (resolved client-side by the store, then replaceState'd to the concrete year +
  // ?from=best so Copy-link never emits `best`); the export menu + share button (Y2's ExportMenu / ShareButton) mount
  // in the pair card's tools slot once B's year is concrete.
  import { app } from '../lib/state.svelte.ts';
  import { flagEmoji, meta } from '../lib/entities.ts';
  import { AXES, COMPARE_VIEWS, METRICS_ADVANCED, METRICS_VISIBLE, UNITS, visualExposed, type Axis, type CompareView, type Metric, type Sex, type Unit } from '../lib/router.ts';
  import { href } from '../lib/url.ts';
  import { entitySeries } from '../lib/series.ts';
  import { fmtPersons, fmtPersonsCompact } from '../lib/format.ts';
  import { UNIT_LABEL } from '../lib/bars.ts';
  import { METRIC_LABEL, METRIC_HINT, SEX_LABEL } from '../lib/restate.ts';
  import { pyramidToCsv, SITE_NAME, SOURCE_LINE } from '../lib/export.ts';
  import Overlay from '../lib/components/Overlay.svelte';
  import CompareScrubbers from '../lib/components/CompareScrubbers.svelte';
  import PairCard from '../lib/components/PairCard.svelte';
  import Picker from '../lib/components/Picker.svelte';
  import ExportMenu, { type CsvItem } from '../lib/components/ExportMenu.svelte';
  import ShareButton from '../lib/components/ShareButton.svelte';

  const q = $derived(app.compare);
  const A = $derived(app.entityA);
  const B = $derived(app.entityB);
  const pyA = $derived(app.pyramidA);
  const pyB = $derived(app.pyramidB);
  const axis = $derived(app.pairAxis);
  const yb = $derived(q && q.yb !== 'best' ? q.yb : null);
  const seriesA = $derived(A && app.shardA?.id === A.id ? entitySeries(app.shardA) : null);
  const seriesB = $derived(B && app.shardB?.id === B.id ? entitySeries(app.shardB) : null);

  const AXIS_LABEL: Record<Axis, string> = { fit: 'fit pair', pin10: 'pin 10 %', noclip: 'never clip (0–17 %)' };
  const VIEW_LABEL: Record<CompareView, string> = { overlay: 'Overlay', diff: 'Difference', side: 'Side by side' };
  const VIEW_HINT: Record<CompareView, string> = { overlay: 'A filled, B as a dashed outline on one axis', diff: 'B − A per age band, percentage points of total', side: 'two pyramids on the same axis' };
  const corpusMb = (meta.sizes.shares_d16z / 1e6).toFixed(1);

  let dragging = $state(false);
  let dragTimer: ReturnType<typeof setTimeout> | null = null;
  let svgEl = $state<SVGSVGElement | null>(null);

  function onInput(side: 'a' | 'b', y: number) {
    dragging = true;
    if (dragTimer) clearTimeout(dragTimer);
    dragTimer = setTimeout(() => (dragging = false), 250);
    app.setCompareYear(side, y, { commit: false });
  }
  function onCommit(side: 'a' | 'b', y: number) {
    dragging = false;
    app.setCompareYear(side, y, { commit: true });
  }

  const resolvingText = $derived.by(() => {
    if (!q || q.yb !== 'best' || !A || !B) return null;
    if (app.corpusStatus === 'error') return `could not load all years: ${app.corpusError}`;
    if (app.corpus && app.bestB === null) return `no year of ${B.short_name} in the allowed era qualifies (population floor / era)`;
    return `finding the year of ${B.short_name} closest to ${A.short_name} ${q.ya} … loading all years (${corpusMb} MB)`;
  });
  const pairLoading = $derived.by(() => {
    if (app.pair || app.pairError || !q) return null;
    if (q.yb === 'best') return resolvingText;
    if (app.compareNeedsEmbedding && !app.embedding) return app.embeddingStatus === 'error' ? 'could not load the image embedding' : 'loading the image embedding…';
    return 'loading the two years…';
  });
  const bestNote = $derived.by(() => {
    const best = app.bestB;
    if (!q || !best || q.from !== 'best' || !B) return null;
    if (!best.boundaryHit) return null;
    const era = q.era ?? (q.ya > app.currentYear ? 'all' : 'obs');
    return era === 'obs'
      ? `${B.short_name}'s best year sits on the edge of the observed years (${best.year}) — the true best may be a projection.`
      : `${B.short_name}'s best year sits on the edge of the corpus (${best.year}).`;
  });
  const widenedCaption = $derived(axis && axis.widened ? `axis widened to ${axis.axisPct} % (${A?.short_name ?? 'A'} alone fits ${axis.aFit} %)` : null);

  // export (Y2's ExportMenu / lib/export.ts): PNG 2× with the pair footer, SVG of the live chart, focal + overlay CSV
  const csvItems = $derived<CsvItem[]>([
    {
      label: 'Both pyramids (CSV)',
      suffix: 'pyramids',
      text: () =>
        pyA && pyB && A && B
          ? pyramidToCsv({ id: A.id, name: A.short_name, year: pyA.year, shares: pyA.shares, total: pyA.total }, { id: B.id, name: B.short_name, year: pyB.year, shares: pyB.shares, total: pyB.total })
          : null,
    },
  ]);
  const footer = $derived(
    A && B && q && pyA
      ? `${A.short_name} ${q.ya} · Pop ${fmtPersonsCompact(pyA.total)} vs ${B.short_name} ${yb ?? ''}${pyB ? ` · Pop ${fmtPersonsCompact(pyB.total)}` : ''} · ${SOURCE_LINE} · ${SITE_NAME}`
      : undefined,
  );
  const basename = $derived(A && B && q ? ['compare', A.slug, q.ya, B.slug, yb ?? 'best', q.view] : ['compare']);
  const shareTitle = $derived(A && B && q ? `${A.short_name} ${q.ya} vs ${B.short_name} ${yb ?? ''} · ${SITE_NAME}` : SITE_NAME);
  /** Share always the canonical URL of the current query — the resolved year, never `best` (J6). */
  const shareUrl = () => (app.compare ? new URL(href(app.compare), location.href).toString() : location.href);
</script>

{#if q && A && B}
  <header class="mb-4 flex flex-wrap items-start gap-3">
    <div class="min-w-0 flex-1">
      <p class="text-xs font-medium uppercase tracking-wide text-muted">Compare</p>
      <h1 class="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-2xl font-semibold tracking-tight sm:text-3xl">
        <span><span class="inline-block w-8 text-2xl leading-none" aria-hidden="true">{flagEmoji(A)}</span>{A.short_name} <span class="font-light text-fg-2 tabular-nums">{q.ya}</span></span>
        <span class="text-xl font-light text-muted">vs</span>
        <span><span class="inline-block w-8 text-2xl leading-none" aria-hidden="true">{flagEmoji(B)}</span>{B.short_name} <span class="font-light text-fg-2 tabular-nums">{yb ?? 'best year…'}</span></span>
      </h1>
      <p class="mt-0.5 text-sm text-fg-2 tabular-nums">
        {#if pyA}A: {fmtPersons(pyA.total)} people{/if}
        {#if pyB} · B: {fmtPersons(pyB.total)} people{/if}
      </p>
    </div>
    <details class="w-full sm:w-auto">
      <summary class="btn cursor-pointer text-xs">change countries…</summary>
      <div class="mt-2 grid gap-2 sm:grid-cols-2">
        <label class="text-xs text-muted">A<Picker id="picker-a" onpick={(e) => app.setCompareEntity('a', e.id)} placeholder="Replace {A.short_name}…" /></label>
        <label class="text-xs text-muted">B<Picker id="picker-b" onpick={(e) => app.setCompareEntity('b', e.id)} placeholder="Replace {B.short_name}…" /></label>
      </div>
    </details>
  </header>

  {#if app.error && !pyA}
    <div class="card border-red-500/40 text-sm" role="alert">Could not load the data: {app.error}</div>
  {/if}

  <section aria-label="Overlay" class="min-w-0">
    <div class="mb-2 flex flex-wrap items-center gap-2 text-sm">
      <div class="seg" role="group" aria-label="View">
        {#each COMPARE_VIEWS as v (v)}
          <button type="button" aria-pressed={q.view === v} title={VIEW_HINT[v]} onclick={() => app.setCompareOptions({ view: v })}>{VIEW_LABEL[v]}</button>
        {/each}
      </div>
      <div class="seg" role="group" aria-label="Unit">
        {#each UNITS as u (u)}
          <button type="button" aria-pressed={q.unit === u} onclick={() => app.setCompareOptions({ unit: u as Unit })}>{UNIT_LABEL[u]}</button>
        {/each}
      </div>
      <label class="ml-auto flex items-center gap-1.5 text-xs text-fg-2">
        Axis
        <select class="rounded-md border border-border bg-surface px-2 py-1 text-sm text-fg" value={q.axis} onchange={(e) => app.setCompareOptions({ axis: (e.target as HTMLSelectElement).value as Axis })}>
          {#each AXES as ax (ax)}
            <option value={ax}>{AXIS_LABEL[ax]}{ax === 'fit' && axis ? ` (${Math.max(A.axis_pct, B.axis_pct)} %)` : ''}</option>
          {/each}
        </select>
      </label>
    </div>

    {#if pyA && axis}
      <div class="card p-2 sm:p-3">
        <Overlay
          a={{ shares: pyA.shares, total: pyA.total, name: A.short_name, year: pyA.year }}
          b={pyB ? { shares: pyB.shares, total: pyB.total, name: B.short_name, year: pyB.year } : null}
          {axis}
          unit={q.unit}
          view={q.view}
          fast={dragging}
          bind:svg={svgEl}
        />
        {#if widenedCaption}<p class="mt-1 text-xs text-muted">{widenedCaption}</p>{/if}
        {#if q.view === 'overlay'}<p class="mt-1 text-xs text-muted">Ticks stay in % of each pyramid's total so both shapes share one axis; the unit applies to the table and the side-by-side view.</p>{/if}
      </div>
    {:else}
      <div class="card flex aspect-[640/478] items-center justify-center text-sm text-muted" aria-busy="true">{app.error ? 'no data' : 'loading pyramids…'}</div>
    {/if}

    <div class="mt-3">
      <CompareScrubbers
        a={{ name: A.short_name, year: q.ya, median: seriesA?.median ?? null }}
        b={{ name: B.short_name, year: yb, median: seriesB?.median ?? null }}
        currentYear={app.currentYear}
        lastObserved={app.lastObservedYear}
        lock={app.lockOffset}
        onlock={(on) => app.setLockOffset(on)}
        oninput={onInput}
        oncommit={onCommit}
        resolving={resolvingText}
      />
    </div>
  </section>

  <section class="mt-4" aria-label="Pair">
    <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-fg-2">
      <label class="flex min-w-0 items-center gap-1.5">
        Metric
        <select class="min-w-0 max-w-56 rounded-md border border-border bg-surface px-2 py-1 text-sm text-fg" value={q.metric} title={METRIC_HINT[q.metric]} onchange={(e) => app.setCompareOptions({ metric: (e.target as HTMLSelectElement).value as Metric })}>
          {#each METRICS_VISIBLE as m (m)}<option value={m}>{METRIC_LABEL[m]}</option>{/each}
          <optgroup label="advanced">
            {#each METRICS_ADVANCED as m (m)}<option value={m}>{METRIC_LABEL[m]}</option>{/each}
          </optgroup>
          {#if visualExposed()}<option value="visual" title={METRIC_HINT.visual}>Visual (experimental)</option>{/if}
        </select>
      </label>
      <div class="seg" role="group" aria-label="Sex">
        {#each ['2', '1'] as const as sx (sx)}
          <button type="button" aria-pressed={q.sex === sx} onclick={() => app.setCompareOptions({ sex: sx as Sex })}>{SEX_LABEL[sx]}</button>
        {/each}
      </div>
      <div class="seg" role="group" aria-label="Era for the best-year search">
        {#each [['obs', `observed to ${Math.max(app.lastObservedYear, app.currentYear)}`], ['all', 'incl. projections to 2100']] as const as [e, lbl] (e)}
          <button type="button" aria-pressed={(q.era ?? (q.ya > app.currentYear ? 'all' : 'obs')) === e} onclick={() => app.setCompareOptions({ era: e })} title="the years the best-year search may use (same rule as the time-shift table)">{lbl}</button>
        {/each}
      </div>
    </div>
    <PairCard
      pair={app.pair}
      a={{ entity: A, year: q.ya }}
      b={{ entity: B, year: yb }}
      metric={q.metric}
      bestLit={app.bestLit}
      canBest={yb !== null}
      {bestNote}
      loadingText={pairLoading}
      error={app.pairError}
      onswap={() => app.swapCompare()}
      onbest={() => app.compareBest()}
      econ={app.econ}
      econLib={app.econLib}
      econStatus={app.econStatus}
      lens={app.lensOn}
    >
      {#snippet tools()}
        {#if yb !== null}
          <ExportMenu {basename} svg={() => svgEl} {footer} csv={csvItems} title="Download the chart as PNG (2×, with footer) or SVG, or both pyramids as CSV" />
          <ShareButton url={shareUrl} title={shareTitle} compact />
        {/if}
      {/snippet}
    </PairCard>
  </section>

  <p class="mt-4 text-xs text-muted">
    Source: UN World Population Prospects 2024, medium variant · <a class="underline" href={href({ kind: 'home' })}>home</a> · <a class="underline" href={href({ kind: 'static', page: 'about' })}>how similarity works</a>
  </p>
{/if}
