<script lang="ts">
  // Population pyramid (PLAN §2): 21 rows, bars = sex-bin share of TOTAL population, male left, female right,
  // youngest at the bottom, fixed symmetric axis that never moves while scrubbing. Hand-written SVG.
  // Widths tween over 750 ms (Svelte Tween), 120 ms while the slider is being dragged, 0 under
  // prefers-reduced-motion. Whole-row invisible hit targets drive the persistent Readout strip.
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { N_BINS, N_DIMS } from '../types.ts';
  import type { Unit } from '../router.ts';
  import type { AxisChoice } from '../math/scale.ts';
  import { axisTicks, barLength } from '../math/scale.ts';
  import { barLabel, barPath, rowY, sideValues, tickLabel, UNIT_LABEL } from '../bars.ts';
  import { ageLabel, fmtInt, fmtPct } from '../format.ts';

  interface Props {
    shares: Float32Array; // 42 shares of total
    total: number; // thousands
    axis: AxisChoice;
    unit: Unit;
    name: string;
    year: number;
    selected: number | null; // highlighted bin
    onselect: (k: number) => void;
    fast?: boolean; // dragging → short tween
  }
  let { shares, total, axis, unit, name, year, selected, onselect, fast = false }: Props = $props();

  // ---- geometry (viewBox units) ----
  // On a phone the SVG scales to about half size, which would leave 10-unit labels at ~5 px; below 480 px
  // the compact layout narrows the viewBox and enlarges the type so age and bar-end labels stay legible.
  let width = $state(0); // rendered width in CSS px (bind:clientWidth)
  const compact = $derived(width > 0 && width < 480);
  const W = $derived(compact ? 400 : 640);
  const L = $derived(compact ? 46 : 52); // age labels
  const R = 12;
  const TOP = 30; // sex legend
  const BOTTOM = 28; // axis ticks
  const ROW = $derived(compact ? 22 : 20);
  const BAR = $derived(compact ? 19 : 18); // ≤ 24 px, 2 px surface gap between rows
  const LABEL_ROOM = $derived(compact ? 42 : 44);
  const FS = $derived(compact ? 12 : 10); // label font size (viewBox units)
  const H = $derived(TOP + N_BINS * ROW + BOTTOM);
  const halfFull = $derived((W - L - R) / 2);
  const cx = $derived(L + halfFull);
  const halfBar = $derived(halfFull - LABEL_ROOM);

  // ---- tweened data ----
  const lerp = (a: Float32Array, b: Float32Array) => (t: number) => {
    const o = new Float32Array(N_DIMS);
    for (let i = 0; i < N_DIMS; i++) o[i] = a[i] + (b[i] - a[i]) * t;
    return o;
  };
  // svelte-ignore state_referenced_locally (initial value only; the effect below tracks changes)
  const tw = new Tween<Float32Array>(shares, { duration: 750, easing: cubicOut, interpolate: lerp });
  // svelte-ignore state_referenced_locally
  const twTotal = new Tween(total, { duration: 750, easing: cubicOut });
  $effect(() => {
    const d = prefersReducedMotion.current ? 0 : fast ? 120 : 750;
    void tw.set(shares, { duration: d });
    void twTotal.set(total, { duration: d });
  });

  const drawn = $derived(sideValues(tw.current, twTotal.current, unit));
  const exact = $derived(sideValues(shares, total, unit));
  const ticks = $derived(axisTicks(axis.axisPct));
  const rows = $derived(Array.from({ length: N_BINS }, (_, k) => k));

  function len(pct: number): number {
    return barLength(pct, axis.axisPct, halfBar);
  }
  function over(pct: number): boolean {
    return pct > axis.axisPct + 1e-9;
  }

  const ariaLabel = $derived(
    `Population pyramid of ${name} in ${year}: 21 five-year age bands, male on the left, female on the right, ` +
      `each bar is the share of total population on a fixed 0–${axis.axisPct}% axis. Values are listed in the table that follows.`,
  );

  function onKey(e: KeyboardEvent) {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    e.preventDefault();
    const cur = selected ?? -1;
    const next = e.key === 'ArrowUp' ? Math.min(N_BINS - 1, cur + 1) : Math.max(0, cur - 1);
    onselect(next);
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<!-- (the group is focusable on purpose: ↑/↓ walk the 21 age bands into the readout strip) -->
<div
  class="pyramid"
  role="group"
  aria-label="Population pyramid. Use the up and down arrow keys to read one age band at a time."
  tabindex="0"
  onkeydown={onKey}
  bind:clientWidth={width}
>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label={ariaLabel} class="block h-auto w-full select-none">
    <!-- legend: two series → always present -->
    <g font-size="12" fill="var(--fg-2)">
      <rect x={cx - 92} y="8" width="10" height="10" rx="2" fill="var(--male)" />
      <text x={cx - 78} y="17">Male</text>
      <rect x={cx + 24} y="8" width="10" height="10" rx="2" fill="var(--female)" />
      <text x={cx + 38} y="17">Female</text>
    </g>

    <!-- gridlines + tick labels (hairline, recessive) -->
    <g stroke="var(--grid)" stroke-width="1" shape-rendering="crispEdges">
      {#each ticks as t (t)}
        {#if t > 0}
          <line x1={cx - len(t)} x2={cx - len(t)} y1={TOP} y2={TOP + N_BINS * ROW} />
          <line x1={cx + len(t)} x2={cx + len(t)} y1={TOP} y2={TOP + N_BINS * ROW} />
        {/if}
      {/each}
      <line x1={cx} x2={cx} y1={TOP} y2={TOP + N_BINS * ROW} stroke="var(--axis)" />
    </g>
    <g font-size={FS} fill="var(--muted)" text-anchor="middle" style="font-variant-numeric: tabular-nums">
      {#each ticks as t (t)}
        {#if t > 0}
          <text x={cx - len(t)} y={H - 10}>{tickLabel(t, unit, twTotal.current, drawn.maleShare)}</text>
          <text x={cx + len(t)} y={H - 10}>{tickLabel(t, unit, twTotal.current, drawn.femaleShare)}</text>
        {:else}
          <text x={cx} y={H - 10}>0</text>
        {/if}
      {/each}
    </g>

    <!-- selected row wash -->
    {#if selected !== null}
      <rect x={L - 48} y={rowY(selected, TOP, ROW)} width={W - (L - 48)} height={ROW} fill="var(--fg)" opacity="0.06" rx="3" />
    {/if}

    <!-- bars -->
    {#each rows as k (k)}
      {@const y = rowY(k, TOP, ROW) + (ROW - BAR) / 2}
      {@const m = drawn.male[k]}
      {@const f = drawn.female[k]}
      {@const ml = len(m.pctTotal)}
      {@const fl = len(f.pctTotal)}
      <path d={barPath(cx - 1, y, Math.max(0, ml - 1), BAR, 'left')} fill="var(--male)" />
      <path d={barPath(cx + 1, y, Math.max(0, fl - 1), BAR, 'right')} fill="var(--female)" />
      <text x={L - 6} y={y + BAR / 2 + 3.5} font-size={FS} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">{ageLabel(k)}</text>
      <text x={cx - ml - 5} y={y + BAR / 2 + 3.5} font-size={FS} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">
        {over(m.pctTotal) ? '▸' : ''}{barLabel(m.value, unit)}
      </text>
      <text x={cx + fl + 5} y={y + BAR / 2 + 3.5} font-size={FS} fill="var(--fg-2)" style="font-variant-numeric: tabular-nums">
        {barLabel(f.value, unit)}{over(f.pctTotal) ? '◂' : ''}
      </text>
    {/each}

    <!-- whole-row hit targets (last, on top) -->
    {#each rows as k (k)}
      <rect
        x="0"
        y={rowY(k, TOP, ROW)}
        width={W}
        height={ROW}
        fill="transparent"
        onpointerenter={() => onselect(k)}
        onclick={() => onselect(k)}
        role="presentation"
      />
    {/each}
  </svg>

  {#if axis.clips}
    <p class="mt-1 text-xs text-muted">▸ marks a bar longer than the {axis.axisPct}% axis (clamped). Choose “never clip” in the axis menu to see it in full.</p>
  {/if}

  <!-- accessible twin of the chart -->
  <table class="sr-only">
    <caption>{name}, {year}: population by five-year age band and sex ({UNIT_LABEL[unit]})</caption>
    <thead>
      <tr><th scope="col">Age</th><th scope="col">Male</th><th scope="col">Female</th></tr>
    </thead>
    <tbody>
      {#each rows as k (k)}
        <tr>
          <th scope="row">{ageLabel(k)}</th>
          <td>{unit === 'abs' ? fmtInt(exact.male[k].value) : fmtPct(exact.male[k].value, 2, true)}</td>
          <td>{unit === 'abs' ? fmtInt(exact.female[k].value) : fmtPct(exact.female[k].value, 2, true)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .pyramid {
    border-radius: 8px;
  }
  svg text {
    pointer-events: none;
  }
</style>
