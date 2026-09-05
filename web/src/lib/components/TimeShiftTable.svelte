<script lang="ts">
  // Time-shift panel (PLAN §6, J5): "{Name} {year} across time" — for every other country in scope the year
  // that best matches the focal pyramid, Δy, d and the band against the `best` null. Collapsed <details>;
  // opening fetches the corpus (tier 3) once. First 10 rows + "show all"; a best year sitting on the era edge
  // reads "not reached by {year}" instead of posing as a match. Rows link to /{slug}/{year} (compare is M3).
  import type { TimeShiftRow } from '../engine.ts';
  import type { CorpusStatus } from '../state.svelte.ts';
  import { byId, flagEmoji } from '../entities.ts';
  import { countryQuery } from '../router.ts';
  import { href } from '../url.ts';
  import { BAND_LABEL, dyLabel } from '../restate.ts';

  interface Props {
    rows: TimeShiftRow[] | null;
    open: boolean;
    ontoggle: (open: boolean) => void;
    status: CorpusStatus;
    error: string | null;
    focal: { name: string; year: number };
    eraEdge: number; // upper edge of the allowed years (2026 for observed, 2100 for all)
    corpusBytes: number;
  }
  let { rows, open, ontoggle, status, error, focal, eraEdge, corpusBytes }: Props = $props();

  let showAll = $state(false);
  const visible = $derived(rows ? (showAll ? rows : rows.slice(0, 10)) : []);
  const mb = $derived((corpusBytes / 1e6).toFixed(1));

  function edgeNote(r: TimeShiftRow): string | null {
    if (!r.boundaryHit || r.bestYear === focal.year) return null;
    return r.bestYear >= eraEdge ? `not reached by ${r.bestYear}` : `not reached before ${r.bestYear}`;
  }
</script>

<details class="card mt-8 p-0" {open} ontoggle={(e) => ontoggle((e.currentTarget as HTMLDetailsElement).open)}>
  <summary class="cursor-pointer px-4 py-3 text-base font-semibold tracking-tight">
    {focal.name} {focal.year} across time
    <span class="ml-2 text-xs font-normal text-muted">which year of every other country looks most like this one</span>
  </summary>
  <div class="border-t border-border px-4 py-3">
    {#if status === 'error'}
      <p class="text-sm text-fg-2" role="alert">Could not load the corpus: {error}</p>
    {:else if !rows}
      <p class="text-sm text-muted" aria-busy="true">loading all years… {mb} MB</p>
    {:else if rows.length === 0}
      <p class="text-sm text-fg-2">No other country in scope.</p>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-xs text-muted">
            <tr><th scope="col" class="py-1 pr-3 font-medium">Country</th><th scope="col" class="py-1 pr-3 font-medium">Best year</th><th scope="col" class="py-1 pr-3 font-medium">Δy</th><th scope="col" class="py-1 pr-3 font-medium">d</th><th scope="col" class="py-1 font-medium">Band</th></tr>
          </thead>
          <tbody>
            {#each visible as r (r.id)}
              {@const e = byId(r.id)}
              {@const note = edgeNote(r)}
              <tr class="border-t border-border">
                <td class="py-1 pr-3"><span class="inline-block w-5" aria-hidden="true">{e ? flagEmoji(e) : ''}</span><a class="hover:underline" href={href(countryQuery(r.id, r.bestYear))}>{e?.short_name ?? r.id}</a></td>
                <td class="py-1 pr-3 tabular-nums">{#if note}<span class="text-muted" title="the best match sits on the edge of the allowed years — the true best may lie beyond">{note}</span>{:else}{r.bestYear}{/if}</td>
                <td class="py-1 pr-3 tabular-nums text-fg-2">{r.dy === 0 ? '±0 y' : dyLabel(r.dy).slice(1, -1)}</td>
                <td class="py-1 pr-3 tabular-nums">{r.d.toFixed(3)}</td>
                <td class="py-1"><span class="chip">{BAND_LABEL[r.band]}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if rows.length > 10}
        <button type="button" class="btn mt-2" onclick={() => (showAll = !showAll)} aria-expanded={showAll}>
          {showAll ? 'show first 10' : `show all ${rows.length}`}
        </button>
      {/if}
    {/if}
  </div>
</details>
