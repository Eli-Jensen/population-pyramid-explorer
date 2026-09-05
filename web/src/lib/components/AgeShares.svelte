<script lang="ts">
  // Age-shares mini chart 1950–2100: three lines (<15, 15–64, 65+) from the entity shard, current-year
  // marker, shaded projection zone, crosshair tooltip listing all three series, click to jump to a year.
  import { YEAR_MAX, YEAR_MIN } from '../types.ts';
  import type { EntitySeries } from '../series.ts';
  import { fmtPct } from '../format.ts';

  interface Props {
    series: EntitySeries;
    year: number;
    currentYear: number;
    lastObserved: number;
    onpick?: (year: number) => void;
  }
  let { series, year, currentYear, lastObserved, onpick }: Props = $props();

  const W = 320;
  const H = 150;
  const L = 30;
  const R = 8;
  const T = 8;
  const B = 20;
  const n = $derived(series.years.length);
  const x = (y: number) => L + ((y - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)) * (W - L - R);
  const yy = (v: number) => T + (1 - v) * (H - T - B);

  function path(vals: Float32Array): string {
    let d = '';
    for (let i = 0; i < n; i++) d += `${i ? 'L' : 'M'}${x(YEAR_MIN + i).toFixed(1)} ${yy(vals[i]).toFixed(1)}`;
    return d;
  }
  const lines = $derived([
    { key: 'u15', label: 'Under 15', color: 'var(--u15)', d: path(series.u15), vals: series.u15 },
    { key: 'wa', label: '15–64', color: 'var(--wa)', d: path(series.wa), vals: series.wa },
    { key: 'o65', label: '65+', color: 'var(--o65)', d: path(series.o65), vals: series.o65 },
  ]);

  let hover = $state<number | null>(null); // hovered year
  const shown = $derived(hover ?? year);
  const idx = $derived(shown - YEAR_MIN);

  let svgEl: SVGSVGElement | undefined = $state();
  function yearAt(e: MouseEvent): number {
    const rect = svgEl!.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const y = Math.round(YEAR_MIN + ((px - L) / (W - L - R)) * (YEAR_MAX - YEAR_MIN));
    return Math.min(YEAR_MAX, Math.max(YEAR_MIN, y));
  }
  const decades = Array.from({ length: 4 }, (_, i) => 1950 + i * 50);
  const yTicks = [0, 0.25, 0.5, 0.75, 1];
  const tipLeft = $derived(x(shown) > W * 0.6);
</script>

<section class="card" aria-label="Age shares 1950–2100">
  <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-xs font-medium uppercase tracking-wide text-muted">Age shares 1950–2100</h2>
    <ul class="flex gap-3 text-xs text-fg-2" aria-label="Series">
      {#each lines as l (l.key)}
        <li class="flex items-center gap-1.5"><span class="inline-block h-0.5 w-3 rounded" style="background: {l.color}"></span>{l.label}</li>
      {/each}
    </ul>
  </div>

  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
  <!-- (click-to-jump is a pointer convenience; the year is keyboard-reachable through the scrubber) -->
  <svg
    bind:this={svgEl}
    viewBox="0 0 {W} {H}"
    class="mt-2 block h-auto w-full cursor-crosshair touch-none select-none"
    role="img"
    aria-label="Three lines: share of population under 15, 15 to 64, and 65 and over, from 1950 to 2100. In {shown}: under 15 {fmtPct(series.u15[idx], 0)}, 15 to 64 {fmtPct(series.wa[idx], 0)}, 65 and over {fmtPct(series.o65[idx], 0)}."
    onpointermove={(e) => (hover = yearAt(e))}
    onpointerleave={() => (hover = null)}
    onclick={(e) => onpick?.(yearAt(e))}
  >
    <!-- projection zone -->
    <rect x={x(lastObserved)} y={T} width={x(YEAR_MAX) - x(lastObserved)} height={H - T - B} fill="var(--proj)" />
    <!-- gridlines -->
    <g stroke="var(--grid)" stroke-width="1" shape-rendering="crispEdges">
      {#each yTicks as t (t)}
        <line x1={L} x2={W - R} y1={yy(t)} y2={yy(t)} />
      {/each}
    </g>
    <g font-size="9" fill="var(--muted)" style="font-variant-numeric: tabular-nums">
      {#each yTicks as t (t)}
        <text x={L - 4} y={yy(t) + 3} text-anchor="end">{t * 100}%</text>
      {/each}
      {#each decades as d (d)}
        <text x={x(d)} y={H - 6} text-anchor={d === YEAR_MIN ? 'start' : d === YEAR_MAX ? 'end' : 'middle'}>{d}</text>
      {/each}
    </g>
    <!-- today tick -->
    <line x1={x(currentYear)} x2={x(currentYear)} y1={T} y2={H - B} stroke="var(--axis)" stroke-width="1" stroke-dasharray="2 2" />
    <!-- lines -->
    {#each lines as l (l.key)}
      <path d={l.d} fill="none" stroke={l.color} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    {/each}
    <!-- crosshair at shown year -->
    <line x1={x(shown)} x2={x(shown)} y1={T} y2={H - B} stroke="var(--fg)" stroke-width="1" opacity={hover === null ? 0.35 : 0.6} />
    {#each lines as l (l.key)}
      <circle cx={x(shown)} cy={yy(l.vals[idx])} r="4" fill={l.color} stroke="var(--surface)" stroke-width="2" />
    {/each}
    <!-- tooltip -->
    <g transform="translate({tipLeft ? x(shown) - 98 : x(shown) + 8}, {T + 2})" font-size="10" style="font-variant-numeric: tabular-nums">
      <rect width="90" height="54" rx="4" fill="var(--surface)" stroke="var(--border)" />
      <text x="6" y="12" fill="var(--fg-2)">{shown}{shown > currentYear ? ' · projected' : shown > lastObserved ? ' · nowcast' : ''}</text>
      {#each lines as l, i (l.key)}
        <line x1="6" x2="14" y1={24 + i * 13} y2={24 + i * 13} stroke={l.color} stroke-width="2" />
        <text x="18" y={27 + i * 13} fill="var(--fg)" font-weight="600">{fmtPct(l.vals[idx], 0)}</text>
        <text x="48" y={27 + i * 13} fill="var(--fg-2)">{l.label}</text>
      {/each}
    </g>
  </svg>
  <p class="mt-1 text-xs text-muted">Hover for values · click to jump to that year · shaded = projected.</p>

  <details class="mt-1 text-xs">
    <summary class="cursor-pointer text-muted">Table (every 10 years)</summary>
    <table class="mt-1 w-full text-left tabular-nums">
      <thead><tr class="text-muted"><th class="py-0.5 font-medium">Year</th><th class="font-medium">Under 15</th><th class="font-medium">15–64</th><th class="font-medium">65+</th></tr></thead>
      <tbody>
        {#each Array.from({ length: 16 }, (_, i) => YEAR_MIN + i * 10) as y (y)}
          <tr><th scope="row" class="py-0.5 font-normal">{y}</th><td>{fmtPct(series.u15[y - YEAR_MIN])}</td><td>{fmtPct(series.wa[y - YEAR_MIN])}</td><td>{fmtPct(series.o65[y - YEAR_MIN])}</td></tr>
        {/each}
      </tbody>
    </table>
  </details>
</section>
