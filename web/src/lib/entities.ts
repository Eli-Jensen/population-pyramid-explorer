// Entity lookup helpers over the build's `entities.json` (CONTRACT §2) and `meta.json` (§5).
// Everything here is derived from the data files — never hardcode n_entities / n_countries.

import { entities, meta } from './data.ts';
import {
  N_BINS,
  N_DIMS,
  U16_TOTAL,
  YEAR_MAX,
  YEAR_MIN,
  type AxisPct,
  type Entity,
  type EntityType,
  type Meta,
} from './types.ts';

export { entities, meta, N_BINS, N_DIMS, U16_TOTAL, YEAR_MAX, YEAR_MIN };
export type { AxisPct, Entity, EntityType, Meta };

export const N_YEARS = meta.n_years; // 151
export const nEntities = entities.length;

if (nEntities !== meta.n_entities) {
  throw new Error(`entities.json has ${nEntities} entities but meta.json says ${meta.n_entities}`);
}
if (YEAR_MAX - YEAR_MIN + 1 !== N_YEARS) {
  throw new Error(`meta.n_years=${N_YEARS} but the year range is ${YEAR_MIN}–${YEAR_MAX}`);
}

export const countries = entities.filter((e) => e.type === 'country');
export const aggregates = entities.filter((e) => e.type === 'aggregate');

const idMap = new Map<string, Entity>();
const idxMap = new Map<string, number>();
const keyMap = new Map<string, Entity>(); // lowercase slug | id | alias → entity
entities.forEach((e, i) => {
  idMap.set(e.id, e);
  idxMap.set(e.id, i);
  for (const k of [e.slug, e.id, ...e.aliases]) {
    const key = k.toLowerCase();
    const prev = keyMap.get(key);
    if (prev && prev !== e) throw new Error(`alias collision: "${key}" → ${prev.id} and ${e.id}`);
    keyMap.set(key, e);
  }
});

/** Entity by exact id (`JPN`, `agg-900`). */
export const byId = (id: string): Entity | undefined => idMap.get(id);
/** Entity by corpus index (row block `idx*151 … idx*151+150`). */
export const byIdx = (idx: number): Entity | undefined => entities[idx];
/** Corpus index of an entity id, or -1. */
export const idxOf = (id: string): number => idxMap.get(id) ?? -1;
/** Case-insensitive lookup by slug, id, or alias (`/USA`, `jpn`, `united-states-of-america`). */
export const resolve = (key: string): Entity | undefined => keyMap.get(key.trim().toLowerCase());
/** Entity by canonical slug only (case-insensitive). */
export const bySlug = (slug: string): Entity | undefined => {
  const e = resolve(slug);
  return e && e.slug === slug.toLowerCase() ? e : undefined;
};

export const isCountry = (e: Entity) => e.type === 'country';
export const isAggregate = (e: Entity) => e.type === 'aggregate';

/** Row index into the corpus blobs (`shares.*`, `totals.*`, `emb/*`). */
export function rowIndex(id: string, year: number): number {
  const idx = idxOf(id);
  if (idx < 0) throw new Error(`unknown entity ${id}`);
  return idx * N_YEARS + (year - YEAR_MIN);
}

export type Clock = () => Date;
export const systemClock: Clock = () => new Date();

/** The client's current year, clamped to the corpus range (PLAN §7). Inject a clock in tests. */
export function currentYear(clock: Clock = systemClock): number {
  return clampYear(clock().getFullYear());
}

export const isValidYear = (y: number) => Number.isInteger(y) && y >= YEAR_MIN && y <= YEAR_MAX;
export const clampYear = (y: number) => Math.min(YEAR_MAX, Math.max(YEAR_MIN, Math.round(y)));

export type Era = 'observed' | 'nowcast' | 'projected';

/** Which era a year belongs to: observed ≤ last_observed_year, nowcast ≤ current year, else projected. */
export function eraOf(year: number, curYear: number, lastObserved = meta.last_observed_year): Era {
  if (year <= lastObserved) return 'observed';
  if (year <= curYear) return 'nowcast';
  return 'projected';
}

/** Regional-indicator flag for a country, '' for aggregates / Kosovo (no official flag emoji). */
export function flagEmoji(e: Entity): string {
  const iso2 = e.iso2;
  if (!iso2 || iso2.length !== 2 || iso2 === 'XK') return '';
  return String.fromCodePoint(...[...iso2.toUpperCase()].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}
