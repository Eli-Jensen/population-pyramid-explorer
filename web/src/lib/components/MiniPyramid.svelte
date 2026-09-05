<script lang="ts">
  // 120×120 mini pyramid for result cards (PLAN §6 J3): candidate filled, focal pyramid ghosted behind as an
  // outline, shared symmetric axis = the larger of the two pyramids' largest single-sex bin (rounded up to a
  // whole percent) so bulges compare at the same scale. Hand-written SVG, no labels — the card carries the text.
  import { N_BINS } from '../types.ts';

  interface Props {
    shares: Float32Array; // candidate, 42 shares of total
    ghost?: Float32Array | null; // focal pyramid, drawn behind
    size?: number; // CSS px, square
    label: string; // aria-label
  }
  let { shares, ghost = null, size = 120, label }: Props = $props();

  const W = 120;
  const H = 120;
  const PAD = 4;
  const ROW = (H - 2 * PAD) / N_BINS;
  const cx = W / 2;
  const half = W / 2 - PAD;

  function maxPct(a: Float32Array | null): number {
    if (!a) return 0;
    let m = 0;
    for (let i = 0; i < a.length; i++) if (a[i] > m) m = a[i];
    return m * 100;
  }
  const axis = $derived(Math.max(1, Math.ceil(Math.max(maxPct(shares), maxPct(ghost)) + 1e-6)));
  const len = (share: number) => Math.min(half, (share * 100 * half) / axis);
  const y = (k: number) => PAD + (N_BINS - 1 - k) * ROW;
  const rows = Array.from({ length: N_BINS }, (_, k) => k);
</script>

<svg viewBox="0 0 {W} {H}" width={size} height={size} role="img" aria-label={label} class="block shrink-0 select-none">
  <line x1={cx} x2={cx} y1={PAD} y2={H - PAD} stroke="var(--axis)" stroke-width="0.75" />
  {#if ghost}
    <g fill="none" stroke="var(--fg-2)" stroke-opacity="0.55" stroke-width="0.75" aria-hidden="true">
      {#each rows as k (k)}
        <rect x={cx - len(ghost[k])} y={y(k) + 0.5} width={len(ghost[k])} height={Math.max(0.5, ROW - 1)} />
        <rect x={cx} y={y(k) + 0.5} width={len(ghost[N_BINS + k])} height={Math.max(0.5, ROW - 1)} />
      {/each}
    </g>
  {/if}
  <g aria-hidden="true">
    {#each rows as k (k)}
      <rect x={cx - len(shares[k])} y={y(k) + 1} width={len(shares[k])} height={Math.max(0.5, ROW - 2)} fill="var(--male)" fill-opacity="0.85" />
      <rect x={cx} y={y(k) + 1} width={len(shares[N_BINS + k])} height={Math.max(0.5, ROW - 2)} fill="var(--female)" fill-opacity="0.85" />
    {/each}
  </g>
</svg>
