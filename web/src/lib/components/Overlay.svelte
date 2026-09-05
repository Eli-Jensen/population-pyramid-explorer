<script lang="ts">
  // Two pyramids on one fixed axis (PLAN §7 J4): A filled, B as a dashed outline; `diff` = signed per-bin
  // difference bars B − A (percentage points of total) around a zero line per sex; `side` = the two pyramids
  // side by side on the same axis. Hand-written SVG with the country page's geometry (21 rows, male left, female
  // right, youngest at the bottom); widths tween like Pyramid.svelte (120 ms while a scrubber is dragged, 0 under
  // prefers-reduced-motion). One <svg> for every view so the export menu always has a single element to read.
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { N_BINS, N_DIMS } from '../types.ts';
  import type { CompareView, Unit } from '../router.ts';
  import type { AxisChoice } from '../math/scale.ts';
  import { axisTicks, barLength } from '../math/scale.ts';
  import { barLabel, barPath, rowY, sideValues, tickLabel, UNIT_LABEL } from '../bars.ts';
  import { ageLabel, fmtInt, fmtPct } from '../format.ts';

  export interface Side {
    shares: Float32Array; // 42 shares of total
    total: number; // thousands
    name: string;
    year: number;
  }
  interface Props {
    a: Side;
    b: Side | null; // null while `best` is unresolved → A alone, B's outline pending
    axis: AxisChoice;
    unit: Unit;
    view: CompareView;
    fast?: boolean;
    /** The live <svg> (for the export menu). */
    svg?: SVGSVGElement | null;
  }
  let { a, b, axis, unit, view, fast = false, svg = $bindable(null) }: Props = $props();

  // ---- geometry (viewBox units; the compact layout mirrors Pyramid.svelte) ----
  let width = $state(0);
  const compact = $derived(width > 0 && width < 480);
  const W = $derived(compact ? 400 : 640);
  const L = $derived(compact ? 46 : 52);
  const R = 12;
  const TOP = 34;
  const BOTTOM = 28;
  const ROW = $derived(compact ? 22 : 20);
  const BAR = $derived(compact ? 19 : 18);
  const FS = $derived(compact ? 12 : 10);
  const H = $derived(TOP + N_BINS * ROW + BOTTOM);
  const rows = Array.from({ length: N_BINS }, (_, k) => k);

  // ---- tweened shares ----
  const lerp = (x: Float32Array, y: Float32Array) => (t: number) => {
    const o = new Float32Array(N_DIMS);
    for (let i = 0; i < N_DIMS; i++) o[i] = x[i] + (y[i] - x[i]) * t;
    return o;
  };
  // svelte-ignore state_referenced_locally (initial values only; the effect tracks changes)
  const twA = new Tween<Float32Array>(a.shares, { duration: 750, easing: cubicOut, interpolate: lerp });
  // svelte-ignore state_referenced_locally
  const twB = new Tween<Float32Array>(b?.shares ?? a.shares, { duration: 750, easing: cubicOut, interpolate: lerp });
  $effect(() => {
    const d = prefersReducedMotion.current ? 0 : fast ? 120 : 750;
    void twA.set(a.shares, { duration: d });
    if (b) void twB.set(b.shares, { duration: d });
  });
  const drawnA = $derived(sideValues(twA.current, a.total, unit));
  const drawnB = $derived(b ? sideValues(twB.current, b.total, unit) : null);
  const exactA = $derived(sideValues(a.shares, a.total, unit));
  const exactB = $derived(b ? sideValues(b.shares, b.total, unit) : null);
  const ticks = $derived(axisTicks(axis.axisPct));

  // ---- overlay / side: one pyramid drawn inside [x0, x0 + w) ----
  interface Frame {
    x0: number;
    w: number;
    lab: number; // label gutter on the left
    labelRoom: number;
  }
  const full = $derived<Frame>({ x0: 0, w: W, lab: L, labelRoom: compact ? 42 : 44 });
  const half = (i: 0 | 1): Frame => ({ x0: i * (W / 2), w: W / 2, lab: compact ? 40 : 44, labelRoom: compact ? 30 : 34 });
  const cxOf = (f: Frame) => f.x0 + f.lab + (f.w - f.lab - R) / 2;
  const halfBarOf = (f: Frame) => (f.w - f.lab - R) / 2 - f.labelRoom;
  const len = (f: Frame, pct: number) => barLength(pct, axis.axisPct, halfBarOf(f));

  // ---- diff: B − A in percentage points of total, one column per sex ----
  const diff = $derived.by(() => {
    if (!drawnB) return null;
    const m = new Float64Array(N_BINS);
    const f = new Float64Array(N_BINS);
    let max = 0;
    for (let k = 0; k < N_BINS; k++) {
      m[k] = drawnB.male[k].pctTotal - drawnA.male[k].pctTotal;
      f[k] = drawnB.female[k].pctTotal - drawnA.female[k].pctTotal;
      max = Math.max(max, Math.abs(m[k]), Math.abs(f[k]));
    }
    // axis = a round number of percentage points (0.5 steps, at least 0.5)
    const span = Math.max(0.5, Math.ceil(max * 2) / 2);
    return { m, f, span };
  });
  const exactDiff = $derived.by(() => {
    if (!exactB) return null;
    return rows.map((k) => ({ m: exactB.male[k].pctTotal - exactA.male[k].pctTotal, f: exactB.female[k].pctTotal - exactA.female[k].pctTotal }));
  });
  const colW = $derived((W - L - R - 16) / 2); // two columns with a 16-unit gap
  const cxM = $derived(L + colW / 2);
  const cxF = $derived(L + colW + 16 + colW / 2);
  const dLen = (v: number) => (diff ? (Math.abs(v) / diff.span) * (colW / 2 - 26) : 0);
  const signed = (v: number) => (v === 0 ? '±0.0' : `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(v < 0.05 && v > -0.05 ? 2 : 1)}`);

  const legendA = $derived(`${a.name} ${a.year}`);
  const legendB = $derived(b ? `${b.name} ${b.year}` : 'B (resolving best year…)');
  const ariaLabel = $derived.by(() => {
    const scale = `fixed 0–${axis.axisPct}% axis, share of each pyramid's total population`;
    if (view === 'diff') return `Difference chart: ${legendB} minus ${legendA}, percentage points of total population per five-year age band, male left column, female right column. Values are in the table that follows.`;
    if (view === 'side') return `Two population pyramids side by side on a ${scale}: ${legendA} on the left, ${legendB} on the right. Values are in the table that follows.`;
    return `Overlay of two population pyramids on a ${scale}: ${legendA} filled, ${legendB} as a dashed outline. Values are in the table that follows.`;
  });
</script>

<div class="overlay" bind:clientWidth={width}>
  <svg bind:this={svg} viewBox="0 0 {W} {H}" role="img" aria-label={ariaLabel} class="block h-auto w-full select-none" data-view={view}>
    <!-- legend -->
    <g font-size="12" fill="var(--fg-2)">
      {#if view === 'diff'}
        <rect x={L} y="8" width="10" height="10" rx="2" fill="var(--accent)" />
        <text x={L + 14} y="17">B larger ({legendB})</text>
        <rect x={L + 190} y="8" width="10" height="10" rx="2" fill="var(--u15)" />
        <text x={L + 204} y="17">A larger ({legendA})</text>
      {:else}
        <rect x={L} y="8" width="10" height="10" rx="2" fill="var(--male)" fill-opacity="0.85" />
        <rect x={L + 6} y="8" width="10" height="10" rx="2" fill="var(--female)" fill-opacity="0.85" />
        <text x={L + 20} y="17">A · {legendA}</text>
        <rect x={L + 230} y="8" width="16" height="10" rx="2" fill="none" stroke="var(--fg)" stroke-width="1.5" stroke-dasharray="3 2" />
        <text x={L + 250} y="17">B · {legendB}</text>
      {/if}
    </g>

    {#if view === 'diff'}
      {#if diff}
        <!-- zero lines + ticks per column -->
        <g stroke="var(--grid)" stroke-width="1" shape-rendering="crispEdges">
          {#each [cxM, cxF] as cx (cx)}
            <line x1={cx - dLen(diff.span)} x2={cx - dLen(diff.span)} y1={TOP} y2={TOP + N_BINS * ROW} />
            <line x1={cx + dLen(diff.span)} x2={cx + dLen(diff.span)} y1={TOP} y2={TOP + N_BINS * ROW} />
            <line x1={cx} x2={cx} y1={TOP} y2={TOP + N_BINS * ROW} stroke="var(--axis)" />
          {/each}
        </g>
        <g font-size={FS} fill="var(--muted)" text-anchor="middle" style="font-variant-numeric: tabular-nums">
          {#each [cxM, cxF] as cx (cx)}
            <text x={cx - dLen(diff.span)} y={H - 10}>−{diff.span}</text>
            <text x={cx} y={H - 10}>0</text>
            <text x={cx + dLen(diff.span)} y={H - 10}>+{diff.span}</text>
          {/each}
          <text x={cxM} y={TOP - 4} fill="var(--fg-2)">Male, pp of total</text>
          <text x={cxF} y={TOP - 4} fill="var(--fg-2)">Female, pp of total</text>
        </g>
        {#each rows as k (k)}
          {@const y = rowY(k, TOP, ROW) + (ROW - BAR) / 2}
          {@const dm = diff.m[k]}
          {@const df = diff.f[k]}
          <text x={L - 6} y={y + BAR / 2 + 3.5} font-size={FS} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">{ageLabel(k)}</text>
          {#each [[cxM, dm], [cxF, df]] as [cx, v] (cx)}
            <path d={barPath(v >= 0 ? cx : cx, y, dLen(v), BAR, v >= 0 ? 'right' : 'left')} fill={v >= 0 ? 'var(--accent)' : 'var(--u15)'} fill-opacity="0.85" />
            <text
              x={v >= 0 ? cx + dLen(v) + 4 : cx - dLen(v) - 4}
              y={y + BAR / 2 + 3.5}
              font-size={FS - 1}
              fill="var(--fg-2)"
              text-anchor={v >= 0 ? 'start' : 'end'}
              style="font-variant-numeric: tabular-nums">{signed(v)}</text
            >
          {/each}
        {/each}
      {:else}
        <text x={W / 2} y={H / 2} text-anchor="middle" font-size="13" fill="var(--muted)">B is still being resolved…</text>
      {/if}
    {:else}
      {#snippet pyramid(f: Frame, sideA: typeof drawnA, sideB: typeof drawnB, mode: 'overlay' | 'a' | 'b', title: string | null)}
        {@const cx = cxOf(f)}
        <!-- gridlines + ticks -->
        <g stroke="var(--grid)" stroke-width="1" shape-rendering="crispEdges">
          {#each ticks as t (t)}
            {#if t > 0}
              <line x1={cx - len(f, t)} x2={cx - len(f, t)} y1={TOP} y2={TOP + N_BINS * ROW} />
              <line x1={cx + len(f, t)} x2={cx + len(f, t)} y1={TOP} y2={TOP + N_BINS * ROW} />
            {/if}
          {/each}
          <line x1={cx} x2={cx} y1={TOP} y2={TOP + N_BINS * ROW} stroke="var(--axis)" />
        </g>
        <g font-size={FS} fill="var(--muted)" text-anchor="middle" style="font-variant-numeric: tabular-nums">
          {#each ticks as t (t)}
            {#if t > 0}
              <!-- overlay: two totals → ticks stay in % of total; side: each pyramid re-expresses its own ticks -->
              {@const src = mode === 'b' && sideB ? sideB : sideA}
              {@const tot = mode === 'b' && b ? b.total : a.total}
              <text x={cx - len(f, t)} y={H - 10}>{mode === 'overlay' ? `${t}%` : tickLabel(t, unit, tot, src.maleShare)}</text>
              <text x={cx + len(f, t)} y={H - 10}>{mode === 'overlay' ? `${t}%` : tickLabel(t, unit, tot, src.femaleShare)}</text>
            {:else}
              <text x={cx} y={H - 10}>0</text>
            {/if}
          {/each}
        </g>
        {#if title}
          <text x={cx} y={TOP - 4} font-size="11" fill="var(--fg-2)" text-anchor="middle">{title}</text>
        {/if}
        <!-- rows -->
        {#each rows as k (k)}
          {@const y = rowY(k, TOP, ROW) + (ROW - BAR) / 2}
          <text x={f.x0 + f.lab - 6} y={y + BAR / 2 + 3.5} font-size={FS} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">{ageLabel(k)}</text>
          {#if mode !== 'b'}
            {@const ml = len(f, sideA.male[k].pctTotal)}
            {@const fl = len(f, sideA.female[k].pctTotal)}
            <path d={barPath(cx - 1, y, Math.max(0, ml - 1), BAR, 'left')} fill="var(--male)" fill-opacity="0.85" />
            <path d={barPath(cx + 1, y, Math.max(0, fl - 1), BAR, 'right')} fill="var(--female)" fill-opacity="0.85" />
            {#if mode === 'a'}
              <text x={cx - ml - 5} y={y + BAR / 2 + 3.5} font-size={FS - 1} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">{barLabel(sideA.male[k].value, unit)}</text>
              <text x={cx + fl + 5} y={y + BAR / 2 + 3.5} font-size={FS - 1} fill="var(--fg-2)" style="font-variant-numeric: tabular-nums">{barLabel(sideA.female[k].value, unit)}</text>
            {/if}
          {/if}
          {#if sideB && mode !== 'a'}
            {@const ml = len(f, sideB.male[k].pctTotal)}
            {@const fl = len(f, sideB.female[k].pctTotal)}
            {#if mode === 'b'}
              <path d={barPath(cx - 1, y, Math.max(0, ml - 1), BAR, 'left')} fill="var(--male)" fill-opacity="0.85" />
              <path d={barPath(cx + 1, y, Math.max(0, fl - 1), BAR, 'right')} fill="var(--female)" fill-opacity="0.85" />
              <text x={cx - ml - 5} y={y + BAR / 2 + 3.5} font-size={FS - 1} fill="var(--fg-2)" text-anchor="end" style="font-variant-numeric: tabular-nums">{barLabel(sideB.male[k].value, unit)}</text>
              <text x={cx + fl + 5} y={y + BAR / 2 + 3.5} font-size={FS - 1} fill="var(--fg-2)" style="font-variant-numeric: tabular-nums">{barLabel(sideB.female[k].value, unit)}</text>
            {:else}
              <!-- B outlined (dashed) on the same axis -->
              {#if ml > 1}<rect x={cx - ml} y={y + 0.75} width={ml - 1} height={BAR - 1.5} fill="none" stroke="var(--fg)" stroke-width="1.5" stroke-dasharray="4 2" rx="2" />{/if}
              {#if fl > 1}<rect x={cx + 1} y={y + 0.75} width={fl - 1} height={BAR - 1.5} fill="none" stroke="var(--fg)" stroke-width="1.5" stroke-dasharray="4 2" rx="2" />{/if}
            {/if}
          {/if}
        {/each}
      {/snippet}

      {#if view === 'side'}
        {@render pyramid(half(0), drawnA, null, 'a', `A · ${legendA}`)}
        {#if drawnB}
          {@render pyramid(half(1), drawnA, drawnB, 'b', `B · ${legendB}`)}
        {:else}
          <text x={(3 * W) / 4} y={H / 2} text-anchor="middle" font-size="13" fill="var(--muted)">B is still being resolved…</text>
        {/if}
      {:else}
        {@render pyramid(full, drawnA, drawnB, 'overlay', null)}
      {/if}
    {/if}
  </svg>

  {#if axis.clips}
    <p class="mt-1 text-xs text-muted">Some bar exceeds the {axis.axisPct}% axis and is clamped. Choose “never clip” in the axis menu to see it in full.</p>
  {/if}

  <!-- accessible twin -->
  <table class="sr-only">
    {#if view === 'diff'}
      <caption>{legendB} minus {legendA}: difference per five-year age band and sex, percentage points of total population</caption>
      <thead><tr><th scope="col">Age</th><th scope="col">Male Δ</th><th scope="col">Female Δ</th></tr></thead>
      <tbody>
        {#each rows as k (k)}
          <tr><th scope="row">{ageLabel(k)}</th><td>{exactDiff ? signed(exactDiff[k].m) : '—'}</td><td>{exactDiff ? signed(exactDiff[k].f) : '—'}</td></tr>
        {/each}
      </tbody>
    {:else}
      <caption>{legendA} (A) and {legendB} (B): population by five-year age band and sex ({UNIT_LABEL[unit]})</caption>
      <thead>
        <tr><th scope="col">Age</th><th scope="col">A male</th><th scope="col">A female</th><th scope="col">B male</th><th scope="col">B female</th></tr>
      </thead>
      <tbody>
        {#each rows as k (k)}
          {@const fmt = (v: number) => (unit === 'abs' ? fmtInt(v) : fmtPct(v, 2, true))}
          <tr>
            <th scope="row">{ageLabel(k)}</th>
            <td>{fmt(exactA.male[k].value)}</td>
            <td>{fmt(exactA.female[k].value)}</td>
            <td>{exactB ? fmt(exactB.male[k].value) : '—'}</td>
            <td>{exactB ? fmt(exactB.female[k].value) : '—'}</td>
          </tr>
        {/each}
      </tbody>
    {/if}
  </table>
</div>

<style>
  .overlay {
    border-radius: 8px;
  }
  svg text {
    pointer-events: none;
  }
</style>
