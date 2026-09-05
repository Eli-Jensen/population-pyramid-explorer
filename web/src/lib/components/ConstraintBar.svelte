<script lang="ts">
  // Query constraints (PLAN §6, progressive disclosure). Row 1: year-mode segmented control, the restated
  // query and Reset. "More" reveals the era chip (J8), scope, floor, metric (visible / advanced / Visual), sex,
  // k, diversity preset and the trend toggle. Every change goes through `onchange` → the store writes the URL
  // (defaults elided). All controls are real buttons / selects / inputs (keyboard + screen reader).
  import {
    DEFAULT_SEARCH,
    DIV_VALUES,
    K_VALUES,
    L_VALUES,
    METRICS_ADVANCED,
    METRICS_VISIBLE,
    MINPOP_PRESETS,
    TRENDS,
    type CountryQuery,
    type Div,
    type K,
    type L,
    type Metric,
    type SearchInput,
    type Trend,
  } from '../router.ts';
  import { meta } from '../entities.ts';
  import { YEAR_MAX, YEAR_MIN } from '../types.ts';
  import {
    anyYearLabel,
    DIV_HINT,
    divLabel,
    eraChip,
    fmtMinpop,
    METRIC_HINT,
    METRIC_LABEL,
    MODE_LABEL,
    nonDefaultControls,
    restateQuery,
    SEX_LABEL,
    TREND_HINT,
  } from '../restate.ts';

  interface Props {
    query: CountryQuery;
    name: string; // focal short name
    currentYear: number;
    lastObserved: number;
    visual: boolean; // whether the build exposes an image space
    onchange: (o: SearchInput) => void;
    onreset: () => void;
  }
  let { query, name, currentYear, lastObserved, visual, onchange, onreset }: Props = $props();

  const q = $derived(query);
  const isToday = $derived(q.mode === 'range' && q.via === 'today');
  const activeMode = $derived(isToday ? 'today' : q.mode);
  const sentence = $derived(restateQuery(q, { name, currentYear, lastObserved }));
  const chip = $derived(eraChip(q, currentYear));
  const nonDefault = $derived(nonDefaultControls(q, DEFAULT_SEARCH));
  const advancedTouched = $derived(nonDefault.some((k) => !['mode', 'n', 'from', 'to', 'via'].includes(k)));
  let more = $state(false);
  $effect(() => {
    if (advancedTouched) more = true;
  });
  const modes = $derived(
    [
      { id: 'same', label: `${MODE_LABEL.same} (${q.year})` },
      ...(q.year === currentYear ? [] : [{ id: 'today', label: `${MODE_LABEL.today} (${currentYear})` }]),
      { id: 'near', label: MODE_LABEL.near },
      { id: 'range', label: MODE_LABEL.range },
      { id: 'any', label: anyYearLabel(q, currentYear, lastObserved) },
    ] as Array<{ id: 'same' | 'today' | 'near' | 'range' | 'any'; label: string }>,
  );
  const verdictNote = (m: Metric): string => {
    const v = meta.verdicts?.metrics[m === 'visual' ? (meta.verdicts.exposed_visual?.metric ?? 'visual') : m]?.verdict;
    return v ? ` — evaluation: ${v}` : '';
  };
  const trendOk = $derived(q.year - 5 >= YEAR_MIN);

  function setMode(id: 'same' | 'today' | 'near' | 'range' | 'any') {
    if (id === 'range' && q.mode !== 'range') {
      onchange({ mode: 'range', from: Math.max(YEAR_MIN, q.year - 20), to: Math.min(YEAR_MAX, q.year + 20), via: null });
      return;
    }
    onchange({ mode: id, via: null });
  }
  const num = (e: Event) => Number((e.target as HTMLInputElement | HTMLSelectElement).value);
  let rangeFrom = $derived(q.from ?? YEAR_MIN);
  let rangeTo = $derived(q.to ?? YEAR_MAX);
</script>

<div class="card mt-6 space-y-3 p-3" aria-label="Search constraints">
  <div class="flex flex-wrap items-center gap-2">
    <div class="seg flex-wrap" role="group" aria-label="Year mode">
      {#each modes as m (m.id)}
        <button type="button" aria-pressed={activeMode === m.id} onclick={() => setMode(m.id)}>{m.label}</button>
      {/each}
    </div>
    {#if q.mode === 'near'}
      <label class="flex items-center gap-1 text-sm text-fg-2">
        ±
        <input class="w-14 rounded-md border border-border bg-surface px-1.5 py-0.5 text-sm text-fg" type="number" min="1" max="150" value={q.n} onchange={(e) => onchange({ n: Math.max(1, Math.min(150, Math.round(num(e)))) })} aria-label="Half-width in years" />
        y
      </label>
    {:else if q.mode === 'range' && !isToday}
      <label class="flex items-center gap-1 text-sm text-fg-2">
        from
        <input class="w-18 rounded-md border border-border bg-surface px-1.5 py-0.5 text-sm text-fg" type="number" min={YEAR_MIN} max={YEAR_MAX} value={rangeFrom} onchange={(e) => onchange({ from: num(e), to: rangeTo, mode: 'range' })} aria-label="First year" />
        to
        <input class="w-18 rounded-md border border-border bg-surface px-1.5 py-0.5 text-sm text-fg" type="number" min={YEAR_MIN} max={YEAR_MAX} value={rangeTo} onchange={(e) => onchange({ to: num(e), from: rangeFrom, mode: 'range' })} aria-label="Last year" />
      </label>
    {/if}
    <button type="button" class="btn ml-auto" onclick={() => (more = !more)} aria-expanded={more} aria-controls="constraints-more">{more ? 'Less' : 'More'}</button>
    <button type="button" class="btn" onclick={onreset} disabled={nonDefault.length === 0} title="Back to the default constraints">Reset</button>
  </div>
  <p class="text-sm text-fg-2" aria-live="polite">{sentence}</p>

  {#if more}
    <div id="constraints-more" class="grid gap-3 border-t border-border pt-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      {#if chip}
        <div class="sm:col-span-2 lg:col-span-3">
          <span class="chip">{chip.text}</span>
          <button type="button" class="-my-1 ml-1 inline-block py-1 text-sm text-accent underline" onclick={() => onchange({ era: chip.target })}>{chip.action}</button>
          <span class="ml-2 text-xs text-muted">Projected pyramids converge, so they crowd cross-year matches unless the query is itself a projection.</span>
        </div>
      {/if}

      <label class="flex items-center justify-between gap-2">
        <span class="text-fg-2">Scope</span>
        <select class="rounded-md border border-border bg-surface px-2 py-1 text-fg" value={q.scope} onchange={(e) => onchange({ scope: (e.target as HTMLSelectElement).value as 'c' | 'all' })}>
          <option value="c">countries</option>
          <option value="all">countries + regions</option>
        </select>
      </label>

      <label class="flex items-center justify-between gap-2">
        <span class="text-fg-2" title="candidate's own-year population">Population floor</span>
        <select class="rounded-md border border-border bg-surface px-2 py-1 text-fg" value={String(q.minpop)} onchange={(e) => onchange({ minpop: num(e) })}>
          {#each MINPOP_PRESETS as p (p)}
            <option value={String(p)}>{fmtMinpop(p)}</option>
          {/each}
          {#if !(MINPOP_PRESETS as readonly number[]).includes(q.minpop)}<option value={String(q.minpop)}>{fmtMinpop(q.minpop)}</option>{/if}
        </select>
      </label>

      <label class="flex items-center justify-between gap-2">
        <span class="text-fg-2">Metric</span>
        <select class="max-w-56 rounded-md border border-border bg-surface px-2 py-1 text-fg" value={q.metric} disabled={q.trend !== null} title={q.trend ? 'Trend matching uses its own distance; switch the trend off to choose a snapshot metric.' : METRIC_HINT[q.metric]} onchange={(e) => onchange({ metric: (e.target as HTMLSelectElement).value as Metric })}>
          {#each METRICS_VISIBLE as m (m)}
            <option value={m} title={METRIC_HINT[m] + verdictNote(m)}>{METRIC_LABEL[m]}</option>
          {/each}
          <optgroup label="Advanced">
            {#each METRICS_ADVANCED as m (m)}
              <option value={m} title={METRIC_HINT[m] + verdictNote(m)}>{METRIC_LABEL[m]}</option>
            {/each}
          </optgroup>
          {#if visual}
            <optgroup label="Image embedding">
              <option value="visual" title={METRIC_HINT.visual + verdictNote('visual')}>{METRIC_LABEL.visual}</option>
            </optgroup>
          {/if}
        </select>
      </label>

      <div class="flex items-center justify-between gap-2">
        <span class="text-fg-2">Sex</span>
        <div class="seg" role="group" aria-label="Sex handling">
          {#each ['2', '1'] as const as s (s)}
            <button type="button" aria-pressed={q.sex === s} onclick={() => onchange({ sex: s })} title={s === '2' ? 'Distance over the 42 age × sex shares' : 'Collapse to the 21 total-age shares (sex ratio ignored)'}>{SEX_LABEL[s]}</button>
          {/each}
        </div>
      </div>

      <div class="flex items-center justify-between gap-2">
        <span class="text-fg-2">Results</span>
        <div class="seg" role="group" aria-label="Number of results">
          {#each K_VALUES as k (k)}
            <button type="button" aria-pressed={q.k === k} onclick={() => onchange({ k: k as K })}>{k}</button>
          {/each}
        </div>
      </div>

      <div class="flex items-center justify-between gap-2">
        <span class="text-fg-2" title="how far apart the 'most different' results are pushed">Diversity</span>
        <div class="seg" role="group" aria-label="Diversity of the opposites">
          {#each DIV_VALUES as d (d)}
            <button type="button" aria-pressed={q.div === d} onclick={() => onchange({ div: d as Div })} title={DIV_HINT[String(d)]}>{divLabel(d as Div)}</button>
          {/each}
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 sm:col-span-2 lg:col-span-3">
        <span class="text-fg-2" title="Compare how pyramids MOVE over L years instead of where they stand">Trend</span>
        <div class="flex flex-wrap items-center gap-2">
          <div class="seg" role="group" aria-label="Trend matching">
            <button type="button" aria-pressed={q.trend === null} onclick={() => onchange({ trend: null })}>off</button>
            {#each TRENDS as t (t)}
              <button type="button" aria-pressed={q.trend === t} disabled={!trendOk} onclick={() => onchange({ trend: t as Trend })} title={TREND_HINT[t]}>{t}</button>
            {/each}
          </div>
          {#if q.trend}
            <div class="seg" role="group" aria-label="Trend window">
              {#each L_VALUES as l (l)}
                <button type="button" aria-pressed={q.L === l} disabled={q.year - l < YEAR_MIN} onclick={() => onchange({ L: l as L })}>{l} y</button>
              {/each}
            </div>
          {/if}
          {#if !trendOk}<span class="text-xs text-muted">needs a year ≥ {YEAR_MIN + 5}</span>{/if}
        </div>
      </div>
    </div>
  {/if}
</div>
