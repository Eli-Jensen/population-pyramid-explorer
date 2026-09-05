<script lang="ts">
  // Decomposition sparkline (PLAN §4.4): 42 columns (male 0–4 … 100+, then female) of candidate − focal share
  // around a midline; the bins that contribute most to the ranking metric are drawn in the accent colour.
  // 42 viewBox units wide (one per bin), rendered at 2× by default; purely decorative — the card's text carries
  // the same bins in words, so the SVG is aria-hidden.
  import { N_BINS, N_DIMS } from '../types.ts';
  import { ageLabel } from '../format.ts';

  interface Props {
    delta: Float32Array; // 42 values, candidate − focal
    highlight?: number[]; // bin indices 0..41
    width?: number; // CSS px (viewBox is 42 × 14)
  }
  let { delta, highlight = [], width = 84 }: Props = $props();

  const H = 14;
  const mid = H / 2;
  const scale = $derived.by(() => {
    let m = 0;
    for (let i = 0; i < N_DIMS; i++) m = Math.max(m, Math.abs(delta[i]));
    return m > 0 ? (mid - 1) / m : 0;
  });
  const hi = $derived(new Set(highlight));
  const cols = Array.from({ length: N_DIMS }, (_, i) => i);
  const title = $derived(
    highlight.length
      ? 'largest contributions: ' + highlight.map((b) => `${b < N_BINS ? 'M' : 'F'} ${ageLabel(b % N_BINS)}`).join(', ')
      : 'candidate minus focal, per age × sex bin',
  );
</script>

<svg viewBox="0 0 {N_DIMS} {H}" {width} height={(width * H) / N_DIMS} aria-hidden="true" class="block select-none" shape-rendering="crispEdges">
  <title>{title}</title>
  <line x1="0" x2={N_DIMS} y1={mid} y2={mid} stroke="var(--grid)" stroke-width="0.5" />
  <line x1={N_BINS} x2={N_BINS} y1="0" y2={H} stroke="var(--grid)" stroke-width="0.5" />
  {#each cols as i (i)}
    {@const h = Math.abs(delta[i]) * scale}
    <rect
      x={i + 0.1}
      y={delta[i] >= 0 ? mid - h : mid}
      width="0.8"
      height={Math.max(h, 0.15)}
      fill={hi.has(i) ? 'var(--accent)' : i < N_BINS ? 'var(--male)' : 'var(--female)'}
      fill-opacity={hi.has(i) ? 1 : 0.45}
    />
  {/each}
</svg>
