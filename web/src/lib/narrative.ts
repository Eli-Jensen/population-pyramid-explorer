// Template prose for Narrative.svelte — our own wording (PLAN §2: "auto narrative in our own template prose").
// Pure: (entity facts, year, era, features, change) → short paragraphs. Every number is formatted here so the
// component is markup only. Stage wording follows features.ts' documented thresholds (25 / 40 median age).

import type { Features, Stage } from './math/features.ts';
import type { Era } from './entities.ts';
import type { Change } from './series.ts';
import { fmtPersonsCompact, fmtSignedPct, fmtYears } from './format.ts';

export interface NarrativeInput {
  name: string; // display name ("Japan", "World")
  isAggregate: boolean;
  year: number;
  era: Era;
  total: number; // thousands
  features: Features;
  change: Change | null; // ten-year total change
  lastObservedYear: number;
}

export const STAGE_LABEL: Record<Stage, string> = {
  expansive: 'expansive',
  stationary: 'stationary',
  constrictive: 'constrictive',
};

export const STAGE_HINT: Record<Stage, string> = {
  expansive: 'wide base, narrow top — a young, growing population',
  stationary: 'straight sides — births roughly replace deaths',
  constrictive: 'narrow base, heavy top — an ageing population',
};

/** "is" / "was" / "is projected to be" by era. */
export function tense(era: Era): { be: string; have: string; live: string } {
  switch (era) {
    case 'observed':
      return { be: 'was', have: 'had', live: 'lived' };
    case 'nowcast':
      return { be: 'is', have: 'has', live: 'live' };
    default:
      return { be: 'is projected to be', have: 'is projected to have', live: 'are projected to live' };
  }
}

function pct(x: number, digits = 0): string {
  return `${(x * 100).toFixed(digits)}%`;
}

/** Paragraphs of prose (2–4). */
export function narrative(inp: NarrativeInput): string[] {
  const { name, year, era, total, features: f, change } = inp;
  const t = tense(era);
  const out: string[] = [];

  // 1 — size and change
  let p1 = `${name} ${t.have} a population of about ${fmtPersonsCompact(total, 2)} in ${year}`;
  if (change) {
    const dir = change.fraction > 0.0005 ? 'up' : change.fraction < -0.0005 ? 'down' : 'flat';
    const span = change.to - change.from;
    if (change.to === year) {
      p1 +=
        dir === 'flat'
          ? `, essentially unchanged over the previous ${span} years.`
          : `, ${dir} ${fmtSignedPct(change.fraction).replace(/^[+−]/, '')} since ${change.from}.`;
    } else {
      p1 +=
        dir === 'flat'
          ? `, essentially unchanged over the following ${span} years.`
          : `, heading ${dir} ${fmtSignedPct(change.fraction).replace(/^[+−]/, '')} by ${change.to}.`;
    }
  } else {
    p1 += '.';
  }
  out.push(p1);

  // 2 — shape and stage
  const stage = STAGE_LABEL[f.stage];
  let p2 = `The median age ${t.be} ${fmtYears(f.median_age)} years, which makes the pyramid ${stage} (${STAGE_HINT[f.stage]}).`;
  p2 += ` Children under 15 ${era === 'observed' ? 'made up' : era === 'nowcast' ? 'make up' : 'are projected to make up'} ${pct(f.u15)} of the population, working ages 15–64 ${pct(f.wa)}, and people 65 and over ${pct(f.o65)}`;
  p2 += f.o80 >= 0.03 ? `, including ${pct(f.o80, 1)} aged 80+.` : '.';
  out.push(p2);

  // 3 — dependency
  const dep = f.total_dep;
  if (Number.isFinite(dep)) {
    const child = Math.round(f.child_dep * 100);
    const old = Math.round(f.old_dep * 100);
    const lead = child > old * 2 ? 'almost all of them children' : old > child * 2 ? 'mostly older people' : 'split between children and older people';
    out.push(
      `For every 100 people of working age there ${era === 'observed' ? 'were' : era === 'nowcast' ? 'are' : 'would be'} ${Math.round(dep * 100)} dependants — ${lead} (${child} under 15, ${old} aged 65+).`,
    );
  }

  // 4 — flags and caveats
  const notes: string[] = [];
  if (f.flag_male_skew) {
    notes.push(
      `Men outnumber women ${f.wa_sex_ratio.toFixed(2)} to 1 at working ages, a skew usually explained by migrant labour.`,
    );
  } else if (Number.isFinite(f.wa_sex_ratio) && f.wa_sex_ratio < 0.85) {
    notes.push(`Women outnumber men at working ages (${f.wa_sex_ratio.toFixed(2)} men per woman).`);
  }
  if (f.flag_urn) {
    notes.push(`The largest five-year cohort ${t.be} already ${f.modal_bin}–${f.modal_bin + 4}, an urn-shaped profile.`);
  } else if (f.base_slope_20 < 0.7 && f.stage !== 'expansive') {
    notes.push(`The 0–4 cohort ${t.be} only ${pct(f.base_slope_20)} the size of the 20–24 cohort: births have been falling.`);
  }
  if (era === 'projected') {
    notes.push(`Figures after ${inp.lastObservedYear} are UN medium-variant projections${year > inp.lastObservedYear + 25 ? ' — distant years converge toward similar shapes and should be read loosely' : ''}.`);
  } else if (era === 'nowcast') {
    notes.push(`${year} is a UN nowcast: the last fully observed year is ${inp.lastObservedYear}.`);
  }
  if (notes.length) out.push(notes.join(' '));

  return out;
}
