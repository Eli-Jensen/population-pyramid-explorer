<script lang="ts">
  // /{slug}/{year} — the country page (PLAN §7). M1: pyramid, scrubber, callouts, narrative, age shares.
  // M2: distinctiveness chip, constraint bar, twins + opposites (full width below the two columns), the
  // own-trajectory row and the collapsed time-shift panel. Data flow: the store owns route + shards + search;
  // scrubbing repaints from the entity shard alone and the search trails the slider by 30 ms.
  import { app } from '../lib/state.svelte.ts';
  import { flagEmoji, isAggregate, byId, meta } from '../lib/entities.ts';
  import { AXES, UNITS, visualExposed, type Axis, type Unit } from '../lib/router.ts';
  import { href } from '../lib/url.ts';
  import { entitySeries, tenYearChange } from '../lib/series.ts';
  import { narrative } from '../lib/narrative.ts';
  import { fmtPersons } from '../lib/format.ts';
  import { UNIT_LABEL } from '../lib/bars.ts';
  import { rememberLast } from '../lib/last.ts';
  import { eraEdge, METRIC_LABEL } from '../lib/restate.ts';
  import Pyramid from '../lib/components/Pyramid.svelte';
  import Readout from '../lib/components/Readout.svelte';
  import YearScrubber from '../lib/components/YearScrubber.svelte';
  import Callouts from '../lib/components/Callouts.svelte';
  import Narrative from '../lib/components/Narrative.svelte';
  import AgeShares from '../lib/components/AgeShares.svelte';
  import Picker from '../lib/components/Picker.svelte';
  import Distinctiveness from '../lib/components/Distinctiveness.svelte';
  import ConstraintBar from '../lib/components/ConstraintBar.svelte';
  import Twins from '../lib/components/Twins.svelte';
  import Opposites from '../lib/components/Opposites.svelte';
  import TimeShiftTable from '../lib/components/TimeShiftTable.svelte';

  const entity = $derived(app.entity);
  const year = $derived(app.year);
  const pyramid = $derived(app.pyramid);
  const features = $derived(app.features);
  const shard = $derived(app.entityShard?.id === entity?.id ? app.entityShard : null);
  const series = $derived(shard ? entitySeries(shard) : null);
  const change = $derived(shard ? tenYearChange(shard.totals, year) : null);

  const AXIS_LABEL: Record<Axis, string> = { fit: 'fit entity', pin10: 'pin 10 %', noclip: 'never clip (0–17 %)' };

  let selected = $state<number | null>(null);
  let dragging = $state(false);
  let dragTimer: ReturnType<typeof setTimeout> | null = null;

  // Default the readout to the modal bin once a pyramid lands; keep the reader's choice afterwards.
  $effect(() => {
    if (selected === null && features) selected = features.modal_bin / 5;
  });
  $effect(() => {
    if (entity) rememberLast(entity.id, year);
  });

  function onInput(y: number) {
    dragging = true;
    if (dragTimer) clearTimeout(dragTimer);
    dragTimer = setTimeout(() => (dragging = false), 250);
    app.setYear(y, { commit: false });
  }
  function onCommit(y: number) {
    dragging = false;
    app.setYear(y, { commit: true });
  }

  const paragraphs = $derived(
    entity && features && pyramid
      ? narrative({
          name: entity.short_name,
          isAggregate: isAggregate(entity),
          year,
          era: app.era,
          total: pyramid.total,
          features,
          change,
          lastObservedYear: app.lastObservedYear,
        })
      : [],
  );
  const eraLabel = $derived(app.era === 'observed' ? 'observed' : app.era === 'nowcast' ? 'nowcast' : 'projected');
  const memberNames = $derived(entity?.members?.map((id) => byId(id)?.short_name ?? id).sort() ?? []);

  // ---- M2: search ----
  const query = $derived(app.query);
  const results = $derived(app.results);
  const corpusMb = (meta.sizes.shares_d16z / 1e6).toFixed(1);
  const embMb = $derived(app.visualModel ? ((meta.sizes.emb[app.visualModel] ?? 0) / 1e6).toFixed(1) : '0');
  /** Skeleton caption while the search waits for data (null = a computed result is on its way). */
  const loadingText = $derived.by(() => {
    if (results) return null;
    if (app.searchError) return null;
    if (app.needsCorpus) {
      if (app.corpusStatus === 'error') return `could not load all years: ${app.corpusError}`;
      return `loading all years… ${corpusMb} MB`;
    }
    if (app.needsEmbedding && !app.embedding) return app.embeddingStatus === 'error' ? 'could not load the image embedding' : `loading the image embedding… ${embMb} MB`;
    return 'loading this year…';
  });
  const focal = $derived(
    entity && pyramid ? { id: entity.id, shares: pyramid.shares, name: entity.short_name, year: results?.q.year ?? year } : null,
  );
  const metricLabel = $derived(query?.trend ? `trend (${query.trend}, ${query.L} y)` : METRIC_LABEL[query?.metric ?? 'blend']);
</script>

{#if entity && query}
  <header class="mb-4 flex flex-wrap items-start gap-3">
    <div class="min-w-0 flex-1">
      <div class="flex flex-wrap items-center gap-2">
        <span class="inline-block w-8 text-2xl leading-none" aria-hidden="true">{flagEmoji(entity)}</span>
        <span class="chip font-mono uppercase">{entity.type === 'country' ? entity.id : (entity.agg_kind ?? 'group')}</span>
        <h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{entity.short_name}</h1>
        <span class="text-2xl font-light text-fg-2 tabular-nums sm:text-3xl">{year}</span>
        <span class="chip" title="observed ≤ {app.lastObservedYear}; nowcast ≤ {app.currentYear}; projected after">{eraLabel}</span>
        <Distinctiveness percentile={app.isolationPercentile} {metricLabel} />
      </div>
      <div class="mt-0.5 text-sm text-fg-2">
        {#if entity.name !== entity.short_name}<span>{entity.name} · </span>{/if}
        {#if pyramid}<span class="tabular-nums">{fmtPersons(pyramid.total)} people</span>{:else}<span>loading…</span>{/if}
        {#if entity.members?.length}
          <details class="mt-0.5 inline-block align-baseline">
            <summary class="cursor-pointer text-xs text-muted">ⓘ {entity.members.length} members</summary>
            <p class="mt-1 max-w-prose text-xs text-fg-2">{memberNames.join(', ')}</p>
          </details>
        {/if}
      </div>
    </div>
    <div class="w-full sm:w-72">
      <Picker onpick={(e) => app.setEntity(e.id)} placeholder="Switch country or region…" id="country-picker" />
    </div>
  </header>

  {#if app.error && !pyramid}
    <div class="card border-red-500/40 text-sm" role="alert">Could not load the data: {app.error}</div>
  {/if}

  <div class="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
    <section class="min-w-0" aria-label="Pyramid">
      <div class="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <div class="seg" role="group" aria-label="Unit">
          {#each UNITS as u (u)}
            <button type="button" aria-pressed={app.options.unit === u} onclick={() => app.setOptions({ unit: u as Unit })}>{UNIT_LABEL[u]}</button>
          {/each}
        </div>
        <label class="ml-auto flex items-center gap-1.5 text-xs text-fg-2">
          Axis
          <select
            class="rounded-md border border-border bg-surface px-2 py-1 text-sm text-fg"
            value={app.options.axis}
            onchange={(e) => app.setOptions({ axis: (e.target as HTMLSelectElement).value as Axis })}
          >
            {#each AXES as a (a)}
              <option value={a}>{AXIS_LABEL[a]}{a === 'fit' ? ` (${entity.axis_pct} %)` : ''}</option>
            {/each}
          </select>
        </label>
      </div>

      {#if pyramid}
        <div class="card p-2 sm:p-3">
          <Pyramid
            shares={pyramid.shares}
            total={pyramid.total}
            axis={app.axis}
            unit={app.options.unit}
            name={entity.short_name}
            {year}
            {selected}
            onselect={(k) => (selected = k)}
            fast={dragging}
          />
        </div>
        <Readout shares={pyramid.shares} total={pyramid.total} bin={selected} />
      {:else}
        <div class="card flex aspect-[640/478] items-center justify-center text-sm text-muted" aria-busy="true">
          {app.error ? 'no data' : 'loading pyramid…'}
        </div>
      {/if}

      <div class="card mt-3">
        <YearScrubber
          {year}
          currentYear={app.currentYear}
          lastObserved={app.lastObservedYear}
          median={series?.median ?? null}
          oninput={onInput}
          oncommit={onCommit}
        />
      </div>
    </section>

    <aside class="min-w-0 space-y-4" aria-label="Review">
      {#if pyramid && features}
        <Callouts total={pyramid.total} {features} {change} {year} />
        <Narrative {paragraphs} />
      {/if}
      {#if series}
        <AgeShares {series} {year} currentYear={app.currentYear} lastObserved={app.lastObservedYear} onpick={(y) => app.setYear(y)} />
      {/if}
      <p class="text-xs text-muted">
        Source: UN World Population Prospects 2024, medium variant · <a class="underline" href={href({ kind: 'home' })}>home</a>
      </p>
    </aside>
  </div>

  <!-- M2: twins + opposites, full width -->
  <section aria-label="Similar and different pyramids">
    <ConstraintBar
      {query}
      name={entity.short_name}
      currentYear={app.currentYear}
      lastObserved={app.lastObservedYear}
      visual={visualExposed()}
      onchange={(o) => app.setOptions(o)}
      onreset={() => app.resetSearch()}
    />
    {#if app.searchError}
      <p class="card mt-3 border-red-500/40 text-sm" role="alert">The search could not run: {app.searchError}</p>
    {/if}
    {#if focal}
      <Twins {results} k={query.k} {focal} {loadingText} lastObserved={app.lastObservedYear} currentYear={app.currentYear} />
      <Opposites {results} k={query.k} div={query.div} {focal} {loadingText} lastObserved={app.lastObservedYear} currentYear={app.currentYear} />
      {#if results && results.ms > 0}
        <p class="mt-2 text-right text-[11px] text-muted" title="scan + dedupe + MMR + explanations, main thread">
          {results.nCandidates.toLocaleString('en-US')} candidate rows · {results.source === 'corpus' ? 'all years' : 'year shards'} · {results.ms.toFixed(1)} ms
          {#if results.source === 'corpus' && app.corpus}
            · all-years blob {corpusMb} MB fetched in {app.corpus.source.fetchMs.toFixed(0)} ms, decoded in {app.corpus.source.decodeMs.toFixed(0)} ms ({app.corpus.source.path})
          {/if}
        </p>
      {/if}
      <TimeShiftTable
        rows={app.timeShift}
        open={app.timeShiftOpen}
        ontoggle={(o) => app.setTimeShiftOpen(o)}
        status={app.corpusStatus}
        error={app.corpusError}
        focal={{ name: entity.short_name, year }}
        eraEdge={eraEdge(app.searchEra, app.currentYear, app.lastObservedYear)}
        corpusBytes={meta.sizes.shares_d16z}
      />
    {/if}
  </section>
{/if}
