import { describe, expect, it } from 'vitest';
import { entities, resolve } from './entities.ts';
import { flatten, scoreEntity, search, subsequenceSpan } from './fuzzy.ts';

const top = (q: string) => search(entities, q).countries[0]?.entity.id;

describe('fuzzy search over the real entity list', () => {
  it.each<[string, string]>([
    ['japan', 'JPN'],
    ['JPN', 'JPN'],
    ['jp', 'JPN'],
    ['USA', 'USA'],
    ['united states', 'USA'],
    ['korea', resolve('korea')!.id],
    ['niger', 'NER'], // exact short name beats Nigeria's prefix match
    ['viet', 'VNM'],
    ['côte', 'CIV'],
    ['cote', 'CIV'],
  ])('%s → %s', (q, id) => expect(top(q)).toBe(id));

  it('groups countries and aggregates separately', () => {
    const g = search(entities, 'world');
    expect(g.aggregates[0]?.entity.id).toBe('agg-900');
    expect(g.countries.every((h) => h.entity.type === 'country')).toBe(true);
  });

  it('empty query lists the biggest first, grouped and capped', () => {
    const g = search(entities, '', 5);
    expect(g.countries.length).toBe(5);
    expect(g.aggregates.length).toBe(5);
    expect(g.countries[0]!.entity.pop_2026).toBeGreaterThanOrEqual(g.countries[1]!.entity.pop_2026);
    expect(flatten(g).length).toBe(10);
  });

  it('no hits for gibberish', () => {
    const g = search(entities, 'zzqx');
    expect(flatten(g)).toEqual([]);
  });

  it('subsequence matching is loose but ranked below substrings', () => {
    expect(subsequenceSpan('jpn', 'japan')).toBe(4);
    expect(subsequenceSpan('xq', 'japan')).toBe(-1);
    const jpn = resolve('jpn')!;
    expect(scoreEntity(jpn, 'jap')).toBe(80);
    expect(scoreEntity(jpn, 'apan')).toBe(40);
    expect(scoreEntity(jpn, 'jpa')).toBeGreaterThanOrEqual(10);
    expect(scoreEntity(jpn, 'jpa')).toBeLessThan(40);
  });
});
