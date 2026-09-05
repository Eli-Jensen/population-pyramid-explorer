// Pure router (PLAN §7): pathname + search → Route; Query → canonical URL. No DOM, no globals.
//
// Routes (M1):            '/'                         → home
//                         '/{slug}'                   → Redirect to '/{slug}/{currentYear}' (hub)
//                         '/{slug}/{year}'            → CountryQuery (year 1950–2100)
// Reserved (M2/M3):       '/compare/…', '/about', '/evidence', '/eval/…' → Placeholder
// Anything else           → NotFound.
// Canonical form: no trailing slash, lowercase slug, canonical slug (aliases redirect), defaults elided,
// query params in a fixed order. Non-canonical URLs return a Redirect (the app applies it with replaceState).

import { resolve, currentYear, isValidYear, type Clock, type Entity } from './entities.ts';

export const AXES = ['fit', 'pin10', 'noclip'] as const;
export type Axis = (typeof AXES)[number];
export const UNITS = ['pct', 'abs', 'pctsex'] as const;
export type Unit = (typeof UNITS)[number];

/** Display options that live in the URL (M1). Defaults are elided from emitted links. */
export interface DisplayOptions {
  axis: Axis; // fit = entities[].axis_pct · pin10 = clamp at 10 % · noclip = 0–17 %
  unit: Unit; // pct = % of total · abs = thousands · pctsex = % of own sex
}
export const DEFAULT_OPTIONS: Readonly<DisplayOptions> = { axis: 'fit', unit: 'pct' };

export interface HomeQuery {
  kind: 'home';
}
export interface CountryQuery extends DisplayOptions {
  kind: 'country';
  id: string; // entity id (ISO3 / agg-*)
  year: number;
}
export const PLACEHOLDER_ROUTES = ['compare', 'about', 'evidence', 'eval'] as const;
export type PlaceholderRoute = (typeof PLACEHOLDER_ROUTES)[number];
export interface PlaceholderQuery {
  kind: 'placeholder';
  route: PlaceholderRoute;
  segments: string[]; // path segments after the route name, lowercased
  search: string; // raw search string ('' or '?…'), untouched until the route is built
}
export type Query = HomeQuery | CountryQuery | PlaceholderQuery;

export interface Redirect {
  kind: 'redirect';
  to: string; // canonical URL (pathname + search) including the base prefix
  query: Query; // what `to` parses to
}
export interface NotFound {
  kind: 'notfound';
  path: string; // the offending path relative to base, for the 404 view
}
export type Route = Query | Redirect | NotFound;

export interface ParseOptions {
  clock?: Clock; // injectable for tests (hub redirect year)
}

// ---- base handling ------------------------------------------------------------------------------

/** Normalise a base to '/x/y/' form ('' or '/' → '/'). */
export function normaliseBase(base: string): string {
  let b = base.trim();
  if (!b.startsWith('/')) b = '/' + b;
  if (!b.endsWith('/')) b += '/';
  return b;
}

/** Strip the base prefix (case-insensitively) and return the remainder without leading slash, or null. */
function stripBase(pathname: string, base: string): string | null {
  const b = normaliseBase(base);
  const p = pathname.startsWith('/') ? pathname : '/' + pathname;
  if (b === '/') return p.slice(1);
  const bare = b.slice(0, -1); // '/population-pyramid-explorer'
  const lower = p.toLowerCase();
  if (lower === bare.toLowerCase()) return '';
  if (lower.startsWith(b.toLowerCase())) return p.slice(b.length);
  return null;
}

function segmentsOf(rest: string): string[] {
  return rest
    .split('/')
    .map((s) => {
      try {
        return decodeURIComponent(s);
      } catch {
        return s;
      }
    })
    .filter((s) => s.length > 0)
    .map((s) => s.toLowerCase());
}

// ---- options ----------------------------------------------------------------------------------------

function pick<T extends string>(allowed: readonly T[], v: string | null, dflt: T): T {
  return v !== null && (allowed as readonly string[]).includes(v) ? (v as T) : dflt;
}

/** Parse the display options from a search string; unknown params and invalid values fall back to defaults. */
export function parseOptions(search: string): DisplayOptions {
  const sp = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  return {
    axis: pick(AXES, sp.get('axis'), DEFAULT_OPTIONS.axis),
    unit: pick(UNITS, sp.get('unit'), DEFAULT_OPTIONS.unit),
  };
}

/** Only the non-default options, in a fixed order — the serialised form of PLAN §6 "defaults elided". */
export function elideDefaults(o: Partial<DisplayOptions>): Partial<DisplayOptions> {
  const out: Partial<DisplayOptions> = {};
  if (o.axis !== undefined && o.axis !== DEFAULT_OPTIONS.axis) out.axis = o.axis;
  if (o.unit !== undefined && o.unit !== DEFAULT_OPTIONS.unit) out.unit = o.unit;
  return out;
}

/** '?axis=pin10&unit=abs' or '' — the canonical search string for a set of options. */
export function optionsSearch(o: Partial<DisplayOptions>): string {
  const e = elideDefaults(o);
  const parts: string[] = [];
  if (e.axis) parts.push(`axis=${e.axis}`);
  if (e.unit) parts.push(`unit=${e.unit}`);
  return parts.length ? '?' + parts.join('&') : '';
}

// ---- era (kept for M2; J8 rule) ---------------------------------------------------------------------

export type EraMode = 'obs' | 'all';

/** J8: a query from a projected year defaults the cross-year era to `all` (PLAN §6). */
export function defaultEra(year: number, curYear: number): EraMode {
  return year > curYear ? 'all' : 'obs';
}

// ---- canonical --------------------------------------------------------------------------------------

/** Canonical URL (pathname + search) for a query, with the base prefix. */
export function canonical(query: Query, base: string): string {
  const b = normaliseBase(base);
  switch (query.kind) {
    case 'home':
      return b;
    case 'country': {
      const e = resolve(query.id);
      if (!e) throw new Error(`canonical(): unknown entity ${query.id}`);
      return `${b}${e.slug}/${query.year}${optionsSearch(query)}`;
    }
    case 'placeholder': {
      const path = [query.route, ...query.segments].join('/');
      return `${b}${path}${query.search}`;
    }
  }
}

/** Build a country query with defaults filled in. */
export function countryQuery(id: string, year: number, opts: Partial<DisplayOptions> = {}): CountryQuery {
  return { kind: 'country', id, year, ...DEFAULT_OPTIONS, ...elideDefaults(opts) };
}

// ---- parse ------------------------------------------------------------------------------------------

/**
 * Parse a location into a Route. `pathname` may carry the `base` prefix (GitHub Pages project site).
 * Returns a Redirect whenever the input is not already canonical, so the app can `replaceState` it.
 */
export function parse(pathname: string, search: string, base: string, opts: ParseOptions = {}): Route {
  const b = normaliseBase(base);
  const rest = stripBase(pathname, b);
  if (rest === null) return { kind: 'notfound', path: pathname };
  const segs = segmentsOf(rest);
  const searchNorm = search && !search.startsWith('?') ? '?' + search : search;

  if (segs.length === 0) {
    const q: HomeQuery = { kind: 'home' };
    return redirectIfNeeded(q, pathname + searchNorm, b);
  }

  const head = segs[0]!;
  if ((PLACEHOLDER_ROUTES as readonly string[]).includes(head)) {
    const q: PlaceholderQuery = {
      kind: 'placeholder',
      route: head as PlaceholderRoute,
      segments: segs.slice(1),
      search: searchNorm,
    };
    return redirectIfNeeded(q, pathname + searchNorm, b);
  }

  const entity: Entity | undefined = resolve(head);
  if (!entity) return { kind: 'notfound', path: '/' + segs.join('/') };
  const options = parseOptions(searchNorm);

  if (segs.length === 1) {
    // hub: '/{slug}' → '/{slug}/{currentYear}'
    const q = countryQuery(entity.id, currentYear(opts.clock), options);
    return { kind: 'redirect', to: canonical(q, b), query: q };
  }
  if (segs.length > 2) return { kind: 'notfound', path: '/' + segs.join('/') };

  const yearSeg = segs[1]!;
  if (!/^\d{4}$/.test(yearSeg)) return { kind: 'notfound', path: '/' + segs.join('/') };
  const year = Number(yearSeg);
  if (!isValidYear(year)) return { kind: 'notfound', path: '/' + segs.join('/') };

  const q = countryQuery(entity.id, year, options);
  return redirectIfNeeded(q, pathname + searchNorm, b);
}

function redirectIfNeeded(q: Query, actual: string, base: string): Route {
  const want = canonical(q, base);
  return want === actual ? q : { kind: 'redirect', to: want, query: q };
}

/** Type guards. */
export const isQuery = (r: Route): r is Query => r.kind === 'home' || r.kind === 'country' || r.kind === 'placeholder';
export const isCountry = (r: Route): r is CountryQuery => r.kind === 'country';
