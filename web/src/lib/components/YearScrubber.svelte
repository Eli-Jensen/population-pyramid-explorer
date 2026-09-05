<script lang="ts">
  // Year navigation (PLAN §2/§7): real <input type=range> 1950–2100, play at 6 yr/s (1×/2×/4×), ←/→ ±1 and
  // ⇧ ±5, ±1/±5 buttons, decade ticks, shaded projection zone, "today" tick, median-age sparkline under the
  // track, aria-valuetext, a polite live region throttled to ≤ 2/s. `oninput` = replaceState while dragging /
  // playing, `oncommit` = one pushState on release / step / pause (the store owns history).
  import { onDestroy } from 'svelte';
  import { prefersReducedMotion } from 'svelte/motion';
  import { YEAR_MAX, YEAR_MIN } from '../types.ts';
  import { eraOf } from '../entities.ts';
  import { fmtYears } from '../format.ts';

  interface Props {
    year: number;
    currentYear: number;
    lastObserved: number;
    median?: Float32Array | null; // 151 values for the sparkline
    oninput: (year: number) => void;
    oncommit: (year: number) => void;
    id?: string; // element id of the range input (two scrubbers on the compare page need distinct ids)
    label?: string; // aria-label of the group + input ('Year', 'Year of A: South Korea')
  }
  let { year, currentYear, lastObserved, median = null, oninput, oncommit, id = 'year-range', label = 'Year' }: Props = $props();

  const N = YEAR_MAX - YEAR_MIN; // 150 steps
  const pos = (y: number) => ((y - YEAR_MIN) / N) * 100; // percent along the track

  const era = $derived(eraOf(year, currentYear, lastObserved));
  const valueText = $derived(`${year}${era === 'observed' ? '' : era === 'nowcast' ? ', nowcast' : ', projected'}`);

  // ---- live region, ≤ 2 announcements per second ----
  let live = $state('');
  let liveTimer: ReturnType<typeof setTimeout> | null = null;
  let livePending = '';
  $effect(() => {
    livePending = `Year ${valueText}`;
    if (liveTimer) return;
    liveTimer = setTimeout(() => {
      live = livePending;
      liveTimer = null;
    }, 500);
  });

  // ---- play ----
  let playing = $state(false);
  let speed = $state<1 | 2 | 4>(1);
  let timer: ReturnType<typeof setInterval> | null = null;
  // svelte-ignore state_referenced_locally (re-seeded from `year` whenever play starts)
  let playYear = year;
  const reduced = $derived(prefersReducedMotion.current);

  function stop(commit = true) {
    if (timer) clearInterval(timer);
    timer = null;
    if (playing) {
      playing = false;
      if (commit) oncommit(playYear);
    }
  }
  function start() {
    if (reduced) return;
    stop(false);
    playing = true;
    playYear = year >= YEAR_MAX ? YEAR_MIN : year;
    if (playYear !== year) oninput(playYear);
    timer = setInterval(() => {
      if (playYear >= YEAR_MAX) {
        stop();
        return;
      }
      playYear += 1;
      oninput(playYear);
    }, 1000 / (6 * speed));
  }
  function restartIfPlaying() {
    if (playing) {
      const y = playYear;
      stop(false);
      playing = true;
      playYear = y;
      timer = setInterval(() => {
        if (playYear >= YEAR_MAX) {
          stop();
          return;
        }
        playYear += 1;
        oninput(playYear);
      }, 1000 / (6 * speed));
    }
  }
  onDestroy(() => {
    if (timer) clearInterval(timer);
    if (liveTimer) clearTimeout(liveTimer);
  });

  function step(d: number) {
    stop(false);
    oncommit(Math.min(YEAR_MAX, Math.max(YEAR_MIN, year + d)));
  }
  function onRangeInput(e: Event) {
    stop(false);
    oninput(Number((e.target as HTMLInputElement).value));
  }
  function onRangeChange(e: Event) {
    oncommit(Number((e.target as HTMLInputElement).value));
  }
  function onRangeKey(e: KeyboardEvent) {
    if (e.shiftKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault();
      step(e.key === 'ArrowRight' ? 5 : -5);
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault();
      step(e.key === 'Home' ? YEAR_MIN - year : YEAR_MAX - year);
    }
  }

  // ---- sparkline (median age) ----
  const spark = $derived.by(() => {
    if (!median || median.length !== N + 1) return null;
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = 0; i <= N; i++) {
      if (median[i] < lo) lo = median[i];
      if (median[i] > hi) hi = median[i];
    }
    const span = hi - lo || 1;
    let d = '';
    for (let i = 0; i <= N; i++) {
      const px = (i / N) * 100;
      const py = 2 + (1 - (median[i] - lo) / span) * 26;
      d += `${i ? 'L' : 'M'}${px.toFixed(2)} ${py.toFixed(2)}`;
    }
    return { d, lo, hi };
  });
  const decades = Array.from({ length: 16 }, (_, i) => YEAR_MIN + i * 10);
</script>

<div class="scrubber select-none" role="group" aria-label={label}>
  <div class="flex flex-wrap items-center gap-2">
    <button
      type="button"
      class="btn"
      onclick={() => (playing ? stop() : start())}
      aria-pressed={playing}
      aria-label={playing ? 'Pause' : 'Play through the years'}
      disabled={reduced}
      title={reduced ? 'Play is off because your system prefers reduced motion' : playing ? 'Pause' : 'Play (6 years per second)'}
    >
      {playing ? '❚❚' : '▶'}
    </button>
    <div class="seg" role="group" aria-label="Play speed">
      {#each [1, 2, 4] as const as s (s)}
        <button type="button" aria-pressed={speed === s} onclick={() => { speed = s; restartIfPlaying(); }}>{s}×</button>
      {/each}
    </div>
    <div class="ml-auto flex items-center gap-1">
      <button type="button" class="btn" onclick={() => step(-5)} aria-label="Back 5 years" disabled={year <= YEAR_MIN}>−5</button>
      <button type="button" class="btn" onclick={() => step(-1)} aria-label="Back 1 year" disabled={year <= YEAR_MIN}>−1</button>
      <output class="min-w-14 text-center text-lg font-semibold tabular-nums" for={id} aria-live="off">{year}</output>
      <button type="button" class="btn" onclick={() => step(1)} aria-label="Forward 1 year" disabled={year >= YEAR_MAX}>+1</button>
      <button type="button" class="btn" onclick={() => step(5)} aria-label="Forward 5 years" disabled={year >= YEAR_MAX}>+5</button>
    </div>
  </div>

  <div class="track relative mt-2 px-2">
    <!-- zones + ticks behind the input; the 8 px side padding matches the thumb's half-width -->
    <div class="pointer-events-none absolute inset-x-2 top-0 h-7" aria-hidden="true">
      <div class="absolute top-[12px] h-1 rounded-r bg-[var(--proj)]" style="left: {pos(lastObserved)}%; right: 0"></div>
      <div class="absolute top-[6px] h-4 w-px bg-fg opacity-60" style="left: {pos(currentYear)}%" title="today"></div>
      {#each decades as d (d)}
        <div class="absolute top-[18px] h-1.5 w-px bg-axis" style="left: {pos(d)}%"></div>
      {/each}
    </div>
    <input
      {id}
      class="scrub relative"
      type="range"
      min={YEAR_MIN}
      max={YEAR_MAX}
      step="1"
      value={year}
      aria-label={label}
      aria-valuetext={valueText}
      oninput={onRangeInput}
      onchange={onRangeChange}
      onkeydown={onRangeKey}
      onpointerdown={() => stop(false)}
    />
    <!-- sparkline + labels -->
    <div class="relative mt-0.5 h-8" aria-hidden="true">
      {#if spark}
        <svg viewBox="0 0 100 30" preserveAspectRatio="none" class="absolute inset-0 h-full w-full overflow-visible">
          <rect x={pos(lastObserved)} y="0" width={100 - pos(lastObserved)} height="30" fill="var(--proj)" />
          <path d={spark.d} fill="none" stroke="var(--fg-2)" stroke-width="1.5" vector-effect="non-scaling-stroke" />
          <line x1={pos(year)} x2={pos(year)} y1="0" y2="30" stroke="var(--accent)" stroke-width="1" vector-effect="non-scaling-stroke" />
        </svg>
      {/if}
    </div>
    <div class="relative mt-0.5 h-4 text-[10px] text-muted tabular-nums" aria-hidden="true">
      {#each [1950, 1975, 2000, 2025, 2050, 2075, 2100] as y (y)}
        <span class="absolute -translate-x-1/2" style="left: {pos(y)}%">{y}</span>
      {/each}
    </div>
  </div>
  <div class="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
    <span>
      {#if spark}median age {fmtYears(spark.lo)}–{fmtYears(spark.hi)} across 1950–2100 (sparkline) · {/if}
      shaded = UN projections (after {lastObserved}) · | = today
    </span>
    <span class="chip">{era}</span>
  </div>
  <div class="sr-only" aria-live="polite">{live}</div>
</div>
