<script lang="ts">
  // One twin / opposite (PLAN §6 J3, §5): mini pyramid with the focal ghosted, name + year (+ Δy and a
  // projected badge for cross-year hits), band chip with percentile, raw rank for opposites, decomposition
  // sparkline and the two explanation sentences. The mini pyramid and the title link to the compare page
  // /compare/{focal}/{year}/{cand}/{candYear} (M3, PLAN §7) under the metric/sex that ranked the card; a small
  // secondary link opens the candidate's own page. M5: with the market lens on, a historical card (year ≤ last econ
  // year − 5) gains a "then what happened ▸" disclosure (lazy econ chunk: GDP/cap → +10/+20/+30, dividend window, the
  // market row beside VT); a current-era card (J9 lookalikes today) carries the investability badge instead.
  import { app, type CardData } from '../state.svelte.ts';
  import { loadEconUi } from '../econ/ui.ts';
  import { compareQuery, countryQuery, type Metric, type Sex } from '../router.ts';
  import { href } from '../url.ts';
  import { flagEmoji } from '../entities.ts';
  import { BAND_HINT, BAND_LABEL, cardTitle, fmtPercentile } from '../restate.ts';
  import MiniPyramid from './MiniPyramid.svelte';
  import DiffBars from './DiffBars.svelte';

  interface Props {
    card: CardData;
    kind: 'twin' | 'opposite';
    focal: { id: string; shares: Float32Array; name: string; year: number; metric?: Metric; sex?: Sex };
    lastObserved: number;
    currentYear: number;
  }
  let { card, kind, focal, lastObserved, currentYear }: Props = $props();

  const r = $derived(card.result);
  const e = $derived(card.entity);
  const title = $derived(cardTitle(e.short_name, r.year, r.dy));
  const eraBadge = $derived(r.year > currentYear ? 'projected' : r.year > lastObserved ? 'nowcast' : null);
  const dec = $derived(card.explanation?.decomposition ?? null);
  // topBins index the 42-vector for two-sex, s21 for total-only — map s21 bins onto both sexes' columns
  const highlight = $derived.by(() => {
    if (!dec) return [];
    const bins = [...dec.topBinsL2.map(([b]) => b), ...dec.topBinsW1.map(([b]) => b)];
    return dec.sex === '2' ? bins : bins.flatMap((b) => [b, b + 21]);
  });
  const link = $derived(href(compareQuery(focal.id, focal.year, e.id, r.year, { metric: focal.metric, sex: focal.sex }, currentYear)));
  const pageLink = $derived(href(countryQuery(e.id, r.year)));
  const bandChip = $derived(`${BAND_LABEL[r.band]}${r.percentile !== null ? ` · ${fmtPercentile(r.percentile)}` : ''}`);
  const thenWhat = $derived(app.lensOn && !!app.econ && e.type === 'country' && app.lastEconYear !== null && r.year <= app.lastEconYear - 5);
  // J9 lookalikes today: a current-era card (no "then what" window yet) carries the investability badge instead —
  // live / liquidated fund + MSCI class as recorded, never a price or a return.
  const badge = $derived(app.lensOn && !!app.econ && e.type === 'country' && !thenWhat);
  const bandTitle = $derived(
    r.percentile !== null
      ? `${kind === 'opposite' ? 'farther' : 'closer'} than ${fmtPercentile(kind === 'opposite' ? r.percentile : 100 - r.percentile)} of random pairs of this kind (${BAND_HINT[r.band]})`
      : BAND_HINT[r.band],
  );
</script>

<article class="card flex gap-3 p-3" aria-label="{title}: {kind === 'twin' ? 'similar to' : 'different from'} {focal.name} {focal.year}">
  <a href={link} title="Compare {focal.name} {focal.year} with {title} (overlay)" class="shrink-0 rounded-md focus-visible:outline-2">
    <MiniPyramid shares={card.shares} ghost={focal.shares} size={104} label="Pyramid of {title}, with {focal.name} {focal.year} outlined behind it" />
  </a>
  <div class="min-w-0 flex-1 text-sm">
    <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span class="inline-block w-5 text-base leading-none" aria-hidden="true">{flagEmoji(e)}</span>
      <a href={link} class="font-medium text-fg hover:underline" title="Compare {focal.name} {focal.year} with {title} (overlay)">{title}</a>
      {#if eraBadge}<span class="chip">{eraBadge}</span>{/if}
      <a href={pageLink} class="text-xs text-muted hover:underline" title="Open the {e.short_name} {r.year} page">page →</a>
    </div>
    <div class="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
      <span class="chip band-{r.band}" title={bandTitle}>{bandChip}</span>
      {#if kind === 'opposite'}
        <span class="chip font-mono" title="rank in the plain farthest-first ordering (diversity may promote a lower rank)">#{r.rankRaw} farthest</span>
      {:else if r.rankRaw !== undefined}
        <span class="chip font-mono" title="rank in the nearest-first ordering">#{r.rankRaw}</span>
      {/if}
      <span class="tabular-nums text-muted" title="distance under the active metric">d {r.d.toFixed(2)}</span>
    </div>
    <div class="mt-2 flex items-center gap-2">
      <DiffBars delta={card.delta} {highlight} width={84} />
      {#if dec}
        <span class="text-xs text-muted tabular-nums" title={card.explanation?.decompositionSentence}>
          L2 {dec.l2Part.toFixed(2)} + W1 {dec.w1Part.toFixed(2)}
        </span>
      {/if}
    </div>
    {#if card.explanation}
      <p class="mt-1.5 text-xs text-fg-2">
        <span class="text-muted">{kind === 'twin' ? 'similar because' : 'still alike in'}</span> {card.explanation.because}
      </p>
      <p class="mt-0.5 text-xs text-fg-2"><span class="text-muted">differs in</span> {card.explanation.differsIn}</p>
      {#if card.explanation.w1Sentence}<p class="mt-0.5 text-xs text-muted">{card.explanation.w1Sentence}</p>{/if}
    {:else if card.trend}
      <p class="mt-1.5 text-xs text-fg-2"><span class="text-muted">movement, focal vs this</span> {card.trend}</p>
    {/if}
    {#if badge && app.econ}
      {#await loadEconUi() then m}
        <div class="mt-1.5"><m.InstrumentBadge econ={app.econ} iso3={e.id} detail={false} /></div>
      {/await}
    {/if}
    {#if thenWhat && app.econ}
      <details class="mt-1.5 text-xs">
        <summary class="cursor-pointer text-muted hover:text-fg">then what happened ▸</summary>
        {#await loadEconUi()}
          <p class="mt-1 text-muted" aria-busy="true">loading…</p>
        {:then m}
          <div class="mt-1.5 rounded-md border border-border bg-surface-2/40 p-2">
            <m.ThenWhat econ={app.econ} iso3={e.id} year={r.year} name={e.short_name} {currentYear} compact />
          </div>
        {/await}
      </details>
    {/if}
  </div>
</article>

<style>
  .band-very_close,
  .band-close {
    border-color: color-mix(in srgb, var(--wa) 60%, transparent);
  }
  .band-far,
  .band-extreme {
    border-color: color-mix(in srgb, var(--u15) 60%, transparent);
  }
</style>
