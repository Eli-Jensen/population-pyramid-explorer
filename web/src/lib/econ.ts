/**
 * Economic-lens data (PLAN §7, M5): the decoder for `econ.{sha8}.ecz` and the accessors every econ component
 * reads. Tier 2b — fetched by `data.ts#loadEcon()` after the first paint, never in the first-paint set.
 *
 * File format (self-describing; the plan's fixed layout is the default when the header omits `arrays`):
 *
 *   u32 LE header length · JSON header (UTF-8) · body (typed arrays, little-endian, country-major, one value per
 *   (country, year) for year_min..year_max)
 *
 *   header = {
 *     version: 1, built, as_of,                 // as_of = derivation date of every market statistic
 *     year_min: 1950, year_max: 2024,           // (or `years: [min, max]`)
 *     ids: ['AFG', …],                          // ISO3 = entity id, file order (or `iso3: […]`)
 *     arrays: { name: { dtype: 'u16'|'i16'|'u8', offset, scale?, encoding?: 'log'|'linear', na } },
 *       gdppc   u16  encoding 'log', scale 4096 → value = exp(u / scale)   Maddison 2011$ (econ/splice.py: spliced past 2022)
 *       g_rgdp  i16  scale 0.01                → trailing 10-year real GDP/cap growth ending in the year, %/yr (econ/export_econ.py);
 *                                                 when the header carries no `g_rgdp_1y`, `g_rgdp` is read as ANNUAL growth
 *                                                 and the 10-year figure is the mean of the ten annual rates
 *       g_rgdp_1y i16 scale 0.01              → annual real GDP growth, 100·ln(rgdpna_t / rgdpna_{t−1}) (PWT; WDI 2024), optional
 *       tfr     u16  scale 0.001               → total fertility rate (WPP 2024)
 *       income  u8   1 = L · 2 = LM · 3 = UM · 4 = H (WB OGHIST, fiscal year; 0 = n/a — before FY1989 or unclassified)
 *       stage   u8   0 = n/a · 1 pre · 2 early · 3 late · 4 post-dividend (pipeline/typology.yaml, econ/typology.py)
 *     last_econ_year, income_labels, stage_labels, stage_hints,
 *     instruments: evals/instruments.yaml `countries` — { ISO3: { status, msci_class, mobility, events[],
 *                  tickers: [{ ticker, name, issuer, inception, status, delisted, liquidation_date, msci_class, status_url,
 *                              source_url, since_inception_cagr_pct, vt_same_window_pct, benchmark, window: [from, to],
 *                              cagr_10y_pct, cagr_10y_vt_pct, cagr_10y_window, cagr_10y_benchmark, cagr_10y_status,
 *                              cagr_10y_incomplete, max_dd_pct, as_of, annual?: { from_year, levels[] } }] } }
 *                  (a plain array of tickers per ISO3 is accepted too; `annual` year-end levels are optional and, when
 *                  present, let any y1→y2 window be derived — otherwise only the precomputed windows are shown)
 *     benchmark?: { vt: { from_year, levels[] }, vt_first_bar: '2008-06-24', proxy_until_year: 2008 },
 *     mobility?: { ISO3: … }, events?: { ISO3: [...] }, sources?: { … }
 *   }
 *
 * Every market number is a derived statistic (a CAGR, a drawdown, a date) beside VT over the identical window — never a
 * price series. Every accessor returns `null` for "n/a"; nothing here touches the DOM.
 */

import { gunzip, isGzip } from './math/gz.ts';

export type IncomeCode = 1 | 2 | 3 | 4;
export type Mobility = 'open' | 'restricted' | 'closed' | 'not_assessed';
export type InstrumentStatus = 'live' | 'liquidated' | 'liquidating';
export type VtFlag = 'vt' | 'vt_proxy' | 'none';

export interface ArraySpec {
  dtype: 'u16' | 'i16' | 'u8';
  offset: number; // bytes from the start of the body
  scale?: number; // multiplier (linear) or divisor of the log (encoding 'log')
  encoding?: 'linear' | 'log';
  na?: number; // sentinel meaning "no value"
}

export interface AnnualLevels {
  from_year: number;
  levels: number[];
}

/** A precomputed window statistic: instrument CAGR beside VT over the identical window (dates and years). */
export interface InstrumentWindow {
  label: 'since_inception' | '10y' | 'derived';
  from: string; // YYYY-MM-DD (or YYYY-12-31 for derived year-end windows)
  to: string;
  y1: number; // calendar year of `from`
  y2: number; // calendar year of `to`
  years: number;
  r: number | null; // %/yr
  rVt: number | null; // %/yr, VT (or proxy) over [from, to]
  vt: VtFlag;
  maxDd: number | null; // %, maximum drawdown over the window (null when not derived)
  basis?: string | null;
  incomplete?: string | null; // NAV-ladder gap note (liquidated funds), never dropped
  status?: string | null; // ok | manual_incomplete | …
}

/** The derived statistics block (flat in evals/instruments.yaml, nested under `stats` in the .ecz header). */
export interface RawStats {
  since_inception_cagr_pct?: number | null;
  vt_same_window_pct?: number | null;
  benchmark?: VtFlag | null;
  window?: [string, string] | null;
  basis?: string | null;
  max_dd_pct?: number | null;
  cagr_10y_pct?: number | null;
  cagr_10y_vt_pct?: number | null;
  cagr_10y_window?: [string, string] | null;
  cagr_10y_benchmark?: VtFlag | null;
  cagr_10y_status?: string | null;
  cagr_10y_incomplete?: string | null;
  cagr_10y_max_dd_pct?: number | null;
  as_of?: string | null;
}
/** A ticker as the header carries it (evals/instruments.yaml `tickers[]` or the .ecz `instruments[iso3][]`), plus the optional derived levels. */
export interface RawInstrument extends RawStats {
  ticker: string;
  name?: string | null;
  issuer: string;
  inception: string;
  status: InstrumentStatus;
  delisted?: string | null;
  liquidation_date?: string | null;
  status_url?: string | null;
  source_url?: string | null;
  msci_class?: string | null;
  stats?: RawStats | null;
  annual?: (AnnualLevels & { basis?: string }) | null;
}

export interface EconInstrument {
  ticker: string;
  name: string | null;
  issuer: string;
  inception: string; // YYYY-MM-DD
  inceptionYear: number;
  status: InstrumentStatus;
  delisted: string | null; // last trading day
  liquidationDate: string | null;
  statusUrl: string | null; // issuer notice / filing for a liquidation
  sourceUrl: string | null; // issuer product page / factsheet / filing
  msciClass: string | null;
  asOf: string | null;
  windows: InstrumentWindow[];
  annual: AnnualLevels | null;
}

export interface MarketEvent {
  iso3?: string;
  date: string;
  kind: string; // repatriation | index_deletion | trading_halt | …
  detail?: string;
  note?: string;
  url?: string | null;
  verified?: boolean;
}

export interface CountryInstruments {
  status?: InstrumentStatus | 'none';
  msci_class?: string | null;
  mobility?: Mobility | null;
  tickers?: RawInstrument[];
  events?: MarketEvent[];
}

export interface EconHeader {
  version: number;
  built?: string;
  as_of?: string;
  year_min?: number;
  year_max?: number;
  years?: [number, number];
  ids?: string[];
  iso3?: string[];
  arrays?: Record<string, ArraySpec>;
  last_econ_year?: number;
  income_labels?: Record<string, string>;
  stage_labels?: Record<string, string>;
  stage_hints?: Record<string, string>;
  instruments?: Record<string, CountryInstruments | RawInstrument[]>;
  benchmark?: { vt: AnnualLevels; vt_first_bar?: string; proxy_until_year?: number; proxy_note?: string };
  mobility?: Record<string, Mobility>;
  events?: Record<string, MarketEvent[]>;
  sources?: Record<string, string>;
}

export interface EconData {
  header: EconHeader;
  yearMin: number;
  yearMax: number;
  nYears: number;
  ids: string[];
  /** Decoded per-array values, country-major (`idx × nYears + (year − yearMin)`); NaN = n/a. */
  gdppc: Float32Array;
  growth: Float32Array; // annual real GDP growth, log points (%/yr) — NaN throughout when the file ships only the 10-y series
  /** Trailing 10-year real GDP/cap growth as shipped (`g_rgdp` beside `g_rgdp_1y`); null when it has to be computed. */
  growth10Shipped: Float32Array | null;
  tfr: Float32Array;
  income: Uint8Array; // 0 = n/a
  stage: Uint8Array; // 0 = n/a
  index: Map<string, number>;
}

export const INCOME_LABEL: Record<IncomeCode, string> = { 1: 'low income', 2: 'lower-middle income', 3: 'upper-middle income', 4: 'high income' };
export const INCOME_SHORT: Record<IncomeCode, string> = { 1: 'L', 2: 'LM', 3: 'UM', 4: 'H' };
/** OGHIST's first fiscal year is FY1989 (data year 1987); the plan's label is "n/a before 1987". */
export const INCOME_FIRST_YEAR = 1987;
export const DEFAULT_STAGE_LABEL: Record<string, string> = { '1': 'pre-dividend', '2': 'early-dividend', '3': 'late-dividend', '4': 'post-dividend' };
export const DEFAULT_STAGE_HINT: Record<string, string> = {
  '1': 'working-age share rising over the next 15 years and fertility at or above 4 births per woman (Ahmed–Cruz / GMR 2015 typology)',
  '2': 'working-age share rising over the next 15 years and fertility below 4 births per woman',
  '3': 'working-age share no longer rising; fertility a generation ago was at or above 2.1',
  '4': 'working-age share no longer rising; fertility a generation ago was already below 2.1',
};
/** The plan's fixed layout, used when the header carries no `arrays` block. */
export const DEFAULT_ARRAYS = (nValues: number): Record<string, ArraySpec> => ({
  gdppc: { dtype: 'u16', offset: 0, encoding: 'log', scale: 4096, na: 0 },
  g_rgdp: { dtype: 'i16', offset: nValues * 2, scale: 0.01, na: -32768 },
  tfr: { dtype: 'u16', offset: nValues * 4, scale: 0.001, na: 0 },
  income: { dtype: 'u8', offset: nValues * 6, na: 0 },
  stage: { dtype: 'u8', offset: nValues * 7, na: 0 },
});
export const VT_FIRST_BAR = '2008-06-24';
export const VT_FIRST_YEAR = 2008;

// ------------------------------------------------------------------------------------------------ decode

function readArray(body: DataView, spec: ArraySpec, n: number, into: Float32Array | Uint8Array): void {
  const width = spec.dtype === 'u8' ? 1 : 2;
  if (spec.offset < 0 || spec.offset + n * width > body.byteLength) throw new Error(`econ: array at ${spec.offset} (${n} × ${width} B) exceeds the body`);
  const na = spec.na ?? (spec.dtype === 'i16' ? -32768 : 0);
  for (let i = 0; i < n; i++) {
    const raw = spec.dtype === 'u8' ? body.getUint8(spec.offset + i) : spec.dtype === 'i16' ? body.getInt16(spec.offset + 2 * i, true) : body.getUint16(spec.offset + 2 * i, true);
    if (into instanceof Uint8Array) {
      into[i] = raw === na ? 0 : raw;
      continue;
    }
    if (raw === na) {
      into[i] = NaN;
      continue;
    }
    const scale = spec.scale ?? 1;
    into[i] = spec.encoding === 'log' ? Math.exp(raw / scale) : raw * scale;
  }
}

/** Parse an inflated `.ecz` buffer. Throws on a malformed header or a body that does not fit the declared layout. */
export function parseEcon(buf: ArrayBuffer): EconData {
  if (buf.byteLength < 4) throw new Error('econ: truncated header');
  const headerLen = new DataView(buf).getUint32(0, true);
  if (4 + headerLen > buf.byteLength) throw new Error('econ: header length exceeds file');
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, headerLen))) as EconHeader;
  const ids = header.ids ?? header.iso3;
  const yearMin = header.year_min ?? header.years?.[0];
  const yearMax = header.year_max ?? header.years?.[1];
  if (!Array.isArray(ids) || !Number.isInteger(yearMin) || !Number.isInteger(yearMax)) throw new Error('econ: header lacks ids / year_min / year_max');
  const nYears = yearMax! - yearMin! + 1;
  if (nYears <= 0) throw new Error('econ: year_max < year_min');
  const n = ids.length * nYears;
  const body = new DataView(buf, 4 + headerLen);
  const arrays = header.arrays ?? DEFAULT_ARRAYS(n);
  const need = (...names: string[]): ArraySpec => {
    for (const nm of names) if (arrays[nm]) return arrays[nm]!;
    throw new Error(`econ: header declares no array '${names[0]}'`);
  };
  const gdppc = new Float32Array(n);
  const growth = new Float32Array(n);
  const tfr = new Float32Array(n);
  const income = new Uint8Array(n);
  const stage = new Uint8Array(n);
  let growth10Shipped: Float32Array | null = null;
  readArray(body, need('gdppc'), n, gdppc);
  if (arrays['g_rgdp_1y']) {
    // the export ships both: `g_rgdp` is the trailing 10-year series, `g_rgdp_1y` the annual one
    growth10Shipped = new Float32Array(n);
    readArray(body, need('g_rgdp'), n, growth10Shipped);
    readArray(body, arrays['g_rgdp_1y'], n, growth);
  } else {
    readArray(body, need('g_rgdp', 'growth'), n, growth);
  }
  readArray(body, need('tfr'), n, tfr);
  readArray(body, need('income', 'income_class'), n, income);
  readArray(body, need('stage'), n, stage);
  const index = new Map<string, number>();
  ids.forEach((id, i) => index.set(id, i));
  return { header, yearMin: yearMin!, yearMax: yearMax!, nYears, ids, gdppc, growth, growth10Shipped, tfr, income, stage, index };
}

/** Sniff + inflate (gzip magic → `DecompressionStream`; anything else is taken as already inflated) then parse. */
export async function decodeEcon(raw: ArrayBuffer): Promise<EconData> {
  const head = new Uint8Array(raw, 0, Math.min(2, raw.byteLength));
  const inflated = isGzip(head) ? await gunzip(raw) : new Uint8Array(raw);
  const buf = inflated.byteOffset === 0 && inflated.byteLength === inflated.buffer.byteLength ? (inflated.buffer as ArrayBuffer) : inflated.slice().buffer;
  return parseEcon(buf as ArrayBuffer);
}

// ------------------------------------------------------------------------------------------------ accessors

function cell(e: EconData, iso3: string, year: number): number {
  const i = e.index.get(iso3);
  if (i === undefined || year < e.yearMin || year > e.yearMax) return -1;
  return i * e.nYears + (year - e.yearMin);
}

const num = (v: number): number | null => (Number.isFinite(v) ? v : null);

/** Whether the file carries any GDP/cap value for this id. */
export function hasEcon(e: EconData, iso3: string): boolean {
  const i = e.index.get(iso3);
  if (i === undefined) return false;
  for (let k = i * e.nYears; k < (i + 1) * e.nYears; k++) if (Number.isFinite(e.gdppc[k])) return true;
  return false;
}

/** GDP per capita (Maddison 2011$, spliced past 2022 with WDI / PWT growth), or null. */
export function gdppc(e: EconData, iso3: string, year: number): number | null {
  const c = cell(e, iso3, year);
  return c < 0 ? null : num(e.gdppc[c]);
}

/** Annual real GDP growth in `year` (100·ln ratio, %/yr), or null. */
export function growthAnnual(e: EconData, iso3: string, year: number): number | null {
  const c = cell(e, iso3, year);
  return c < 0 ? null : num(e.growth[c]);
}

/**
 * Trailing 10-year real GDP/cap growth ending in `year`, %/yr: the shipped series when the file carries one, else the
 * mean of the annual log growth rates over (year − 9 … year) — null unless at least `minYears` of the ten are present.
 */
export function growth10(e: EconData, iso3: string, year: number, minYears = 8): number | null {
  if (e.growth10Shipped) {
    const c = cell(e, iso3, year);
    return c < 0 ? null : num(e.growth10Shipped[c]);
  }
  let s = 0;
  let n = 0;
  for (let y = year - 9; y <= year; y++) {
    const g = growthAnnual(e, iso3, y);
    if (g === null) continue;
    s += g;
    n++;
  }
  return n >= minYears ? s / n : null;
}

/** Total fertility rate in `year`, or null. */
export function tfr(e: EconData, iso3: string, year: number): number | null {
  const c = cell(e, iso3, year);
  return c < 0 ? null : num(e.tfr[c]);
}

export interface IncomeThen {
  code: IncomeCode;
  label: string;
  short: string;
}
/** World Bank income group as classified for `year` (OGHIST); null when unclassified — see `incomeNote`. */
export function income(e: EconData, iso3: string, year: number): IncomeThen | null {
  const c = cell(e, iso3, year);
  if (c < 0) return null;
  const code = e.income[c];
  if (code < 1 || code > 4) return null;
  const k = code as IncomeCode;
  return { code: k, label: e.header.income_labels?.[String(k)] ?? INCOME_LABEL[k], short: INCOME_SHORT[k] };
}
/** Why an income group is missing: before the OGHIST series, or simply unclassified. */
export function incomeNote(year: number): string {
  return year < INCOME_FIRST_YEAR ? `n/a before ${INCOME_FIRST_YEAR}` : 'not classified';
}

export interface StageThen {
  code: number;
  label: string;
  hint: string;
}
/** Demographic-dividend stage (Ahmed–Cruz / GMR 2015 typology applied to `year`), or null. */
export function stage(e: EconData, iso3: string, year: number): StageThen | null {
  const c = cell(e, iso3, year);
  if (c < 0) return null;
  const code = e.stage[c];
  if (code < 1) return null;
  const k = String(code);
  return { code, label: e.header.stage_labels?.[k] ?? DEFAULT_STAGE_LABEL[k] ?? `stage ${code}`, hint: e.header.stage_hints?.[k] ?? DEFAULT_STAGE_HINT[k] ?? '' };
}

/** The last year any GDP/cap value exists in the file (the header may state it; else scanned). */
export function lastEconYear(e: EconData): number {
  if (Number.isInteger(e.header.last_econ_year)) return e.header.last_econ_year!;
  for (let y = e.yearMax; y >= e.yearMin; y--) {
    for (let i = 0; i < e.ids.length; i++) if (Number.isFinite(e.gdppc[i * e.nYears + (y - e.yearMin)])) return y;
  }
  return e.yearMin;
}

/** Last year with a GDP/cap value for this id (or null). */
export function lastGdpYear(e: EconData, iso3: string): number | null {
  const i = e.index.get(iso3);
  if (i === undefined) return null;
  for (let y = e.yearMax; y >= e.yearMin; y--) if (Number.isFinite(e.gdppc[i * e.nYears + (y - e.yearMin)])) return y;
  return null;
}

// ------------------------------------------------------------------------------------------------ then what

export interface Horizon {
  h: number; // requested horizon (10 / 20 / 30)
  years: number; // actual span (< h when clipped to the last data year)
  toYear: number;
  multiple: number; // y_{to} / y_from
  pctPerYear: number; // CAGR in %/yr
  clipped: boolean;
}
export interface ThenWhat {
  iso3: string;
  year: number;
  gdppcThen: number | null;
  horizons: Horizon[]; // one per requested horizon that could be computed (≥ minYears of data)
  unavailable: number[]; // requested horizons with no window yet
  lastYear: number | null;
}

/** CAGR in %/yr between two levels over `years`. */
export function cagr(from: number, to: number, years: number): number {
  return (Math.pow(to / from, 1 / years) - 1) * 100;
}

/**
 * GDP/cap at `year` → +h for each horizon: exact when the data reach `year + h`, clipped to the last data year when
 * at least `minYears` exist (flagged), otherwise listed under `unavailable`.
 */
export function thenWhat(e: EconData, iso3: string, year: number, horizons: readonly number[] = [10, 20, 30], minYears = 5): ThenWhat {
  const y0 = gdppc(e, iso3, year);
  const last = lastGdpYear(e, iso3);
  const out: ThenWhat = { iso3, year, gdppcThen: y0, horizons: [], unavailable: [], lastYear: last };
  if (y0 === null || last === null) {
    out.unavailable = [...horizons];
    return out;
  }
  for (const h of horizons) {
    let to = year + h;
    let clipped = false;
    if (to > last) {
      to = last;
      clipped = true;
    }
    const y1 = to > year ? gdppc(e, iso3, to) : null;
    if (y1 === null || to - year < minYears) {
      out.unavailable.push(h);
      continue;
    }
    const years = to - year;
    out.horizons.push({ h, years, toYear: to, multiple: y1 / y0, pctPerYear: cagr(y0, y1, years), clipped });
  }
  return out;
}

// ------------------------------------------------------------------------------------------------ instruments

const yearOf = (d: string | null | undefined): number => (d ? Number(String(d).slice(0, 4)) : NaN);
const dateStr = (d: unknown): string | null => (typeof d === 'string' && /^\d{4}-\d{2}-\d{2}/.test(d) ? d.slice(0, 10) : null);
const numOrNull = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** The country block of the header in either accepted shape. */
function countryBlock(e: EconData, iso3: string): CountryInstruments | null {
  const b = e.header.instruments?.[iso3];
  if (!b) return null;
  return Array.isArray(b) ? { tickers: b } : b;
}

function precomputedWindows(inst: RawInstrument): InstrumentWindow[] {
  const raw: RawStats = { ...inst, ...(inst.stats ?? {}) };
  const out: InstrumentWindow[] = [];
  if (raw.window && raw.since_inception_cagr_pct != null) {
    const [from, to] = raw.window;
    const y1 = yearOf(from);
    const y2 = yearOf(to);
    const years = Math.max(1, (new Date(to).getTime() - new Date(from).getTime()) / (365.25 * 86400e3));
    out.push({ label: 'since_inception', from, to, y1, y2, years: Math.round(years * 100) / 100, r: raw.since_inception_cagr_pct, rVt: numOrNull(raw.vt_same_window_pct), vt: raw.benchmark ?? (numOrNull(raw.vt_same_window_pct) === null ? 'none' : 'vt'), maxDd: numOrNull(raw.max_dd_pct), basis: raw.basis ?? null });
  }
  if (raw.cagr_10y_window && raw.cagr_10y_pct != null) {
    const [from, to] = raw.cagr_10y_window;
    out.push({ label: '10y', from, to, y1: yearOf(from), y2: yearOf(to), years: yearOf(to) - yearOf(from), r: raw.cagr_10y_pct, rVt: numOrNull(raw.cagr_10y_vt_pct), vt: raw.cagr_10y_benchmark ?? 'vt', maxDd: numOrNull(raw.cagr_10y_max_dd_pct), status: raw.cagr_10y_status ?? null, incomplete: raw.cagr_10y_incomplete ?? null });
  }
  return out;
}

export function normaliseInstrument(raw: RawInstrument): EconInstrument {
  return {
    ticker: raw.ticker,
    name: raw.name ?? null,
    issuer: raw.issuer,
    inception: raw.inception,
    inceptionYear: yearOf(raw.inception),
    status: raw.status,
    delisted: dateStr(raw.delisted),
    liquidationDate: dateStr(raw.liquidation_date),
    statusUrl: raw.status_url ?? null,
    sourceUrl: raw.source_url ?? null,
    msciClass: raw.msci_class && raw.msci_class !== 'n/a' ? raw.msci_class : null,
    asOf: raw.stats?.as_of ?? raw.as_of ?? null,
    windows: precomputedWindows(raw),
    annual: raw.annual ? { from_year: raw.annual.from_year, levels: raw.annual.levels } : null,
  };
}

/** US-listed single-country instruments curated for this id (may be empty), earliest inception first. */
export function instruments(e: EconData, iso3: string): EconInstrument[] {
  const b = countryBlock(e, iso3);
  return (b?.tickers ?? []).map(normaliseInstrument).sort((a, c) => a.inception.localeCompare(c.inception));
}
export function mobility(e: EconData, iso3: string): Mobility | null {
  return countryBlock(e, iso3)?.mobility ?? e.header.mobility?.[iso3] ?? null;
}
/** MSCI market class of the country (the funds' class, else the header's snapshot for fund-less countries). */
export function msciClass(e: EconData, iso3: string): string | null {
  const b = countryBlock(e, iso3);
  const c = b?.msci_class ?? b?.tickers?.find((t) => t.msci_class)?.msci_class ?? null;
  return c && c !== 'n/a' ? c : null;
}
export function events(e: EconData, iso3: string): MarketEvent[] {
  return countryBlock(e, iso3)?.events ?? e.header.events?.[iso3] ?? [];
}

/** Level at the end of `year`, or null when the series does not cover it. */
export function levelAt(s: AnnualLevels | null | undefined, year: number): number | null {
  if (!s) return null;
  const i = year - s.from_year;
  if (i < 0 || i >= s.levels.length) return null;
  const v = s.levels[i];
  return Number.isFinite(v) && v > 0 ? v : null;
}
export function lastLevelYear(s: AnnualLevels | null | undefined): number | null {
  if (!s || s.levels.length === 0) return null;
  return s.from_year + s.levels.length - 1;
}

/** VT's flag for a window: proxy when the window starts before VT's first bar, none when VT has no level at either end. */
export function vtFlag(e: EconData, y1: number, y2: number): VtFlag {
  const b = e.header.benchmark;
  if (!b || levelAt(b.vt, y1) === null || levelAt(b.vt, y2) === null) return 'none';
  const proxyUntil = b.proxy_until_year ?? Number((b.vt_first_bar ?? VT_FIRST_BAR).slice(0, 4));
  return y1 < proxyUntil ? 'vt_proxy' : 'vt';
}

/** Derived year-end window y1→y2 from `annual` levels beside VT over the identical window (null without levels). */
export function derivedWindow(e: EconData, inst: EconInstrument, y1: number, y2: number): InstrumentWindow | null {
  if (y2 <= y1) return null;
  const a = levelAt(inst.annual, y1);
  const b = levelAt(inst.annual, y2);
  if (a === null || b === null) return null;
  const flag = vtFlag(e, y1, y2);
  const va = levelAt(e.header.benchmark?.vt, y1);
  const vb = levelAt(e.header.benchmark?.vt, y2);
  return { label: 'derived', from: `${y1}-12-31`, to: `${y2}-12-31`, y1, y2, years: y2 - y1, r: cagr(a, b, y2 - y1), rVt: flag === 'none' || va === null || vb === null ? null : cagr(va, vb, y2 - y1), vt: flag, maxDd: null };
}

/**
 * The window to show for an instrument that existed at `y`: a derived y→y+horizon window when year-end levels are
 * shipped, else the precomputed window that starts in `y` (the backtest's 2015→2025 row), else the since-inception
 * window (its own years are printed, never presented as y→y+N).
 */
export function windowFrom(e: EconData, inst: EconInstrument, y: number, horizon = 10): InstrumentWindow | null {
  if (inst.annual) {
    const last = lastLevelYear(inst.annual)!;
    const d = derivedWindow(e, inst, y, Math.min(y + horizon, last));
    if (d) return d;
  }
  return inst.windows.find((w) => w.y1 === y) ?? inst.windows.find((w) => w.label === 'since_inception') ?? inst.windows[0] ?? null;
}

/** Whether the instrument had a price at the end of `y` (year-end levels when shipped, else inception year ≤ y). */
export function existedAt(inst: EconInstrument, y: number): boolean {
  if (inst.annual) return levelAt(inst.annual, y) !== null;
  if (inst.inceptionYear > y) return false;
  const last = inst.delisted ? yearOf(inst.delisted) : Infinity;
  return y < last;
}

export type MarketCase = 'existed' | 'later' | 'liquidated' | 'none';
export interface MarketRow {
  kind: MarketCase;
  instrument: EconInstrument | null;
  /** The window shown (existed: from y when derivable; later: since inception; liquidated: to the liquidation). */
  window: InstrumentWindow | null;
  /** For `later`: the year no fund existed (= y). For `liquidated`: the last trading day. */
  note: string | null;
  msciClass: string | null;
  mobility: Mobility | null;
}

/**
 * The market row of a "then what happened" disclosure for (iso3, y), PLAN §7 rules:
 *  existed at y         → "{TICKER} total return y1–y2 · VT same window" (y→y+N when derivable, else the precomputed window)
 *  exists now, not then → "No US-listed fund existed in y" + the fund since inception
 *  liquidated           → "{TICKER} liquidated {date}" + return to liquidation
 *  none                 → badge + MSCI class
 * With several funds the earliest inception that existed at y wins (PREREG §3.4); else the earliest live one.
 */
export function marketRow(e: EconData, iso3: string, y: number, horizon = 10): MarketRow {
  const list = instruments(e, iso3);
  const cls = msciClass(e, iso3);
  const mob = mobility(e, iso3);
  if (list.length === 0) return { kind: 'none', instrument: null, window: null, note: null, msciClass: cls, mobility: mob };
  const existed = list.filter((i) => existedAt(i, y)); // `instruments` sorts by inception: the earliest that existed wins
  const pickExisted = existed[0];
  if (pickExisted) {
    const w = windowFrom(e, pickExisted, y, horizon);
    if (pickExisted.status !== 'live') return { kind: 'liquidated', instrument: pickExisted, window: w, note: pickExisted.delisted, msciClass: cls, mobility: mob };
    return { kind: 'existed', instrument: pickExisted, window: w, note: null, msciClass: cls, mobility: mob };
  }
  const live = list.find((i) => i.status === 'live');
  if (live) return { kind: 'later', instrument: live, window: sinceInception(e, live), note: String(y), msciClass: cls, mobility: mob };
  const dead = list[0]!;
  return { kind: 'liquidated', instrument: dead, window: sinceInception(e, dead), note: dead.delisted, msciClass: cls, mobility: mob };
}

/** The since-inception window: precomputed when shipped, else derived from the first to the last year-end level. */
export function sinceInception(e: EconData, inst: EconInstrument): InstrumentWindow | null {
  const pre = inst.windows.find((w) => w.label === 'since_inception');
  if (pre) return pre;
  if (inst.annual && inst.annual.levels.length >= 2) return derivedWindow(e, inst, inst.annual.from_year, lastLevelYear(inst.annual)!);
  return inst.windows[0] ?? null;
}

// ------------------------------------------------------------------------------------------------ cross-sections

export type EconField = 'log_gdppc' | 'growth10' | 'income' | 'stage' | 'tfr';
export interface CrossSection {
  year: number;
  n: number;
  mean: number;
  sd: number;
}

export function econFieldValue(e: EconData, iso3: string, year: number, f: EconField): number | null {
  switch (f) {
    case 'log_gdppc': {
      const v = gdppc(e, iso3, year);
      return v === null || v <= 0 ? null : Math.log(v);
    }
    case 'growth10':
      return growth10(e, iso3, year);
    case 'income':
      return income(e, iso3, year)?.code ?? null;
    case 'stage':
      return stage(e, iso3, year)?.code ?? null;
    case 'tfr':
      return tfr(e, iso3, year);
  }
}

/** Mean / sd of a field over every id with a value in `year` (the reference cross-section for z-scores). */
export function crossSection(e: EconData, year: number, f: EconField): CrossSection {
  let n = 0;
  let s = 0;
  let s2 = 0;
  for (const id of e.ids) {
    const v = econFieldValue(e, id, year, f);
    if (v === null) continue;
    n++;
    s += v;
    s2 += v * v;
  }
  const mean = n ? s / n : NaN;
  const sd = n > 1 ? Math.sqrt(Math.max(0, s2 / n - mean * mean)) : NaN;
  return { year, n, mean, sd };
}

/** z-score of a value against a cross-section (null when sd is 0 / n < 2). */
export function zScore(v: number | null, cs: CrossSection): number | null {
  if (v === null || !Number.isFinite(cs.sd) || cs.sd === 0) return null;
  return (v - cs.mean) / cs.sd;
}
