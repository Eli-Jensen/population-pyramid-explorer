<script lang="ts">
  // Persistent readout strip under the pyramid (PLAN §2 "hover → persistent readout strip"):
  // age band, male count + share, female count + share, sex ratio (males per 100 females).
  import { N_BINS } from '../types.ts';
  import { ageLabel, fmtPct, fmtPersons, fmtRatio, sexRatio } from '../format.ts';

  interface Props {
    shares: Float32Array;
    total: number; // thousands
    bin: number | null;
  }
  let { shares, total, bin }: Props = $props();

  const m = $derived(bin === null ? NaN : shares[bin]);
  const f = $derived(bin === null ? NaN : shares[N_BINS + bin]);
  const ratio = $derived(sexRatio(m, f));
</script>

<div class="readout mt-2 grid grid-cols-2 gap-x-4 gap-y-1 rounded-md border border-border bg-surface px-3 py-2 text-sm sm:grid-cols-4" aria-live="off">
  {#if bin === null}
    <p class="col-span-full text-muted">Hover, tap or use ↑/↓ on the pyramid to read one age band.</p>
  {:else}
    <div>
      <div class="text-xs text-muted">Age band</div>
      <div class="font-medium tabular-nums">{ageLabel(bin)}</div>
    </div>
    <div>
      <div class="flex items-center gap-1.5 text-xs text-muted"><span class="inline-block h-2.5 w-2.5 rounded-sm bg-male"></span>Male</div>
      <div class="tabular-nums"><span class="font-medium">{fmtPersons(m * total)}</span> <span class="text-fg-2">· {fmtPct(m, 2)}</span></div>
    </div>
    <div>
      <div class="flex items-center gap-1.5 text-xs text-muted"><span class="inline-block h-2.5 w-2.5 rounded-sm bg-female"></span>Female</div>
      <div class="tabular-nums"><span class="font-medium">{fmtPersons(f * total)}</span> <span class="text-fg-2">· {fmtPct(f, 2)}</span></div>
    </div>
    <div>
      <div class="text-xs text-muted">Sex ratio</div>
      <div class="tabular-nums"><span class="font-medium">{fmtRatio(ratio, 0)}</span> <span class="text-fg-2">males per 100 females</span></div>
    </div>
  {/if}
</div>
