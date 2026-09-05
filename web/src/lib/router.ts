// Pure router (PLAN §7): pathname + search → Route; Query → canonical URL. No DOM, no globals.
//
// Routes (M1):            '/'                         → home
//                         '/{slug}'                   → Redirect to '/{slug}/{currentYear}' (hub)
//                         '/{slug}/{year}'            → CountryQuery (year 1950–2100)
// Reserved (M3):          '/compare/…', '/about', '/evidence', '/eval/…' → Placeholder
// Anything else           → NotFound.
// Canonical form: no trailing slash, lowercase slug, canonical slug (aliases redirect), defaults elided,
// query params in a fixed order. Non-canonical URLs return a Redirect (the app applies it with replaceState).
//
// M2 search constraints (PLAN §6 table) live in the same query string, after the display options:
//   ?axis= &unit= &mode=same|near|range|any &n= &from= &to= &via=today &era=obs|all &scope=c|all
//   &minpop=<persons> &metric= &sex=2|1 &k=3|5|10|20 &div=0|0.5|2 &trend=motion|path &L=5|10|20
// `mode=today` is INPUT sugar: it resolves to `mode=range&from=Y&to=Y&via=today` (Y = current year) and the
// app replaceStates the concrete form, so a pasted link reproduces the exact view next year (J6). `near` stays
// `mode=near&n=N` in the URL and is expanded to [y−n, y+n] by the search layer (one code path there).
// `era` is elided when it equals the J8 default (`obs` for year ≤ currentYear, else `all`) — the query
// object stores `era: null` for "default", so `canonical()` needs no clock.

import { resolve, currentYear, isValidYear, meta, YEAR_MAX, YEAR_MIN, type Clock, type Entity } from './entities.ts';

// ---- display options (M1) ---------------------------------------------------------------------------

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

// ---- search constraints (M2, PLAN §6) ------------------------------------------------------------------

/** Year modes accepted in the URL; `today` never survives normalisation (it becomes a one-year range). */
export const YEAR_MODES = ['same', 'near', 'range', 'any', 'today'] as const;
export type YearMode = (typeof YEAR_MODES)[number];
export type StoredYearMode = Exclude<YearMode, 'today'>;
export type EraMode = 'obs' | 'all';
export type Scope = 'c' | 'all';
export const METRICS = ['blend', 'l2', 'w1', 'l2s', 'hel', 'feat', 'w1sex', 'w1bal', 'visual'] as const;
export type Metric = (typeof METRICS)[number];
/** Menu structure (PLAN §4.3 as amended by the M2 brief): visible · advanced · visual (always present, experimental). */
export const METRICS_VISIBLE: readonly Metric[] = ['blend', 'w1', 'l2'];
export const METRICS_ADVANCED: readonly Metric[] = ['l2s', 'hel', 'feat', 'w1sex', 'w1bal'];
export type Sex = '2' | '1';
export const K_VALUES = [3, 5, 10, 20] as const;
export type K = (typeof K_VALUES)[number];
export const DIV_VALUES = [0, 0.5, 2] as const;
export type Div = (typeof DIV_VALUES)[number];
/** Named diversity presets (PLAN §5 as re-calibrated; mirrors `search.DIV_PRESETS`). `div=` stays numeric in the URL. */
export const DIV_PRESETS: Readonly<Record<'strict' | 'balanced' | 'spread', Div>> = { strict: 0, balanced: 0.5, spread: 2 };
export const TRENDS = ['motion', 'path'] as const;
export type Trend = (typeof TRENDS)[number];
export const L_VALUES = [5, 10, 20] as const;
export type L = (typeof L_VALUES)[number];
/** Population-floor presets in PERSONS (candidate's own-year population); 100k drops the microstates. */
export const MINPOP_PRESETS = [0, 10_000, 100_000, 1_000_000] as const;
export const DEFAULT_N = 10;

export interface SearchOptions {
  mode: StoredYearMode; // same (default) · near · range · any
  n: number; // half-width of `near`, ≥ 1 (10)
  from: number | null; // `range` edges (inclusive); null = corpus edge (1950 / 2100)
  to: number | null;
  via: 'today' | null; // marks a range produced by the Today control (from === to)
  era: EraMode | null; // null = J8 default: obs for year ≤ currentYear, else all
  scope: Scope; // c = countries (default) · all = countries + aggregates
  minpop: number; // persons (default 100 000)
  metric: Metric;
  sex: Sex; // 2 = two-sex (default) · 1 = total only
  k: K;
  div: Div; // MMR β for the opposites (0.5 balanced)
  trend: Trend | null; // trajectory matching (motion / path) — off by default
  L: L; // trend window in years (10)
}
export const DEFAULT_SEARCH: Readonly<SearchOptions> = {
  mode: 'same',
  n: DEFAULT_N,
  from: null,
  to: null,
  via: null,
  era: null,
  scope: 'c',
  minpop: 100_000,
  metric: 'blend',
  sex: '2',
  k: 5,
  div: 0.5,
  trend: null,
  L: 10,
};
/** Raw, un-normalised input (URL params or a control) — `mode` may still be the `today` sugar. */
export type SearchInput = Partial<Omit<SearchOptions, 'mode'> & { mode: YearMode }>;

export interface HomeQuery {
  kind: 'home';
}
export interface CountryQuery extends DisplayOptions, SearchOptions {
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
  clock?: Clock; // injectable for tests (hub redirect year, era default, today sugar)
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
function pickOrNull<T extends string>(allowed: readonly T[], v: string | null): T | null {
  return v !== null && (allowed as readonly string[]).includes(v) ? (v as T) : null;
}
function pickNum<T extends number>(allowed: readonly T[], v: string | null, dflt: T): T {
  if (v === null || !/^\d+(\.\d+)?$/.test(v)) return dflt;
  const n = Number(v);
  return (allowed as readonly number[]).includes(n) ? (n as T) : dflt;
}
function intOrNull(v: string | null): number | null {
  return v !== null && /^\d{1,7}$/.test(v) ? Number(v) : null;
}
function yearOrNull(v: string | null): number | null {
  const y = v !== null && /^\d{4}$/.test(v) ? Number(v) : null;
  return y !== null && isValidYear(y) ? y : null;
}

function params(search: string): URLSearchParams {
  return new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
}

/** Parse the display options from a search string; unknown params and invalid values fall back to defaults. */
export function parseOptions(search: string): DisplayOptions {
  const sp = params(search);
  return {
    axis: pick(AXES, sp.get('axis'), DEFAULT_OPTIONS.axis),
    unit: pick(UNITS, sp.get('unit'), DEFAULT_OPTIONS.unit),
  };
}

/** Whether the `visual` metric may be selected in this build (DECISION 4: `meta.verdicts.exposed_visual`). */
export function visualExposed(m: typeof meta = meta): boolean {
  return !!m.verdicts?.exposed_visual?.model;
}

/**
 * Parse the search constraints from a search string. Invalid values → defaults; `mode=today` is kept as
 * input sugar for `normaliseSearch`. Nothing here depends on the year or the clock.
 */
export function parseSearchInput(search: string, opts: { visual?: boolean } = {}): SearchInput {
  const sp = params(search);
  const out: SearchInput = {
    mode: pick(YEAR_MODES, sp.get('mode'), DEFAULT_SEARCH.mode),
    era: pickOrNull(['obs', 'all'] as const, sp.get('era')),
    scope: pick(['c', 'all'] as const, sp.get('scope'), DEFAULT_SEARCH.scope),
    metric: pick(METRICS, sp.get('metric'), DEFAULT_SEARCH.metric),
    sex: pick(['2', '1'] as const, sp.get('sex'), DEFAULT_SEARCH.sex),
    k: pickNum(K_VALUES, sp.get('k'), DEFAULT_SEARCH.k),
    div: pickNum(DIV_VALUES, sp.get('div'), DEFAULT_SEARCH.div),
    trend: pickOrNull(TRENDS, sp.get('trend')),
    L: pickNum(L_VALUES, sp.get('L'), DEFAULT_SEARCH.L),
    via: sp.get('via') === 'today' ? 'today' : null,
    from: yearOrNull(sp.get('from')),
    to: yearOrNull(sp.get('to')),
  };
  const n = intOrNull(sp.get('n'));
  out.n = n !== null && n >= 1 && n <= YEAR_MAX - YEAR_MIN ? n : DEFAULT_SEARCH.n;
  const minpop = intOrNull(sp.get('minpop'));
  out.minpop = minpop !== null ? minpop : DEFAULT_SEARCH.minpop;
  if (out.metric === 'visual' && !(opts.visual ?? visualExposed())) out.metric = DEFAULT_SEARCH.metric;
  return out;
}

/**
 * The ONE place that turns raw constraints into a stored `SearchOptions` for a given (year, currentYear):
 *  - `today` → `range [currentYear, currentYear]` with `via=today`;
 *  - `n` only with `near`; `from`/`to`/`via` only with `range` (corpus edges elided to null, swapped if reversed;
 *    `via=today` only when `from === to`);
 *  - `era` equal to the J8 default → null;
 *  - `trend` whose window reaches before 1950 is dropped; `L` is meaningful only with `trend`;
 *  - `visual` only when the build exposes an image space.
 * Used by `parse` (with the clock) and by the store on every constraint / year change, so the URL never carries a
 * constraint that the search would ignore.
 */
export function normaliseSearch(raw: SearchInput, year: number, curYear: number, opts: { visual?: boolean } = {}): SearchOptions {
  let mode: YearMode = raw.mode ?? DEFAULT_SEARCH.mode;
  let n = raw.n ?? DEFAULT_SEARCH.n;
  let from = raw.from ?? null;
  let to = raw.to ?? null;
  let via = raw.via ?? null;
  if (mode === 'today') {
    mode = 'range';
    from = to = curYear;
    via = 'today';
  }
  if (mode !== 'near') n = DEFAULT_SEARCH.n;
  if (!Number.isInteger(n) || n < 1) n = DEFAULT_SEARCH.n;
  if (mode !== 'range') {
    from = to = null;
    via = null;
  } else {
    if (from !== null && to !== null && from > to) [from, to] = [to, from];
    via = via === 'today' && from !== null && from === to ? 'today' : null;
    if (from === YEAR_MIN) from = null;
    if (to === YEAR_MAX) to = null;
  }
  let era = raw.era ?? null;
  if (era === defaultEra(year, curYear)) era = null;
  let trend = raw.trend ?? null;
  let L = raw.L ?? DEFAULT_SEARCH.L;
  if (trend && year - L < YEAR_MIN) trend = null;
  if (!trend) L = DEFAULT_SEARCH.L;
  let metric = raw.metric ?? DEFAULT_SEARCH.metric;
  if (metric === 'visual' && !(opts.visual ?? visualExposed())) metric = DEFAULT_SEARCH.metric;
  const minpop = raw.minpop !== undefined && Number.isInteger(raw.minpop) && raw.minpop >= 0 ? raw.minpop : DEFAULT_SEARCH.minpop;
  return {
    mode: mode as StoredYearMode,
    n,
    from,
    to,
    via,
    era,
    scope: raw.scope ?? DEFAULT_SEARCH.scope,
    minpop,
    metric,
    sex: raw.sex ?? DEFAULT_SEARCH.sex,
    k: raw.k ?? DEFAULT_SEARCH.k,
    div: raw.div ?? DEFAULT_SEARCH.div,
    trend,
    L,
  };
}

/** Only the non-default options, in a fixed order — the serialised form of PLAN §6 "defaults elided". */
export function elideDefaults(o: Partial<DisplayOptions>): Partial<DisplayOptions> {
  const out: Partial<DisplayOptions> = {};
  if (o.axis !== undefined && o.axis !== DEFAULT_OPTIONS.axis) out.axis = o.axis;
  if (o.unit !== undefined && o.unit !== DEFAULT_OPTIONS.unit) out.unit = o.unit;
  return out;
}

/** Non-default search constraints as `[param, value]` pairs in canonical order (input assumed normalised). */
export function searchParams(s: Partial<SearchOptions>): Array<[string, string]> {
  const p: Array<[string, string]> = [];
  const mode = s.mode ?? DEFAULT_SEARCH.mode;
  if (mode !== DEFAULT_SEARCH.mode) p.push(['mode', mode]);
  if (mode === 'near' && s.n !== undefined && s.n !== DEFAULT_SEARCH.n) p.push(['n', String(s.n)]);
  if (mode === 'range') {
    if (s.from != null) p.push(['from', String(s.from)]);
    if (s.to != null) p.push(['to', String(s.to)]);
    if (s.via === 'today') p.push(['via', 'today']);
  }
  if (s.era) p.push(['era', s.era]);
  if (s.scope !== undefined && s.scope !== DEFAULT_SEARCH.scope) p.push(['scope', s.scope]);
  if (s.minpop !== undefined && s.minpop !== DEFAULT_SEARCH.minpop) p.push(['minpop', String(s.minpop)]);
  if (s.metric !== undefined && s.metric !== DEFAULT_SEARCH.metric) p.push(['metric', s.metric]);
  if (s.sex !== undefined && s.sex !== DEFAULT_SEARCH.sex) p.push(['sex', s.sex]);
  if (s.k !== undefined && s.k !== DEFAULT_SEARCH.k) p.push(['k', String(s.k)]);
  if (s.div !== undefined && s.div !== DEFAULT_SEARCH.div) p.push(['div', String(s.div)]);
  if (s.trend) {
    p.push(['trend', s.trend]);
    if (s.L !== undefined && s.L !== DEFAULT_SEARCH.L) p.push(['L', String(s.L)]);
  }
  return p;
}

/** '?axis=pin10&unit=abs&mode=any…' or '' — the canonical search string for a set of options. */
export function optionsSearch(o: Partial<DisplayOptions & SearchOptions>): string {
  const e = elideDefaults(o);
  const parts: string[] = [];
  if (e.axis) parts.push(`axis=${e.axis}`);
  if (e.unit) parts.push(`unit=${e.unit}`);
  for (const [k, v] of searchParams(o)) parts.push(`${k}=${v}`);
  return parts.length ? '?' + parts.join('&') : '';
}

// ---- era (J8) ---------------------------------------------------------------------------------------

/** J8: a query from a projected year defaults the cross-year era to `all` (PLAN §6). */
export function defaultEra(year: number, curYear: number): EraMode {
  return year > curYear ? 'all' : 'obs';
}

/** The era the search actually uses: the explicit URL value or the J8 default. */
export function effectiveEra(q: Pick<CountryQuery, 'year' | 'era'>, curYear: number): EraMode {
  return q.era ?? defaultEra(q.year, curYear);
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

/**
 * Build a country query with defaults filled in and the search constraints normalised for (year, currentYear).
 * `curYear` defaults to the client clock; the store always passes its own.
 */
export function countryQuery(
  id: string,
  year: number,
  opts: Partial<DisplayOptions> & SearchInput = {},
  curYear: number = currentYear(),
): CountryQuery {
  return {
    kind: 'country',
    id,
    year,
    ...DEFAULT_OPTIONS,
    ...elideDefaults(opts),
    ...normaliseSearch(opts, year, curYear),
  };
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
  const curYear = currentYear(opts.clock);
  const options = { ...parseOptions(searchNorm), ...parseSearchInput(searchNorm) };

  if (segs.length === 1) {
    // hub: '/{slug}' → '/{slug}/{currentYear}'
    const q = countryQuery(entity.id, curYear, options, curYear);
    return { kind: 'redirect', to: canonical(q, b), query: q };
  }
  if (segs.length > 2) return { kind: 'notfound', path: '/' + segs.join('/') };

  const yearSeg = segs[1]!;
  if (!/^\d{4}$/.test(yearSeg)) return { kind: 'notfound', path: '/' + segs.join('/') };
  const year = Number(yearSeg);
  if (!isValidYear(year)) return { kind: 'notfound', path: '/' + segs.join('/') };

  const q = countryQuery(entity.id, year, options, curYear);
  return redirectIfNeeded(q, pathname + searchNorm, b);
}

function redirectIfNeeded(q: Query, actual: string, base: string): Route {
  const want = canonical(q, base);
  return want === actual ? q : { kind: 'redirect', to: want, query: q };
}

/** Type guards. */
export const isQuery = (r: Route): r is Query => r.kind === 'home' || r.kind === 'country' || r.kind === 'placeholder';
export const isCountry = (r: Route): r is CountryQuery => r.kind === 'country';
