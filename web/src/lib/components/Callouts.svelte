<script lang="ts">
  // Stat tiles (PLAN §2 callouts): total, median age, youth / old-age dependency per 100, 10-year change,
  // stage chip. Distinctiveness arrives with M2 (omitted here).
  import type { Features } from '../math/features.ts';
  import type { Change } from '../series.ts';
  import { fmtPersons, fmtSignedPct, fmtYears } from '../format.ts';
  import { STAGE_HINT, STAGE_LABEL } from '../narrative.ts';

  interface Props {
    total: number; // thousands
    features: Features;
    change: Change | null;
    year: number;
  }
  let { total, features, change, year }: Props = $props();

  const per100 = (x: number) => (Number.isFinite(x) ? Math.round(x * 100).toString() : '—');
  const changeLabel = $derived(change ? (change.to === year ? `since ${change.from}` : `${change.from}→${change.to}`) : 'no comparison year');
</script>

<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
  <div class="card col-span-2 sm:col-span-3">
    <div class="text-xs text-muted">Population, {year}</div>
    <div class="mt-0.5 text-3xl font-semibold tracking-tight">{fmtPersons(total)}</div>
  </div>
  <div class="card">
    <div class="text-xs text-muted">Median age</div>
    <div class="mt-0.5 text-xl font-semibold">{fmtYears(features.median_age)} <span class="text-sm font-normal text-fg-2">years</span></div>
  </div>
  <div class="card">
    <div class="text-xs text-muted">Youth dependency</div>
    <div class="mt-0.5 text-xl font-semibold">{per100(features.child_dep)} <span class="text-sm font-normal text-fg-2">per 100</span></div>
    <div class="text-xs text-muted">under 15 per 100 aged 15–64</div>
  </div>
  <div class="card">
    <div class="text-xs text-muted">Old-age dependency</div>
    <div class="mt-0.5 text-xl font-semibold">{per100(features.old_dep)} <span class="text-sm font-normal text-fg-2">per 100</span></div>
    <div class="text-xs text-muted">65+ per 100 aged 15–64</div>
  </div>
  <div class="card">
    <div class="text-xs text-muted">10-year change</div>
    <div class="mt-0.5 text-xl font-semibold tabular-nums">{change ? fmtSignedPct(change.fraction) : '—'}</div>
    <div class="text-xs text-muted">{changeLabel}</div>
  </div>
  <div class="card col-span-2 sm:col-span-2">
    <div class="text-xs text-muted">Stage</div>
    <div class="mt-1 flex flex-wrap items-center gap-2">
      <span class="chip capitalize">{STAGE_LABEL[features.stage]}</span>
      <span class="text-xs text-fg-2">{STAGE_HINT[features.stage]}</span>
    </div>
  </div>
</div>
