<script lang="ts">
  // Text-free pyramid for the triplet collector (PLAN §4.6 item 8): one inline u16 row, drawn on a FIXED axis that
  // the page computes once for the whole sitting, so every anchor / A / B sits at an identical scale. No labels, no
  // ticks, no name, no year — only the aria-label the page passes ("Anchor", "Option A", "Option B"). Bars are
  // shares of TOTAL population, male left, female right, youngest at the bottom (same geometry as Pyramid.svelte).
  import { N_BINS } from '../types.ts';
  import { barLength } from '../math/scale.ts';
  import { barPath, rowY } from '../bars.ts';
  import { toShares } from '../triplets.ts';

  interface Props {
    row: ArrayLike<number>; // 42 × u16
    axisPct: number; // fixed for the sitting
    label: string; // aria-label only — never a name or year
    size?: number; // CSS px, square
    emphasis?: boolean; // selected option (pending choice) — a ring, not a change of geometry
  }
  let { row, axisPct, label, size = 240, emphasis = false }: Props = $props();

  const W = 200;
  const H = 200;
  const PAD = 6;
  const ROW = (H - 2 * PAD) / N_BINS;
  const cx = W / 2;
  const half = W / 2 - PAD;
  const rows = Array.from({ length: N_BINS }, (_, k) => k);

  const shares = $derived(toShares(row));
  const len = (share: number) => barLength(share * 100, axisPct, half);
  const barH = Math.max(0.5, ROW - 1.2);
</script>

<svg viewBox="0 0 {W} {H}" width={size} height={size} role="img" aria-label={label} class="block h-auto max-w-full shrink-0 select-none rounded-md" class:ring-2={emphasis} style="--tw-ring-color: var(--accent)">
  <line x1={cx} x2={cx} y1={PAD} y2={H - PAD} stroke="var(--axis)" stroke-width="0.75" aria-hidden="true" />
  <g aria-hidden="true">
    {#each rows as k (k)}
      <path d={barPath(cx, rowY(k, PAD, ROW) + 0.6, len(shares[k]), barH, 'left', 1.5)} fill="var(--male)" fill-opacity="0.85" />
      <path d={barPath(cx, rowY(k, PAD, ROW) + 0.6, len(shares[N_BINS + k]), barH, 'right', 1.5)} fill="var(--female)" fill-opacity="0.85" />
    {/each}
  </g>
</svg>
