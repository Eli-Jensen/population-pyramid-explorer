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
  // static page (M3) + reserved future routes
  { path: '/about', want: { kind: 'static', page: 'about' } },
  { path: '/About/', want: { kind: 'redirect', to: '/about' } },
  { path: '/about/more', want: { kind: 'notfound' } },
  { path: '/evidence/', want: { kind: 'redirect', to: '/evidence' } },
  // M5: /evidence is a static page; /eval/triplets the dev-only tool; other /eval/… stay placeholders
  { path: '/evidence', want: { kind: 'static', page: 'evidence' } },
  { path: '/Evidence', want: { kind: 'redirect', to: '/evidence' } },
  { path: '/evidence/x', want: { kind: 'notfound' } },
  { path: '/eval/triplets', want: { kind: 'eval', tool: 'triplets' } },
  { path: '/eval/triplets/', want: { kind: 'redirect', to: '/eval/triplets' } },
  { path: '/eval/other', want: { kind: 'placeholder', route: 'eval' } },
  { path: `${PAGES}eval/triplets`, base: PAGES, want: { kind: 'eval', tool: 'triplets' } },
  // M5: the market lens rides as ?lens=econ (elided when off, last in the order, junk values dropped)
  { path: '/japan/2026', search: '?lens=econ', want: { kind: 'country', id: 'JPN', year: 2026, lens: 'econ' } },
  { path: '/japan/2026', search: '?lens=off', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?lens=econ&unit=abs', want: { kind: 'redirect', to: '/japan/2026?unit=abs&lens=econ' } },
  { path: '/japan/2026', search: '?unit=abs&mode=any&lens=econ', want: { kind: 'country', unit: 'abs', mode: 'any', lens: 'econ' } },
  { path: '/japan/2026', search: '?lens=econ&mode=any', want: { kind: 'redirect', to: '/japan/2026?mode=any&lens=econ' } },
  { path: '/compare/japan/2026/italy/2008', search: '?lens=econ', want: { kind: 'compare', a: 'JPN', b: 'ITA', lens: 'econ' } },
  { path: '/compare/japan/2026/italy/2008', search: '?lens=econ&view=diff', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2008?view=diff&lens=econ' } },
  { path: '/compare/japan/2026/italy/best', search: '?lens=econ', want: { kind: 'compare', yb: 'best', lens: 'econ' } },
  // compare (M3) — the detailed table is below
  { path: '/compare/japan/2026/italy/2026', want: { kind: 'compare', a: 'JPN', ya: 2026, b: 'ITA', yb: 2026, view: 'overlay', from: null } },
  { path: `${PAGES}compare/japan/2026/italy/best`, base: PAGES, search: '?view=diff', want: { kind: 'compare', yb: 'best', view: 'diff', from: null } },
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

// ---------------------------------------------------------------------------------------------- M2 search params

import { DEFAULT_SEARCH, effectiveEra, normaliseSearch, searchParams, visualExposed } from './router.ts';

const clock2027b = () => new Date(2027, 6, 1);
const visual = visualExposed(); // this build ships an exposed image space (meta.verdicts.exposed_visual)

// `want` is loose on purpose: `to` is both the range edge (number | null) and `Redirect.to` (string).
type SCase = { path: string; search: string; clock?: () => Date; want: Record<string, unknown> };
const searchCases: SCase[] = [
  // year mode
  { path: '/japan/2026', search: '?mode=same', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?mode=near', want: { kind: 'country', mode: 'near', n: 10 } },
  { path: '/japan/2026', search: '?mode=near&n=10', want: { kind: 'redirect', to: '/japan/2026?mode=near' } },
  { path: '/japan/2026', search: '?mode=near&n=5', want: { kind: 'country', mode: 'near', n: 5 } },
  { path: '/japan/2026', search: '?mode=near&n=0', want: { kind: 'redirect', to: '/japan/2026?mode=near' } },
  { path: '/japan/2026', search: '?n=5', want: { kind: 'redirect', to: '/japan/2026' } }, // n without near
  { path: '/japan/2026', search: '?mode=any', want: { kind: 'country', mode: 'any', from: null, to: null } },
  { path: '/japan/2026', search: '?mode=range&from=1990&to=2026', want: { kind: 'country', mode: 'range', from: 1990, to: 2026 } },
  { path: '/japan/2026', search: '?mode=range&from=1950&to=2100', want: { kind: 'redirect', to: '/japan/2026?mode=range' } },
  { path: '/japan/2026', search: '?mode=range&from=2026&to=1990', want: { kind: 'redirect', to: '/japan/2026?mode=range&from=1990&to=2026' } },
  { path: '/japan/2026', search: '?mode=range&from=1899', want: { kind: 'redirect', to: '/japan/2026?mode=range' } },
  { path: '/japan/2026', search: '?from=1990', want: { kind: 'redirect', to: '/japan/2026' } }, // range edge without range
  // today sugar → concrete one-year range + via=today (replaceState'd by the app), a fixed point afterwards
  { path: '/japan/1990', search: '?mode=today', clock: clock2026, want: { kind: 'redirect', to: '/japan/1990?mode=range&from=2026&to=2026&via=today' } },
  { path: '/japan/1990', search: '?mode=today', clock: clock2027b, want: { kind: 'redirect', to: '/japan/1990?mode=range&from=2027&to=2027&via=today' } },
  { path: '/japan/1990', search: '?mode=range&from=2026&to=2026&via=today', want: { kind: 'country', mode: 'range', from: 2026, to: 2026, via: 'today' } },
  { path: '/japan/1990', search: '?mode=range&from=2026&to=2027&via=today', want: { kind: 'redirect', to: '/japan/1990?mode=range&from=2026&to=2027' } },
  { path: '/japan/1990', search: '?via=today', want: { kind: 'redirect', to: '/japan/1990' } },
  { path: '/japan/2026', search: '?mode=today', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026?mode=range&from=2026&to=2026&via=today' } },
  // era (J8): the default is elided; the opposite value is kept
  { path: '/japan/2050', search: '', clock: clock2026, want: { kind: 'country', era: null } },
  { path: '/japan/2050', search: '?era=all', clock: clock2026, want: { kind: 'redirect', to: '/japan/2050' } },
  { path: '/japan/2050', search: '?era=obs', clock: clock2026, want: { kind: 'country', era: 'obs' } },
  { path: '/japan/2026', search: '?era=obs', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?era=all', clock: clock2026, want: { kind: 'country', era: 'all' } },
  { path: '/japan/2027', search: '?era=all', clock: clock2026, want: { kind: 'redirect', to: '/japan/2027' } }, // 2027 is projected today
  { path: '/japan/2027', search: '?era=all', clock: clock2027b, want: { kind: 'country', era: 'all' } }, // …but nowcast next year
  { path: '/japan/2026', search: '?era=maybe', want: { kind: 'redirect', to: '/japan/2026' } },
  // scope · floor · metric · sex · k · div
  { path: '/japan/2026', search: '?scope=all', want: { kind: 'country', scope: 'all' } },
  { path: '/japan/2026', search: '?scope=c', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?minpop=100000', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?minpop=0', want: { kind: 'country', minpop: 0 } },
  { path: '/japan/2026', search: '?minpop=1000000', want: { kind: 'country', minpop: 1_000_000 } },
  { path: '/japan/2026', search: '?minpop=lots', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?metric=w1', want: { kind: 'country', metric: 'w1' } },
  { path: '/japan/2026', search: '?metric=blend', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?metric=clr', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?metric=visual', want: visual ? { kind: 'country', metric: 'visual' } : { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?sex=1', want: { kind: 'country', sex: '1' } },
  { path: '/japan/2026', search: '?sex=3', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?k=10', want: { kind: 'country', k: 10 } },
  { path: '/japan/2026', search: '?k=7', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?div=0', want: { kind: 'country', div: 0 } },
  { path: '/japan/2026', search: '?div=2', want: { kind: 'country', div: 2 } },
  { path: '/japan/2026', search: '?div=0.5', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/2026', search: '?div=4', want: { kind: 'redirect', to: '/japan/2026' } },
  // trend · L
  { path: '/japan/2026', search: '?trend=motion', want: { kind: 'country', trend: 'motion', L: 10 } },
  { path: '/japan/2026', search: '?trend=motion&L=10', want: { kind: 'redirect', to: '/japan/2026?trend=motion' } },
  { path: '/japan/2026', search: '?trend=path&L=20', want: { kind: 'country', trend: 'path', L: 20 } },
  { path: '/japan/2026', search: '?L=5', want: { kind: 'redirect', to: '/japan/2026' } }, // L without trend
  { path: '/japan/2026', search: '?trend=wobble', want: { kind: 'redirect', to: '/japan/2026' } },
  { path: '/japan/1955', search: '?trend=motion', want: { kind: 'redirect', to: '/japan/1955' } }, // window reaches before 1950
  { path: '/japan/1955', search: '?trend=motion&L=5', want: { kind: 'country', trend: 'motion', L: 5 } },
  // fixed parameter order: display options first, then the search constraints
  { path: '/japan/2026', search: '?k=10&mode=any&unit=abs', want: { kind: 'redirect', to: '/japan/2026?unit=abs&mode=any&k=10' } },
  { path: '/japan/2026', search: '?unit=abs&mode=any&k=10', want: { kind: 'country', unit: 'abs', mode: 'any', k: 10 } },
  // hub redirect keeps the constraints
  { path: '/japan', search: '?mode=any&k=20', clock: clock2026, want: { kind: 'redirect', to: '/japan/2026?mode=any&k=20' } },
];

describe('router.parse — M2 search constraints', () => {
  for (const c of searchCases) {
    it(`${c.path}${c.search}${c.clock ? ` @${c.clock().getFullYear()}` : ''}`, () => {
      const got = parse(c.path, c.search, '/', { clock: c.clock ?? clock2026 });
      expect(got).toMatchObject(c.want);
    });
  }

  it('every M2 redirect target is a fixed point under the same clock', () => {
    for (const c of searchCases) {
      const clock = c.clock ?? clock2026;
      const got = parse(c.path, c.search, '/', { clock });
      if (got.kind !== 'redirect') continue;
      const [p, s = ''] = got.to.split('?');
      expect(parse(p!, s ? '?' + s : '', '/', { clock })).toEqual(got.query);
    }
  });

  it('a canonical M2 URL parses to a query whose canonical form is the input', () => {
    const url = '/japan/1990?axis=pin10&mode=range&from=2026&to=2026&via=today&era=all&scope=all&minpop=0&metric=l2&sex=1&k=20&div=2&trend=path&L=20';
    const [p, s] = url.split('?');
    const r = parse(p!, '?' + s, '/', { clock: clock2026 });
    expect(r.kind).toBe('country');
    if (r.kind === 'country') expect(canonical(r, '/')).toBe(url);
  });
});

describe('normaliseSearch / searchParams / effectiveEra', () => {
  it('fills defaults from nothing', () => {
    expect(normaliseSearch({}, 2026, 2026)).toEqual(DEFAULT_SEARCH);
    expect(searchParams(DEFAULT_SEARCH)).toEqual([]);
  });
  it('resolves today against the given current year and keeps via only for a one-year range', () => {
    const s = normaliseSearch({ mode: 'today' }, 1990, 2031);
    expect(s).toMatchObject({ mode: 'range', from: 2031, to: 2031, via: 'today' });
    expect(normaliseSearch({ mode: 'range', from: 2000, to: 2010, via: 'today' }, 1990, 2026).via).toBeNull();
  });
  it('drops n/from/to/via/L when their mode or trend is off', () => {
    expect(normaliseSearch({ mode: 'same', n: 3, from: 1990, to: 2000, via: 'today', L: 20 }, 2026, 2026)).toEqual(DEFAULT_SEARCH);
  });
  it('J8: era equal to the default becomes null; the other value stays', () => {
    expect(normaliseSearch({ era: 'obs' }, 2026, 2026).era).toBeNull();
    expect(normaliseSearch({ era: 'all' }, 2026, 2026).era).toBe('all');
    expect(normaliseSearch({ era: 'all' }, 2050, 2026).era).toBeNull();
    expect(normaliseSearch({ era: 'obs' }, 2050, 2026).era).toBe('obs');
    expect(effectiveEra({ year: 2050, era: null }, 2026)).toBe('all');
    expect(effectiveEra({ year: 2050, era: 'obs' }, 2026)).toBe('obs');
    expect(effectiveEra({ year: 1990, era: null }, 2026)).toBe('obs');
  });
  it('trend windows must stay inside the corpus', () => {
    expect(normaliseSearch({ trend: 'motion', L: 20 }, 1965, 2026).trend).toBeNull();
    expect(normaliseSearch({ trend: 'motion', L: 20 }, 1970, 2026)).toMatchObject({ trend: 'motion', L: 20 });
  });
  it('visual falls back to blend when the build exposes no image space', () => {
    expect(normaliseSearch({ metric: 'visual' }, 2026, 2026, { visual: false }).metric).toBe('blend');
    expect(normaliseSearch({ metric: 'visual' }, 2026, 2026, { visual: true }).metric).toBe('visual');
  });
  it('emits params in the fixed order with defaults elided', () => {
    const s = normaliseSearch({ mode: 'range', from: 1990, to: 2026, era: 'all', minpop: 0, k: 20, div: 0, trend: 'motion', L: 5 }, 2026, 2026);
    expect(searchParams(s)).toEqual([
      ['mode', 'range'], ['from', '1990'], ['to', '2026'], ['era', 'all'], ['minpop', '0'], ['k', '20'], ['div', '0'], ['trend', 'motion'], ['L', '5'],
    ]);
  });
  it('countryQuery takes the current year for the era default', () => {
    expect(countryQuery('JPN', 2050, { era: 'all' }, 2026).era).toBeNull();
    expect(countryQuery('JPN', 2050, { era: 'all' }, 2051).era).toBe('all');
    expect(canonical(countryQuery('JPN', 2050, { era: 'obs', mode: 'any' }, 2026), '/')).toBe('/japan/2050?mode=any&era=obs');
  });
});

// ---------------------------------------------------------------------------------------------- M3 compare route

import { compareQuery, compareSearch, parseCompareInput } from './router.ts';

type CCase = { path: string; search?: string; base?: string; clock?: () => Date; want: Record<string, unknown> };
const compareCases: CCase[] = [
  // canonical pairs
  { path: '/compare/japan/2026/italy/2026', want: { kind: 'compare', a: 'JPN', ya: 2026, b: 'ITA', yb: 2026, view: 'overlay', from: null, era: null, metric: 'blend', sex: '2' } },
  { path: '/compare/south-korea/2026/japan/2008', want: { kind: 'compare', a: 'KOR', ya: 2026, b: 'JPN', yb: 2008 } },
  { path: '/compare/japan/2026/japan/1990', want: { kind: 'compare', a: 'JPN', b: 'JPN', ya: 2026, yb: 1990 } }, // own trajectory
  { path: '/compare/world/2026/japan/2026', want: { kind: 'compare', a: 'agg-900', b: 'JPN' } },
  // aliases / case / trailing slash → canonical slugs, same query
  { path: '/compare/KOR/2026/jpn/2008', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/2008' } },
  { path: '/Compare/Korea/2026/Japan/2008/', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/2008' } },
  { path: '/compare/united-states-of-america/2026/agg-900/2026', want: { kind: 'redirect', to: '/compare/united-states/2026/world/2026' } },
  // best: kept unresolved by the router (the store resolves it); from=best is redundant while yb is best
  { path: '/compare/south-korea/2026/japan/best', want: { kind: 'compare', yb: 'best', from: null } },
  { path: '/compare/south-korea/2026/japan/BEST', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/best' } },
  { path: '/compare/south-korea/2026/japan/best', search: '?from=best', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/best' } },
  // from=best on a concrete year: canonical, kept (the resolved form the store writes)
  { path: '/compare/south-korea/2026/japan/2008', search: '?from=best', want: { kind: 'compare', yb: 2008, from: 'best' } },
  { path: '/compare/south-korea/2026/japan/2008', search: '?from=elsewhere', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/2008' } },
  // view: default elided, others kept, invalid dropped
  { path: '/compare/japan/2026/italy/2026', search: '?view=overlay', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2026' } },
  { path: '/compare/japan/2026/italy/2026', search: '?view=diff', want: { kind: 'compare', view: 'diff' } },
  { path: '/compare/japan/2026/italy/2026', search: '?view=side', want: { kind: 'compare', view: 'side' } },
  { path: '/compare/japan/2026/italy/2026', search: '?view=3d', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2026' } },
  // display options ride along; fixed order axis, unit, view, from, era, metric, sex
  { path: '/compare/japan/2026/italy/2026', search: '?unit=abs&axis=noclip', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2026?axis=noclip&unit=abs' } },
  { path: '/compare/south-korea/2026/japan/2008', search: '?sex=1&metric=l2&from=best&view=diff', want: { kind: 'redirect', to: '/compare/south-korea/2026/japan/2008?view=diff&from=best&metric=l2&sex=1' } },
  { path: '/compare/japan/2026/italy/2026', search: '?metric=blend&sex=2', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2026' } },
  { path: '/compare/japan/2026/italy/2026', search: '?metric=clr', want: { kind: 'redirect', to: '/compare/japan/2026/italy/2026' } },
  // era: J8 default from A's year is elided
  { path: '/compare/japan/2026/italy/best', search: '?era=obs', clock: clock2026, want: { kind: 'redirect', to: '/compare/japan/2026/italy/best' } },
  { path: '/compare/japan/2026/italy/best', search: '?era=all', clock: clock2026, want: { kind: 'compare', era: 'all' } },
  { path: '/compare/japan/2050/italy/best', search: '?era=all', clock: clock2026, want: { kind: 'redirect', to: '/compare/japan/2050/italy/best' } },
  { path: '/compare/japan/2050/italy/best', search: '?era=obs', clock: clock2026, want: { kind: 'compare', era: 'obs' } },
  // validation
  { path: '/compare/japan/2026/italy', want: { kind: 'notfound' } },
  { path: '/compare/japan/2026/italy/2026/extra', want: { kind: 'notfound' } },
  { path: '/compare/japan/best/italy/2026', want: { kind: 'notfound' } }, // best is for B only
  { path: '/compare/japan/1949/italy/2026', want: { kind: 'notfound' } },
  { path: '/compare/japan/2026/italy/2101', want: { kind: 'notfound' } },
  { path: '/compare/japan/2026/narnia/2026', want: { kind: 'notfound' } },
  { path: '/compare', want: { kind: 'notfound' } },
  // base prefix
  { path: `${PAGES}compare/JPN/2026/ITA/2026`, base: PAGES, want: { kind: 'redirect', to: `${PAGES}compare/japan/2026/italy/2026` } },
  { path: `${PAGES}compare/japan/2026/italy/best`, base: PAGES, want: { kind: 'compare', yb: 'best' } },
];

describe('router.parse — M3 compare', () => {
  for (const c of compareCases) {
    it(`${c.base ?? '/'} ${c.path}${c.search ?? ''}`, () => {
      expect(parse(c.path, c.search ?? '', c.base ?? '/', { clock: c.clock ?? clock2026 })).toMatchObject(c.want);
    });
  }

  it('every compare redirect target is a fixed point', () => {
    for (const c of compareCases) {
      const clock = c.clock ?? clock2026;
      const got = parse(c.path, c.search ?? '', c.base ?? '/', { clock });
      if (got.kind !== 'redirect') continue;
      const [p, s = ''] = got.to.split('?');
      expect(parse(p!, s ? '?' + s : '', c.base ?? '/', { clock })).toEqual(got.query);
    }
  });

  it('a canonical compare URL round-trips through canonical()', () => {
    const url = '/compare/south-korea/2026/japan/2008?axis=pin10&unit=abs&view=side&from=best&era=all&metric=l2&sex=1';
    const [p, s] = url.split('?');
    const r = parse(p!, '?' + s, '/', { clock: clock2026 });
    expect(r.kind).toBe('compare');
    if (r.kind === 'compare') expect(canonical(r, '/')).toBe(url);
  });

  it('compareQuery: from=best needs a concrete yb; era default elided against A\'s year; visual gated', () => {
    expect(compareQuery('KOR', 2026, 'JPN', 'best', { from: 'best' }, 2026).from).toBeNull();
    expect(compareQuery('KOR', 2026, 'JPN', 2008, { from: 'best' }, 2026).from).toBe('best');
    expect(compareQuery('KOR', 2026, 'JPN', 2008, { era: 'obs' }, 2026).era).toBeNull();
    expect(compareQuery('KOR', 2050, 'JPN', 2008, { era: 'obs' }, 2026).era).toBe('obs');
    expect(compareQuery('KOR', 2026, 'JPN', 2008, { metric: 'visual' }, 2026, false).metric).toBe('blend');
    expect(compareQuery('KOR', 2026, 'JPN', 2008, { metric: 'visual' }, 2026, true).metric).toBe('visual');
    expect(canonical(compareQuery('kor', 2026, 'jpn', 2008, { from: 'best' }, 2026), PAGES)).toBe(`${PAGES}compare/south-korea/2026/japan/2008?from=best`);
    expect(canonical(compareQuery('KOR', 2026, 'JPN', 'best', {}, 2026), '/')).toBe('/compare/south-korea/2026/japan/best');
  });

  it('compareSearch / parseCompareInput are inverse on the non-default set', () => {
    const q = compareQuery('KOR', 2026, 'JPN', 2008, { view: 'diff', from: 'best', era: 'all', metric: 'w1', sex: '1', unit: 'abs' }, 2026);
    const s = compareSearch(q);
    expect(s).toBe('?unit=abs&view=diff&from=best&era=all&metric=w1&sex=1');
    expect(parseCompareInput(s)).toEqual({ view: 'diff', from: 'best', era: 'all', metric: 'w1', sex: '1' });
    expect(parseCompareInput('')).toEqual({ view: 'overlay', from: null, era: null, metric: 'blend', sex: '2' });
  });

  it('/about is a static query with a canonical form', () => {
    expect(canonical({ kind: 'static', page: 'about' }, PAGES)).toBe(`${PAGES}about`);
    expect(parse(`${PAGES}about`, '', PAGES)).toEqual({ kind: 'static', page: 'about' });
    expect(canonical({ kind: 'static', page: 'evidence' }, PAGES)).toBe(`${PAGES}evidence`);
    expect(canonical({ kind: 'eval', tool: 'triplets' }, PAGES)).toBe(`${PAGES}eval/triplets`);
    expect(canonical(countryQuery('JPN', 2026, { lens: 'econ' }, 2026), '/')).toBe('/japan/2026?lens=econ');
    expect(canonical(countryQuery('JPN', 2026, { lens: null }, 2026), '/')).toBe('/japan/2026');
    expect(countryQuery('JPN', 2026, {}, 2026).lens).toBeNull();
    expect(canonical(compareQuery('JPN', 2026, 'ITA', 2008, { lens: 'econ', view: 'diff' }, 2026), '/')).toBe('/compare/japan/2026/italy/2008?view=diff&lens=econ');
  });
});
