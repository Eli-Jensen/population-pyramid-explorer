// econ.ts decoder + accessors on a synthetic .ecz built here (the same layout the Python export writes).
import { describe, expect, it } from 'vitest';
import {
  crossSection,
  decodeEcon,
  gdppc,
  growth10,
  growthAnnual,
  hasEcon,
  income,
  incomeNote,
  instruments,
  lastEconYear,
  marketRow,
  parseEcon,
  stage,
  tfr,
  thenWhat,
  vtFlag,
  derivedWindow,
  windowFrom,
  zScore,
  type EconHeader,
  type RawInstrument,
} from './econ.ts';

const IDS = ['AAA', 'BBB', 'CCC'];
const Y0 = 1990;
const Y1 = 2024;
const NY = Y1 - Y0 + 1;

/** Levels that compound at `rate` per year from 1.0 at `from`. */
const series = (from: number, to: number, rate: number) => ({ from_year: from, levels: Array.from({ length: to - from + 1 }, (_, i) => Math.pow(1 + rate, i)) });

/** AAA carries year-end levels (any window derivable); BBB carries only the precomputed instruments.yaml statistics. */
const INSTRUMENTS: Record<string, { status: string; msci_class: string; mobility: 'open' | 'closed'; tickers: RawInstrument[] }> = {
  AAA: { status: 'live', msci_class: 'EM', mobility: 'open', tickers: [{ ticker: 'AAA1', issuer: 'Test Co', inception: '2000-05-09', status: 'live', delisted: null, msci_class: 'EM', annual: series(2000, 2024, 0.07) }] },
  BBB: {
    status: 'liquidated',
    msci_class: 'standalone',
    mobility: 'closed',
    tickers: [
      {
        ticker: 'BBB1',
        issuer: 'Test Co',
        inception: '2013-04-02',
        status: 'liquidated',
        delisted: '2024-03-25',
        liquidation_date: '2024-03-29',
        status_url: 'https://example.org/notice',
        msci_class: 'standalone',
        since_inception_cagr_pct: -14.14,
        vt_same_window_pct: 8.06,
        benchmark: 'vt',
        window: ['2013-12-31', '2023-12-29'],
        cagr_10y_pct: -7.08,
        cagr_10y_vt_pct: 11.76,
        cagr_10y_window: ['2015-12-31', '2025-12-31'],
        cagr_10y_benchmark: 'vt',
        cagr_10y_status: 'manual_incomplete',
        cagr_10y_incomplete: '2024-01-31..2024-03-29 (final stub not transcribed)',
        max_dd_pct: -56.03,
      },
    ],
  },
};

function build(opts: { gzip?: boolean; arrays?: boolean } = {}): { buf: ArrayBuffer; header: EconHeader; values: Record<string, number[]> } {
  const n = IDS.length * NY;
  const g = new Uint16Array(n);
  const gr = new Int16Array(n).fill(-32768);
  const tf = new Uint16Array(n);
  const inc = new Uint8Array(n);
  const st = new Uint8Array(n);
  const values: Record<string, number[]> = { gdppc: [], growth: [], tfr: [] };
  IDS.forEach((id, i) => {
    for (let y = Y0; y <= Y1; y++) {
      const k = i * NY + (y - Y0);
      if (id === 'CCC') continue; // no GDP series at all
      const gdp = 1000 * (i + 1) * Math.pow(1.03 + 0.02 * i, y - Y0); // AAA 3 %/yr, BBB 5 %/yr
      g[k] = Math.round(Math.log(gdp) * 4096);
      gr[k] = y - Y0 >= 5 ? Math.round((3 + 2 * i) * 100) : -32768; // annual growth, n/a for the first 5 years
      tf[k] = Math.round((4.5 - 0.05 * (y - Y0)) * 1000);
      inc[k] = y < 1987 ? 0 : ((i + 1) as 1 | 2);
      st[k] = y < 2000 ? 1 : 2;
      values.gdppc.push(gdp);
    }
  });
  const header: EconHeader = {
    version: 1,
    year_min: Y0,
    year_max: Y1,
    ids: IDS,
    last_econ_year: Y1,
    instruments: INSTRUMENTS as unknown as EconHeader['instruments'],
    benchmark: { vt: series(1996, 2024, 0.06), vt_first_bar: '2008-06-24', proxy_until_year: 2008 },
  };
  if (opts.arrays !== false) {
    header.arrays = {
      gdppc: { dtype: 'u16', offset: 0, encoding: 'log', scale: 4096, na: 0 },
      g_rgdp: { dtype: 'i16', offset: n * 2, scale: 0.01, na: -32768 },
      tfr: { dtype: 'u16', offset: n * 4, scale: 0.001, na: 0 },
      income: { dtype: 'u8', offset: n * 6, na: 0 },
      stage: { dtype: 'u8', offset: n * 7, na: 0 },
    };
  }
  const hjson = new TextEncoder().encode(JSON.stringify(header));
  const body = new Uint8Array(n * 8);
  body.set(new Uint8Array(g.buffer), 0);
  body.set(new Uint8Array(gr.buffer), n * 2);
  body.set(new Uint8Array(tf.buffer), n * 4);
  body.set(inc, n * 6);
  body.set(st, n * 7);
  const out = new Uint8Array(4 + hjson.length + body.length);
  new DataView(out.buffer).setUint32(0, hjson.length, true);
  out.set(hjson, 4);
  out.set(body, 4 + hjson.length);
  return { buf: out.buffer, header, values };
}

async function gzipBytes(buf: ArrayBuffer): Promise<ArrayBuffer> {
  const stream = new Blob([buf]).stream().pipeThrough(new CompressionStream('gzip'));
  return new Response(stream).arrayBuffer();
}

describe('econ.ts', () => {
  it('parses the header + arrays and decodes the log / scaled encodings within quantisation error', () => {
    const { buf } = build();
    const e = parseEcon(buf);
    expect(e.ids).toEqual(IDS);
    expect(e.nYears).toBe(NY);
    const v = gdppc(e, 'AAA', 2000)!;
    expect(Math.abs(v / (1000 * Math.pow(1.03, 10)) - 1)).toBeLessThan(2e-4); // 1/4096 in log space
    expect(growthAnnual(e, 'BBB', 2010)).toBeCloseTo(5, 6);
    expect(growthAnnual(e, 'BBB', 1993)).toBeNull(); // sentinel → n/a
    expect(growth10(e, 'BBB', 2010)).toBeCloseTo(5, 6); // mean of ten annual rates
    expect(growth10(e, 'BBB', 2003)).toBeCloseTo(5, 6); // 9 of 10 present ≥ the 8 floor
    expect(growth10(e, 'BBB', 2000)).toBeNull(); // only 6 of 10 present
    expect(tfr(e, 'AAA', 1990)).toBeCloseTo(4.5, 6);
    expect(income(e, 'AAA', 2000)).toEqual({ code: 1, label: 'low income', short: 'L' });
    expect(income(e, 'BBB', 2000)?.short).toBe('LM');
    expect(stage(e, 'AAA', 1995)?.label).toBe('pre-dividend');
    expect(stage(e, 'AAA', 2005)?.label).toBe('early-dividend');
    expect(hasEcon(e, 'CCC')).toBe(false);
    expect(gdppc(e, 'CCC', 2000)).toBeNull();
    expect(gdppc(e, 'ZZZ', 2000)).toBeNull();
    expect(gdppc(e, 'AAA', 1949)).toBeNull();
    expect(lastEconYear(e)).toBe(Y1);
    expect(incomeNote(1980)).toBe('n/a before 1987');
  });

  it('falls back to the plan layout when the header has no arrays block', () => {
    const e = parseEcon(build({ arrays: false }).buf);
    expect(growth10(e, 'AAA', 2020)).toBeCloseTo(3, 6);
  });

  it('decodes a gzip body through the sniff + inflate path and rejects truncated files', async () => {
    const { buf } = build();
    const e = await decodeEcon(await gzipBytes(buf));
    expect(gdppc(e, 'BBB', 1990)).toBeCloseTo(2000, -1);
    const plain = await decodeEcon(buf);
    expect(gdppc(plain, 'BBB', 1990)).toBeCloseTo(2000, -1);
    expect(() => parseEcon(buf.slice(0, 3))).toThrow(/truncated/);
    expect(() => parseEcon(buf.slice(0, 200))).toThrow();
  });

  it('thenWhat: exact horizons, clipped horizon flagged, short windows unavailable', () => {
    const e = parseEcon(build().buf);
    const t = thenWhat(e, 'AAA', 1990);
    expect(t.gdppcThen).toBeCloseTo(1000, -1);
    expect(t.horizons.map((h) => h.h)).toEqual([10, 20, 30]);
    expect(t.horizons[0]!.multiple).toBeCloseTo(Math.pow(1.03, 10), 3);
    expect(t.horizons[0]!.pctPerYear).toBeCloseTo(3, 1);
    expect(t.horizons[0]!.clipped).toBe(false);
    // 1990 + 30 = 2020 ≤ 2024 → exact; from 2000, +30 → clipped to 2024 (24 years)
    const t2 = thenWhat(e, 'AAA', 2000);
    expect(t2.horizons.find((h) => h.h === 30)).toMatchObject({ clipped: true, years: 24, toYear: 2024 });
    // from 2021: 3 years of data < 5 → nothing computable
    const t3 = thenWhat(e, 'AAA', 2021);
    expect(t3.horizons).toEqual([]);
    expect(t3.unavailable).toEqual([10, 20, 30]);
    expect(thenWhat(e, 'CCC', 1990).gdppcThen).toBeNull();
  });

  it('derived windows beside VT, with the proxy flag before 2008 and "none" outside the VT series', () => {
    const e = parseEcon(build().buf);
    const inst = instruments(e, 'AAA')[0]!;
    const w = derivedWindow(e, inst, 2010, 2020)!;
    expect(w.r).toBeCloseTo(7, 6);
    expect(w.rVt).toBeCloseTo(6, 6);
    expect(w.vt).toBe('vt');
    expect(w.label).toBe('derived');
    expect(derivedWindow(e, inst, 2000, 2010)!.vt).toBe('vt_proxy');
    expect(vtFlag(e, 1990, 1995)).toBe('none');
    expect(derivedWindow(e, inst, 2010, 2010)).toBeNull();
    expect(derivedWindow(e, inst, 1990, 2000)).toBeNull(); // no level at 1990
    // precomputed windows (instruments.yaml shape) are normalised verbatim
    const b = instruments(e, 'BBB')[0]!;
    expect(b.windows.map((x) => x.label)).toEqual(['since_inception', '10y']);
    expect(b.windows[1]).toMatchObject({ y1: 2015, y2: 2025, r: -7.08, rVt: 11.76, vt: 'vt', status: 'manual_incomplete' });
    expect(b.windows[0]).toMatchObject({ y1: 2013, y2: 2023, r: -14.14, rVt: 8.06 });
    expect(windowFrom(e, b, 2015)!.label).toBe('10y'); // the window that starts in y wins
    expect(windowFrom(e, b, 2016)!.label).toBe('since_inception'); // else since inception, with its own years
    expect(b.liquidationDate).toBe('2024-03-29');
  });

  it('marketRow: existed / later / liquidated / none per the plan rules', () => {
    const e = parseEcon(build().buf);
    const a = marketRow(e, 'AAA', 2005);
    expect(a.kind).toBe('existed');
    expect(a.window).toMatchObject({ y1: 2005, y2: 2015, vt: 'vt_proxy' });
    const a2 = marketRow(e, 'AAA', 2020); // 10-y horizon clipped to the last level (2024)
    expect(a2.window).toMatchObject({ y1: 2020, y2: 2024 });
    const later = marketRow(e, 'AAA', 1995);
    expect(later.kind).toBe('later');
    expect(later.note).toBe('1995');
    expect(later.window).toMatchObject({ y1: 2000, y2: 2024 });
    const liq = marketRow(e, 'BBB', 2015);
    expect(liq.kind).toBe('liquidated');
    expect(liq.note).toBe('2024-03-25');
    expect(liq.window).toMatchObject({ y1: 2015, y2: 2025, label: '10y' });
    expect(liq.mobility).toBe('closed');
    expect(liq.msciClass).toBe('standalone');
    const liqLater = marketRow(e, 'BBB', 2010); // no fund in 2010, none live now → liquidated, since inception
    expect(liqLater.kind).toBe('liquidated');
    expect(liqLater.window).toMatchObject({ label: 'since_inception', y1: 2013, y2: 2023 });
    const none = marketRow(e, 'CCC', 2000);
    expect(none.kind).toBe('none');
    expect(none.instrument).toBeNull();
  });

  it('cross-section z-scores use every id with a value in that year and print n', () => {
    const e = parseEcon(build().buf);
    const cs = crossSection(e, 2010, 'growth10');
    expect(cs.n).toBe(2); // CCC has no series
    expect(cs.mean).toBeCloseTo(4, 6);
    expect(zScore(3, cs)).toBeCloseTo(-1, 6);
    const early = crossSection(e, 1995, 'growth10');
    expect(early.n).toBe(0);
    expect(zScore(3, early)).toBeNull();
  });
});
