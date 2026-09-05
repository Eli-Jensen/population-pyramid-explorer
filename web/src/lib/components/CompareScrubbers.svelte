<script lang="ts">
  // Two year scrubbers (PLAN §7 J4): one per side, reusing the M1 YearScrubber, with a lock-offset toggle that
  // moves both years together (Δ = yb − ya kept; the store does the arithmetic via lib/compare.ts). While B's
  // year is still `best` (unresolved) its scrubber is replaced by a caption.
  import YearScrubber from './YearScrubber.svelte';
  import { dyText } from '../compare.ts';

  interface SideYears {
    name: string;
    year: number | null; // null = unresolved `best`
    median?: Float32Array | null;
  }
  interface Props {
    a: SideYears & { year: number };
    b: SideYears;
    currentYear: number;
    lastObserved: number;
    lock: boolean;
    onlock: (on: boolean) => void;
    oninput: (side: 'a' | 'b', year: number) => void;
    oncommit: (side: 'a' | 'b', year: number) => void;
    resolving?: string | null; // caption shown in place of B's scrubber
  }
  let { a, b, currentYear, lastObserved, lock, onlock, oninput, oncommit, resolving = null }: Props = $props();

  const offset = $derived(b.year === null ? null : b.year - a.year);
</script>

<div class="grid gap-3 lg:grid-cols-2" role="group" aria-label="Years of the two pyramids">
  <div class="card">
    <p class="mb-1 flex items-baseline gap-2 text-sm">
      <span class="chip font-mono">A</span>
      <span class="font-medium">{a.name}</span>
      <span class="ml-auto text-xs text-muted">filled</span>
    </p>
    <YearScrubber
      id="year-a"
      label="Year of A: {a.name}"
      year={a.year}
      {currentYear}
      {lastObserved}
      median={a.median ?? null}
      oninput={(y) => oninput('a', y)}
      oncommit={(y) => oncommit('a', y)}
    />
  </div>
  <div class="card">
    <p class="mb-1 flex flex-wrap items-baseline gap-2 text-sm">
      <span class="chip font-mono">B</span>
      <span class="font-medium">{b.name}</span>
      <button
        type="button"
        class="btn ml-auto text-xs"
        aria-pressed={lock}
        onclick={() => onlock(!lock)}
        disabled={offset === null}
        title={offset === null ? 'available once B has a year' : lock ? 'Moving either year moves both (offset kept)' : 'Lock the offset so both years move together'}
      >
        {lock ? '🔒' : '🔓'} lock offset{offset !== null ? ` ${offset === 0 ? '(±0 y)' : dyText(offset)}` : ''}
      </button>
      <span class="text-xs text-muted">dashed outline</span>
    </p>
    {#if b.year !== null}
      <YearScrubber
        id="year-b"
        label="Year of B: {b.name}"
        year={b.year}
        {currentYear}
        {lastObserved}
        median={b.median ?? null}
        oninput={(y) => oninput('b', y)}
        oncommit={(y) => oncommit('b', y)}
      />
    {:else}
      <p class="py-6 text-center text-sm text-muted" aria-busy="true">{resolving ?? 'resolving the best year…'}</p>
    {/if}
  </div>
</div>
