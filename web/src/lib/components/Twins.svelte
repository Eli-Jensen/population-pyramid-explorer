<script lang="ts">
  // "Most similar" section (PLAN §6 J3): k result cards + the own-trajectory row (the entity's closest other
  // year, |Δy| ≥ 5). Loading skeleton while the shards / corpus are on their way; empty state when the
  // constraints leave no candidate.
  import type { SearchOutput } from '../state.svelte.ts';
  import { countryQuery } from '../router.ts';
  import { href } from '../url.ts';
  import { BAND_LABEL, dyLabel, fmtPercentile } from '../restate.ts';
  import ResultCard from './ResultCard.svelte';
  import MiniPyramid from './MiniPyramid.svelte';

  interface Props {
    results: SearchOutput | null;
    k: number;
    focal: { id: string; shares: Float32Array; name: string; year: number };
    loadingText: string | null; // skeleton caption, null when nothing is loading
    lastObserved: number;
    currentYear: number;
  }
  let { results, k, focal, loadingText, lastObserved, currentYear }: Props = $props();
  const skeleton = $derived(Array.from({ length: Math.min(k, 5) }, (_, i) => i));
</script>

<section aria-labelledby="twins-h" class="mt-6">
  <h2 id="twins-h" class="text-base font-semibold tracking-tight">Most similar</h2>
  {#if results}
    {#if results.twins.length === 0}
      <p class="card mt-2 text-sm text-fg-2">No candidate matches these constraints — widen the year window, lower the population floor or include projections.</p>
    {:else}
      <ul class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="{results.twins.length} most similar pyramids">
        {#each results.twins as card (card.result.id + ':' + card.result.year)}
          <li><ResultCard {card} kind="twin" {focal} {lastObserved} {currentYear} /></li>
        {/each}
      </ul>
    {/if}
    {#if results.own}
      {@const own = results.own}
      <p class="mt-3 flex flex-wrap items-center gap-2 text-sm text-fg-2">
        <MiniPyramid shares={own.shares} ghost={focal.shares} size={40} label="{focal.name} {own.year}" />
        <span>
          {focal.name}'s closest other year:
          <a class="font-medium text-fg hover:underline" href={href(countryQuery(focal.id, own.year))}>{own.year} {dyLabel(own.dy)}</a>
        </span>
        <span class="chip">{BAND_LABEL[own.band.label]}{own.band.percentile !== null ? ` · ${fmtPercentile(own.band.percentile)}` : ''}</span>
        <span class="tabular-nums text-muted">d {own.d.toFixed(2)}</span>
        <span class="text-xs text-muted">(years within ±4 skipped)</span>
      </p>
    {/if}
  {:else}
    <ul class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label={loadingText ?? 'loading'}>
      {#each skeleton as i (i)}
        <li class="card flex h-32 animate-pulse gap-3 p-3"><div class="h-26 w-26 rounded bg-surface-2"></div><div class="flex-1 space-y-2"><div class="h-3 w-2/3 rounded bg-surface-2"></div><div class="h-3 w-1/2 rounded bg-surface-2"></div><div class="h-3 w-5/6 rounded bg-surface-2"></div></div></li>
      {/each}
    </ul>
    {#if loadingText}<p class="mt-2 text-xs text-muted">{loadingText}</p>{/if}
  {/if}
</section>
