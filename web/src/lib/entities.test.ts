import { describe, expect, it } from 'vitest';
import {
  aggregates,
  byId,
  byIdx,
  bySlug,
  clampYear,
  countries,
  currentYear,
  entities,
  eraOf,
  flagEmoji,
  idxOf,
  isValidYear,
  meta,
  nEntities,
  N_YEARS,
  resolve,
  rowIndex,
  YEAR_MAX,
  YEAR_MIN,
} from './entities.ts';

describe('entities.json', () => {
  it('matches meta.json counts and corpus order (countries by id, then aggregates by id)', () => {
    expect(nEntities).toBe(meta.n_entities);
    expect(countries.length).toBe(meta.n_countries);
    expect(aggregates.length).toBe(meta.n_entities - meta.n_countries);
    expect(nEntities * N_YEARS).toBe(meta.n_rows);
    const ids = entities.map((e) => e.id);
    const c = ids.slice(0, countries.length);
    const a = ids.slice(countries.length);
    expect(c).toEqual([...c].sort());
    expect(a).toEqual([...a].sort());
    expect(a.every((id) => id.startsWith('agg-'))).toBe(true);
  });

  it('lookups', () => {
    expect(byIdx(0)?.id).toBe(entities[0]!.id);
    expect(byIdx(idxOf('JPN'))?.id).toBe('JPN');
    expect(idxOf('nope')).toBe(-1);
    expect(byId('JPN')?.slug).toBe('japan');
    expect(bySlug('Japan')?.id).toBe('JPN');
    expect(bySlug('jpn')).toBeUndefined(); // alias, not the canonical slug
  });

  it.each([
    ['JPN', 'JPN'],
    ['jpn', 'JPN'],
    ['Japan', 'JPN'],
    ['USA', 'USA'],
    ['us', 'USA'],
    ['united-states-of-america', 'USA'],
    ['United-States', 'USA'],
    ['south-korea', 'KOR'],
    ['korea', 'KOR'],
    ['world', 'agg-900'],
    ['AGG-900', 'agg-900'],
    [' japan ', 'JPN'],
  ])('resolve(%s) → %s', (key, id) => {
    expect(resolve(key)?.id).toBe(id);
  });
  it('resolve of an unknown key is undefined', () => {
    expect(resolve('narnia')).toBeUndefined();
    expect(resolve('')).toBeUndefined();
  });

  it('axis_pct only takes the four allowed values', () => {
    for (const e of entities) expect([10, 12, 14, 17]).toContain(e.axis_pct);
  });

  it('rowIndex is entity-major', () => {
    expect(rowIndex(entities[0]!.id, YEAR_MIN)).toBe(0);
    expect(rowIndex(entities[1]!.id, YEAR_MIN)).toBe(N_YEARS);
    expect(rowIndex(entities[nEntities - 1]!.id, YEAR_MAX)).toBe(meta.n_rows - 1);
  });
});

describe('years and clock', () => {
  it('currentYear clamps the client clock to the corpus range', () => {
    expect(currentYear(() => new Date('2026-06-01'))).toBe(2026);
    expect(currentYear(() => new Date('2027-01-01T00:00:00'))).toBe(2027);
    expect(currentYear(() => new Date('1900-01-01'))).toBe(YEAR_MIN);
    expect(currentYear(() => new Date('2200-01-01'))).toBe(YEAR_MAX);
  });
  it('validators', () => {
    expect(isValidYear(1950)).toBe(true);
    expect(isValidYear(2100)).toBe(true);
    expect(isValidYear(1949)).toBe(false);
    expect(isValidYear(2026.5)).toBe(false);
    expect(clampYear(1800)).toBe(1950);
    expect(clampYear(2026.4)).toBe(2026);
  });
  it('eraOf uses last_observed_year and the current year', () => {
    expect(meta.last_observed_year).toBe(2023);
    expect(eraOf(2023, 2026)).toBe('observed');
    expect(eraOf(2024, 2026)).toBe('nowcast');
    expect(eraOf(2026, 2026)).toBe('nowcast');
    expect(eraOf(2027, 2026)).toBe('projected');
    expect(eraOf(2027, 2027)).toBe('nowcast');
  });
});

describe('flagEmoji', () => {
  it('countries get a flag, aggregates and Kosovo do not', () => {
    expect(flagEmoji(byId('JPN')!)).toBe('🇯🇵');
    expect(flagEmoji(byId('agg-900')!)).toBe('');
    expect(flagEmoji(byId('XKX')!)).toBe('');
  });
});
