import { describe, expect, it } from 'vitest';
import {
  canonical,
  countryQuery,
  defaultEra,
  elideDefaults,
  optionsSearch,
  parse,
  parseOptions,
  type Route,
} from './router.ts';

const clock2026 = () => new Date(2026, 5, 15); // local time — getFullYear() is local
const clock2027 = () => new Date(2027, 0, 1);
const PAGES = '/population-pyramid-explorer/';

type Case = { path: string; search?: string; base?: string; clock?: () => Date; want: Partial<Route> & { to?: string } };

const cases: Case[] = [
  // aliases / case / trailing slash → canonical via Redirect
  { path: '/USA/', clock: clock2026, want: { kind: 'redirect', to: '/united-states/2026' } },
  { path: '/jpn', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/United-States-Of-America/2026', want: { kind: 'redirect', to: '/united-states/2026' } },
  { path: '/JAPAN/2026/', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/us/1990', want: { kind: 'redirect', to: '/united-states/1990' } },
  { path: '/south-korea/2026', want: { kind: 'country', id: 'KOR', year: 2026 } },
  { path: '/korea/2026', want: { kind: 'redirect', to: '/south-korea/2026' } },
  { path: '/agg-900/2026', want: { kind: 'redirect', to: '/world/2026' } },
  // hub → current year from the injected clock
  { path: '/japan', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan', clock: clock2027, want: { kind: 'redirect', to: '/japan/2027' } },
  { path: '/world', clock: clock2026, want: { kind: 'redirect', to: '/world/2026' } },
  { path: '/japan/', search: '?unit=abs', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026?unit=abs' } },
  // canonical already → the query itself
  { path: '/japan/2026', want: { kind: 'country', id: 'JPN', year: 2026, axis: 'fit', unit: 'pct' } },
  { path: '/japan/1950', want: { kind: 'country', id: 'JPN', year: 1950 } },
  { path: '/japan/2100', want: { kind: 'country', id: 'JPN', year: 2100 } },
  // year validation
  { path: '/japan/1899', want: { kind: 'notfound' } },
  { path: '/japan/1949', want: { kind: 'notfound' } },
  { path: '/japan/2101', want: { kind: 'notfound' } },
  { path: '/japan/abc', want: { kind: 'notfound' } },
  { path: '/japan/026', want: { kind: 'notfound' } },
  { path: '/japan/2026/extra', want: { kind: 'notfound' } },
  // unknown slug
  { path: '/narnia', want: { kind: 'notfound', path: '/narnia' } },
  { path: '/narnia/2026', want: { kind: 'notfound' } },
  // home
  { path: '/', want: { kind: 'home' } },
  { path: '', want: { kind: 'redirect', to: '/' } },
  // options: defaults elided, fixed order, invalid values dropped
  { path: '/japan/2026', search: '?axis=fit&unit=pct', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?axis=pin10', want: { kind: 'country', axis: 'pin10', unit: 'pct' } },
  { path: '/japan/2026', search: '?unit=abs&axis=noclip', want: { kind: 'redirect', to: '/japan/2026?axis=noclip&unit=abs' } },
  { path: '/japan/2026', search: '?axis=noclip&unit=abs', want: { kind: 'country', axis: 'noclip', unit: 'abs' } },
  { path: '/japan/2026', search: '?axis=bogus', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?utm_source=x&unit=pctsex', want: { kind: 'redirect', to: '/japan/2026?unit=pctsex' } },
  // base prefix (GitHub Pages project site)
  { path: `${PAGES}japan/2026`, base: PAGES, want: { kind: 'country', id: 'JPN', year: 2026 } },
  { path: `${PAGES}JAPAN/2026/`, base: PAGES, want: { kind: 'redirect', to: `${PAGES}japan/2026` } },
  { path: `${PAGES}jpn`, base: PAGES, clock: clock2026, want: { kind: 'redirect', to: `${PAGES}japan/2026` } },
  { path: PAGES, base: PAGES, want: { kind: 'home' } },
  { path: '/population-pyramid-explorer', base: PAGES, want: { kind: 'redirect', to: PAGES } },
  { path: '/Population-Pyramid-Explorer/japan/2026', base: PAGES, want: { kind: 'redirect', to: `${PAGES}japan/2026` } },
  { path: '/japan/2026', base: PAGES, want: { kind: 'notfound' } }, // outside the base
  // reserved future routes
  { path: '/about', want: { kind: 'placeholder', route: 'about' } },
  { path: '/evidence/', want: { kind: 'redirect', to: '/evidence' } },
  { path: '/compare/japan/2026/italy/2026', want: { kind: 'placeholder', route: 'compare', segments: ['japan', '2026', 'italy', '2026'] } },
  { path: `${PAGES}compare/japan/2026/italy/best`, base: PAGES, search: '?view=diff', want: { kind: 'placeholder', route: 'compare', search: '?view=diff' } },
];

describe('router.parse', () => {
  for (const c of cases) {
    const label = `${c.base ?? '/'} ${c.path}${c.search ?? ''}${c.clock ? ` @${c.clock().getUTCFullYear()}` : ''}`;
    it(label, () => {
      const got = parse(c.path, c.search ?? '', c.base ?? '/', { clock: c.clock });
      expect(got).toMatchObject(c.want);
    });
  }

  it('redirects carry the query they resolve to', () => {
    const r = parse('/USA/', '', '/', { clock: clock2026 });
    expect(r.kind).toBe('redirect');
    if (r.kind === 'redirect') {
      expect(r.query).toMatchObject({ kind: 'country', id: 'USA', year: 2026 });
      expect(parse(r.to, '', '/')).toEqual(r.query); // the redirect target is a fixed point
    }
  });

  it('every redirect target is canonical (parses to itself)', () => {
    for (const c of cases) {
      const got = parse(c.path, c.search ?? '', c.base ?? '/', { clock: c.clock });
      if (got.kind !== 'redirect') continue;
      const [p, s = ''] = got.to.split('?');
      const again = parse(p!, s ? '?' + s : '', c.base ?? '/', { clock: c.clock });
      expect(again).toEqual(got.query);
    }
  });

  it('a hub redirect with a 2027 clock counts 2027 as the current year', () => {
    const r = parse('/japan', '', '/', { clock: clock2027 });
    expect(r).toMatchObject({ kind: 'redirect', to: '/japan/2027', query: { year: 2027 } });
  });
});

describe('router.canonical', () => {
  it.each([
    [countryQuery('JPN', 2026), '/', '/japan/2026'],
    [countryQuery('JPN', 2026, { axis: 'fit', unit: 'pct' }), '/', '/japan/2026'],
    [countryQuery('USA', 1990, { unit: 'abs' }), '/', '/united-states/1990?unit=abs'],
    [countryQuery('KOR', 2050, { axis: 'pin10', unit: 'pctsex' }), PAGES, `${PAGES}south-korea/2050?axis=pin10&unit=pctsex`],
    [countryQuery('agg-900', 2026), PAGES, `${PAGES}world/2026`],
    [{ kind: 'home' } as const, PAGES, PAGES],
    [{ kind: 'home' } as const, '/', '/'],
  ])('%o @%s → %s', (q, base, want) => {
    expect(canonical(q, base)).toBe(want);
  });

  it('accepts an alias as id but emits the canonical slug', () => {
    expect(canonical(countryQuery('usa', 2026), '/')).toBe('/united-states/2026');
  });

  it('tolerates a base without slashes', () => {
    expect(canonical(countryQuery('JPN', 2026), 'population-pyramid-explorer')).toBe(`${PAGES}japan/2026`);
  });
});

describe('options', () => {
  it('elideDefaults drops defaults and keeps the rest', () => {
    expect(elideDefaults({ axis: 'fit', unit: 'pct' })).toEqual({});
    expect(elideDefaults({ axis: 'pin10', unit: 'pct' })).toEqual({ axis: 'pin10' });
    expect(elideDefaults({ unit: 'abs' })).toEqual({ unit: 'abs' });
    expect(optionsSearch({ axis: 'fit' })).toBe('');
    expect(optionsSearch({ unit: 'abs', axis: 'noclip' })).toBe('?axis=noclip&unit=abs');
  });
  it('parseOptions accepts with or without the leading ?', () => {
    expect(parseOptions('axis=pin10')).toEqual({ axis: 'pin10', unit: 'pct' });
    expect(parseOptions('?unit=abs')).toEqual({ axis: 'fit', unit: 'abs' });
    expect(parseOptions('')).toEqual({ axis: 'fit', unit: 'pct' });
  });
});

describe('defaultEra (J8)', () => {
  it.each([
    [2050, 2026, 'all'],
    [2027, 2026, 'all'],
    [2026, 2026, 'obs'],
    [1990, 2026, 'obs'],
    [2027, 2027, 'obs'],
  ] as const)('year %i, current %i → %s', (y, cur, want) => {
    expect(defaultEra(y, cur)).toBe(want);
  });
});
