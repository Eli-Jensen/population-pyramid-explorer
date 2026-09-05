<script lang="ts">
  // Header chip (PLAN §5 / J-R): 'more isolated than 91 % of countries this year' — the percentile of the
  // focal country's isolation (mean distance to its 5 nearest same-year countries ≥ 100k) among all of them.
  import { isolationText } from '../restate.ts';

  interface Props {
    percentile: number | null; // null while computing / for aggregates
    metricLabel: string;
  }
  let { percentile, metricLabel }: Props = $props();
</script>

{#if percentile !== null}
  <span
    class="chip"
    title="Isolation = mean {metricLabel} distance to the 5 nearest countries (≥ 100k) in this year; the percentile ranks it among all such countries."
    >{isolationText(percentile)}</span
  >
{/if}
