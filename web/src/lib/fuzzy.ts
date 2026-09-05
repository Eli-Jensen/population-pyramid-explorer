// Picker search (PLAN §2 "fuzzy search on name + ISO3 + aliases"): a small deterministic scorer, no deps.
// Score tiers (higher wins): exact id/alias 100 · name starts with query 80 · a word of the name starts with
// query 70 · alias starts with query 60 · substring 40 · in-order subsequence 10..20 (scaled by tightness).
// Ties break by population (largest first), then name. Countries and aggregates come back grouped.

import type { Entity } from './types.ts';

export interface Hit {
  entity: Entity;
  score: number;
}

export interface Grouped {
  countries: Hit[];
  aggregates: Hit[];
}

const norm = (s: string): string =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’'`]/g, '')
    .trim();

/** Is `q` an in-order subsequence of `s`? Returns the span it covers (last − first index) or −1. */
export function subsequenceSpan(q: string, s: string): number {
  if (!q) return 0;
  let i = 0;
  let first = -1;
  let last = -1;
  for (let j = 0; j < s.length && i < q.length; j++) {
    if (s[j] === q[i]) {
      if (first < 0) first = j;
      last = j;
      i++;
    }
  }
  return i === q.length ? last - first : -1;
}

/** Score one entity for a normalised query (0 = no match). */
export function scoreEntity(e: Entity, q: string): number {
  if (!q) return 0;
  const name = norm(e.short_name);
  const un = norm(e.name);
  const aliases = e.aliases.map(norm);
  if (e.id.toLowerCase() === q || aliases.includes(q) || name === q || un === q) return 100;
  if (name.startsWith(q) || un.startsWith(q)) return 80;
  const words = [...name.split(/[\s-]+/), ...un.split(/[\s-]+/)];
  if (words.some((w) => w.startsWith(q))) return 70;
  if (aliases.some((a) => a.startsWith(q))) return 60;
  if (name.includes(q) || un.includes(q) || aliases.some((a) => a.includes(q))) return 40;
  if (q.length >= 2) {
    const spans = [name, un, ...aliases].map((s) => subsequenceSpan(q, s)).filter((x) => x >= 0);
    if (spans.length) {
      const best = Math.min(...spans);
      // tight subsequences (span close to q.length) score up to 20, loose ones down toward 10
      const tight = Math.max(0, 1 - (best - (q.length - 1)) / Math.max(1, name.length));
      return 10 + Math.round(10 * tight);
    }
  }
  return 0;
}

function cmp(a: Hit, b: Hit): number {
  return b.score - a.score || b.entity.pop_2026 - a.entity.pop_2026 || a.entity.short_name.localeCompare(b.entity.short_name);
}

/** Ranked hits for a raw query. Empty query → everything by population, still grouped. */
export function search(entities: readonly Entity[], query: string, limitPerGroup = 8): Grouped {
  const q = norm(query);
  const countries: Hit[] = [];
  const aggregates: Hit[] = [];
  for (const e of entities) {
    const score = q ? scoreEntity(e, q) : 1;
    if (score <= 0) continue;
    (e.type === 'aggregate' ? aggregates : countries).push({ entity: e, score });
  }
  countries.sort(cmp);
  aggregates.sort(cmp);
  return { countries: countries.slice(0, limitPerGroup), aggregates: aggregates.slice(0, limitPerGroup) };
}

/** Flat list in display order (countries first) — what the keyboard walks. */
export function flatten(g: Grouped): Hit[] {
  return [...g.countries, ...g.aggregates];
}
