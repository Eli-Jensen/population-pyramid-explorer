<script lang="ts">
  // "Most different" section (PLAN §5): headline against the random-pair null, diversified farthest-k cards
  // with their raw ranks, and a faint 'strictly farthest: …' strip whenever diversity changed the list.
  import type { SearchOutput } from '../state.svelte.ts';
  import { byId } from '../entities.ts';
  import { divLabel, oppositesHeadline, strictStrip } from '../restate.ts';
  import type { Div, Metric, Sex } from '../router.ts';
  import ResultCard from './ResultCard.svelte';

  interface Props {
    results: SearchOutput | null;
    k: number;
    div: Div;
    focal: { id: string; shares: Float32Array; name: string; year: number; metric?: Metric; sex?: Sex };
    loadingText: string | null;
    lastObserved: number;
    currentYear: number;
  }
  let { results, k, div, focal, loadingText, lastObserved, currentYear }: Props = $props();

  const first = $derived(results?.opposites[0] ?? null);
  const headline = $derived(
    results && first
      ? oppositesHeadline({ name: focal.name, year: results.q.year }, { name: first.entity.short_name, year: first.result.year }, first.result.percentile, results.nCandidates)
      : null,
  );
  const strip = $derived(
    results
      ? strictStrip(
          results.opposites.map((c) => c.result.id),
          results.strict.map((r) => byId(r.id)?.short_name ?? r.id),
        )
      : null,
  );
  // strictStrip compares ids to names on purpose only when the lists differ; recompute the id-level check here
  const differs = $derived(results ? results.strict.some((r, i) => results.opposites[i]?.result.id !== r.id) || results.strict.length !== results.opposites.length : false);
  const skeleton = $derived(Array.from({ length: Math.min(k, 5) }, (_, i) => i));
</script>

<section aria-labelledby="opp-h" class="mt-8">
  <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
    <h2 id="opp-h" class="text-base font-semibold tracking-tight">Most different</h2>
    <span class="text-xs text-muted" title="Diversity is over shape distance only: the farthest quartile of an old anchor is entirely young pyramids, so no preset yields regional variety.">
      {divLabel(div)} · farthest under the active metric, nudged apart
    </span>
  </div>
  {#if results}
    {#if headline}<p class="mt-1 text-sm text-fg-2">{headline}</p>{/if}
    {#if results.opposites.length === 0}
      <p class="card mt-2 text-sm text-fg-2">No candidate matches these constraints.</p>
    {:else}
      <ul class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="{results.opposites.length} most different pyramids">
        {#each results.opposites as card (card.result.id + ':' + card.result.year)}
          <li><ResultCard {card} kind="opposite" {focal} {lastObserved} {currentYear} /></li>
        {/each}
      </ul>
      {#if differs && strip}
        <p class="mt-2 text-xs text-muted" title="the plain farthest-k under the active metric, before the diversity nudge">{strip}</p>
      {/if}
    {/if}
  {:else}
    <ul class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label={loadingText ?? 'loading'}>
      {#each skeleton as i (i)}
        <li class="card flex h-32 animate-pulse gap-3 p-3"><div class="h-26 w-26 rounded bg-surface-2"></div><div class="flex-1 space-y-2"><div class="h-3 w-2/3 rounded bg-surface-2"></div><div class="h-3 w-1/2 rounded bg-surface-2"></div><div class="h-3 w-5/6 rounded bg-surface-2"></div></div></li>
      {/each}
    </ul>
  {/if}
</section>
