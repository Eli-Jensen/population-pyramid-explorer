import { describe, expect, it } from 'vitest';
import { countryQuery } from './router.ts';
import { currentRoute, href, navigate, navigateTo, onPopState, type HistoryLike, type LocationLike } from './url.ts';

/** Minimal history + location pair that behaves like the browser's. */
export function fakeBrowser(start = '/') {
  const [p, s = ''] = start.split('?');
  const location: LocationLike = { pathname: p!, search: s ? '?' + s : '' };
  const log: { op: 'push' | 'replace'; url: string }[] = [];
  const stack: string[] = [start];
  const set = (url: string) => {
    const [pp, ss = ''] = url.split('?');
    location.pathname = pp!;
    location.search = ss ? '?' + ss : '';
  };
  const history: HistoryLike = {
    pushState: (_d, _t, url) => {
      log.push({ op: 'push', url: url! });
      stack.push(url!);
      set(url!);
    },
    replaceState: (_d, _t, url) => {
      log.push({ op: 'replace', url: url! });
      stack[stack.length - 1] = url!;
      set(url!);
    },
  };
  const target = new EventTarget();
  const back = () => {
    if (stack.length > 1) stack.pop();
    set(stack[stack.length - 1]!);
    target.dispatchEvent(new Event('popstate'));
  };
  return { history, location, log, stack, target, back, href: () => location.pathname + location.search };
}

const PAGES = '/population-pyramid-explorer/';

describe('url.href', () => {
  it('emits canonical links with the base prefix and defaults elided', () => {
    expect(href(countryQuery('JPN', 2026, { axis: 'fit' }), PAGES)).toBe(`${PAGES}japan/2026`);
    expect(href(countryQuery('USA', 2026, { unit: 'abs' }), '/')).toBe('/united-states/2026?unit=abs');
  });
});

describe('url.navigate', () => {
  it('pushState by default, replaceState on request, no-op when unchanged', () => {
    const b = fakeBrowser('/');
    const env = { base: '/', history: b.history, location: b.location };
    expect(navigate(countryQuery('JPN', 2026), env)).toBe(true);
    expect(navigate(countryQuery('JPN', 2026), env)).toBe(false); // same URL → nothing
    expect(navigate(countryQuery('JPN', 2027), { replace: true, ...env })).toBe(true);
    expect(b.log).toEqual([
      { op: 'push', url: '/japan/2026' },
      { op: 'replace', url: '/japan/2027' },
    ]);
    expect(b.href()).toBe('/japan/2027');
  });

  it('respects the base prefix', () => {
    const b = fakeBrowser(PAGES);
    const env = { base: PAGES, history: b.history, location: b.location };
    navigate(countryQuery('KOR', 2026), env);
    expect(b.href()).toBe(`${PAGES}south-korea/2026`);
    expect(currentRoute(env)).toMatchObject({ kind: 'country', id: 'KOR', year: 2026 });
  });

  it('navigateTo applies raw redirect targets', () => {
    const b = fakeBrowser('/USA/');
    const env = { base: '/', history: b.history, location: b.location };
    const r = currentRoute(env, { clock: () => new Date(2026, 2, 1) });
    expect(r.kind).toBe('redirect');
    if (r.kind === 'redirect') navigateTo(r.to, { replace: true, ...env });
    expect(b.log).toEqual([{ op: 'replace', url: '/united-states/2026' }]);
  });

  it('returns false without a history object', () => {
    expect(navigateTo('/x', { history: undefined, location: undefined })).toBe(false);
  });
});

describe('url.onPopState', () => {
  it('delivers the parsed route on Back and unsubscribes cleanly', () => {
    const b = fakeBrowser('/japan/2026');
    const env = { base: '/', history: b.history, location: b.location, target: b.target };
    const seen: string[] = [];
    const off = onPopState((r) => seen.push(r.kind === 'country' ? `${r.id}/${r.year}` : r.kind), env);
    navigate(countryQuery('JPN', 2030), env);
    b.back();
    expect(seen).toEqual(['JPN/2026']);
    off();
    navigate(countryQuery('JPN', 2031), env);
    b.back();
    expect(seen).toEqual(['JPN/2026']);
  });
});
