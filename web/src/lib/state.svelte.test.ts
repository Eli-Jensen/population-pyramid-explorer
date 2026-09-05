import { describe, expect, it } from 'vitest';
import { entities, idxOf, nEntities, N_DIMS, N_YEARS, U16_TOTAL, YEAR_MIN } from './entities.ts';
import { parseEntityShard, parseYearShard } from './data.ts';
import { AppState, pyramidFromEntityShard, pyramidFromYearShard, toAxisMode, type DataSource, type Features } from './state.svelte.ts';
import { fakeBrowser } from './url.test.ts';

const ROW_BYTES = N_DIMS * 2 + 4;

/** Synthetic shard: row r has bin (r % 42) carrying the whole 65535 so rows are distinguishable. */
function syntheticBuffer(nRows: number, totalFor: (r: number) => number): ArrayBuffer {
  const buf = new ArrayBuffer(nRows * ROW_BYTES);
  const u16 = new Uint16Array(buf, 0, nRows * N_DIMS);
  const totals = new Float32Array(buf, nRows * N_DIMS * 2, nRows);
  for (let r = 0; r < nRows; r++) {
    u16[r * N_DIMS + (r % N_DIMS)] = U16_TOTAL;
    totals[r] = totalFor(r);
  }
  return buf;
}

function fakeData(log: string[] = []): DataSource & { log: string[] } {
  return {
    log,
    entityShard: async (id) => {
      log.push(`E:${id}`);
      return parseEntityShard(syntheticBuffer(N_YEARS, (r) => 1000 + r), id);
    },
    yearShard: async (year) => {
      log.push(`Y:${year}`);
      return parseYearShard(syntheticBuffer(nEntities, (r) => 5000 + r), year);
    },
  };
}

const flush = () => new Promise((r) => setTimeout(r, 0));
const clock2026 = () => new Date(2026, 5, 1);

function make(start: string, base = '/') {
  const b = fakeBrowser(start);
  const data = fakeData();
  const s = new AppState({ clock: clock2026, data, env: { base, history: b.history, location: b.location, target: b.target } });
  return { s, b, data };
}

describe('pyramid views', () => {
  it('entity-shard view carries id/year/u16/source; year-shard view resolves the corpus row', () => {
    const e = parseEntityShard(syntheticBuffer(N_YEARS, (r) => r), 'JPN');
    const pe = pyramidFromEntityShard(e, 1953);
    expect(pe).toMatchObject({ id: 'JPN', year: 1953, total: 3, source: 'entity' });
    expect(pe.shares[3]).toBe(1);
    expect(pe.u16[3]).toBe(U16_TOTAL);
    expect(pe.shares.reduce((a, x) => a + x, 0)).toBe(1);
    const y = parseYearShard(syntheticBuffer(nEntities, (r) => r), 2026);
    const py = pyramidFromYearShard(y, 'JPN')!;
    expect(py).toMatchObject({ id: 'JPN', year: 2026, total: idxOf('JPN'), source: 'year' });
    expect(py.shares[idxOf('JPN') % N_DIMS]).toBe(1);
    expect(pyramidFromYearShard(y, 'nope')).toBeNull();
    expect(entities[idxOf('JPN')]!.id).toBe('JPN');
  });
  it('toAxisMode maps the URL vocabulary onto math/scale.ts', () => {
    expect(toAxisMode('fit')).toBe('fit');
    expect(toAxisMode('pin10')).toBe('pin10');
    expect(toAxisMode('noclip')).toBe('never');
  });
});

describe('AppState routing', () => {
  it('init canonicalises the URL with replaceState and loads both shards', async () => {
    const { s, b, data } = make('/USA/');
    s.init();
    expect(b.log).toEqual([{ op: 'replace', url: '/united-states/2026' }]);
    expect(s.query).toMatchObject({ id: 'USA', year: 2026 });
    expect(s.entity?.slug).toBe('united-states');
    expect(s.loading).toBe(true);
    await flush();
    expect(data.log.sort()).toEqual(['E:USA', 'Y:2026']);
    expect(s.loading).toBe(false);
    expect(s.pyramid?.source).toBe('entity');
    expect(s.pyramid?.total).toBe(1000 + (2026 - YEAR_MIN));
    expect(s.pyramid?.shares[(2026 - YEAR_MIN) % N_DIMS]).toBe(1);
    s.dispose();
  });

  it('home route: no query, no fetch', async () => {
    const { s, data } = make('/');
    s.init();
    expect(s.route.kind).toBe('home');
    expect(s.query).toBeNull();
    expect(s.pyramid).toBeNull();
    await flush();
    expect(data.log).toEqual([]);
  });

  it('unknown slug → notfound route', () => {
    const { s } = make('/narnia/2026');
    s.init();
    expect(s.route).toMatchObject({ kind: 'notfound', path: '/narnia/2026' });
  });

  it('respects the GitHub Pages base', async () => {
    const { s, b } = make('/population-pyramid-explorer/JPN', '/population-pyramid-explorer/');
    s.init();
    expect(b.href()).toBe('/population-pyramid-explorer/japan/2026');
    s.setYear(1990);
    expect(b.href()).toBe('/population-pyramid-explorer/japan/1990');
  });
});

describe('AppState.setYear', () => {
  it('drag = replaceState only (no fetch); release = one pushState; Back returns to the pre-drag year', async () => {
    const { s, b, data } = make('/japan/2026');
    s.init();
    await flush();
    data.log.length = 0;
    b.log.length = 0;

    s.setYear(2027, { commit: false });
    s.setYear(2028, { commit: false });
    s.setYear(2029, { commit: false });
    expect(b.log.map((l) => l.op)).toEqual(['replace', 'replace', 'replace']);
    expect(s.year).toBe(2029);
    expect(s.pyramid?.year).toBe(2029); // from the entity shard, no fetch
    await flush();
    expect(data.log).toEqual([]);

    s.setYear(2030, { commit: true });
    expect(b.log.slice(3)).toEqual([
      { op: 'replace', url: '/japan/2026' }, // rewind to the pre-drag URL…
      { op: 'push', url: '/japan/2030' }, // …then exactly one push
    ]);
    expect(b.stack).toEqual(['/japan/2026', '/japan/2030']);
    await flush();
    expect(data.log).toEqual(['Y:2030']); // entity shard cached; the year shard loads on commit

    b.back();
    expect(s.year).toBe(2026);
    expect(b.href()).toBe('/japan/2026');
  });

  it('keyboard step (commit without drag) is a single pushState; same year is a no-op', () => {
    const { s, b } = make('/japan/2026');
    s.init();
    b.log.length = 0;
    s.setYear(2027);
    s.setYear(2027);
    expect(b.log).toEqual([{ op: 'push', url: '/japan/2027' }]);
  });

  it('clamps to 1950–2100 and keeps options', () => {
    const { s, b } = make('/japan/2026?unit=abs');
    s.init();
    s.setYear(2500);
    expect(s.year).toBe(2100);
    expect(b.href()).toBe('/japan/2100?unit=abs');
    s.setYear(1);
    expect(b.href()).toBe('/japan/1950?unit=abs');
  });

  it('a stale entity-shard response never overwrites the current entity', async () => {
    const { s, b } = make('/japan/2026');
    s.init();
    s.setEntity('ITA');
    await flush();
    expect(b.href()).toBe('/italy/2026');
    expect(s.entityShard?.id).toBe('ITA');
    expect(s.pyramid?.id).toBe('ITA');
  });
});

describe('AppState.setEntity / setOptions / derived', () => {
  it('setEntity pushes, keeps year + options; setOptions replaces and elides defaults', () => {
    const { s, b } = make('/japan/1980?axis=pin10');
    s.init();
    b.log.length = 0;
    s.setEntity('usa'); // alias → ignored (not an id)
    expect(b.log).toEqual([]);
    s.setEntity('USA');
    expect(b.log).toEqual([{ op: 'push', url: '/united-states/1980?axis=pin10' }]);
    s.setOptions({ unit: 'abs' });
    s.setOptions({ axis: 'fit' });
    expect(b.log.slice(1)).toEqual([
      { op: 'replace', url: '/united-states/1980?axis=pin10&unit=abs' },
      { op: 'replace', url: '/united-states/1980?unit=abs' },
    ]);
    expect(s.options).toEqual({ axis: 'fit', unit: 'abs' });
  });

  it('axis follows the option, the entity and the drawn year', async () => {
    const { s } = make('/qatar/2026');
    s.init();
    expect(s.entity?.axis_pct).toBe(17);
    expect(s.axisPct).toBe(17); // fit, nothing drawn yet
    expect(s.axis.clips).toBe(false);
    await flush(); // synthetic rows put 100 % in one bin → every mode clips except none
    expect(s.axis).toEqual({ axisPct: 17, clips: true });
    s.setOptions({ axis: 'pin10' });
    expect(s.axisMode).toBe('pin10');
    expect(s.axis).toEqual({ axisPct: 10, clips: true });
    s.setOptions({ axis: 'noclip' });
    expect(s.axisMode).toBe('never');
    expect(s.axisPct).toBe(17);
  });

  it('era / isProjected use the injected clock', () => {
    const { s } = make('/japan/2050');
    s.init();
    expect(s.currentYear).toBe(2026);
    expect(s.era).toBe('projected');
    expect(s.isProjected).toBe(true);
    s.setYear(2024);
    expect(s.era).toBe('nowcast');
    s.setYear(2000);
    expect(s.era).toBe('observed');
  });

  it('features come from the injected function (W1) and track the pyramid', async () => {
    const fake = (shares: Float32Array): Features => ({
      median_age: shares.indexOf(1) * 5,
      mean_age: 0, u15: 0, wa: 0, o65: 0, o80: 0, child_dep: 0, old_dep: 0, total_dep: 0,
      base_slope_20: 0, base_slope_10: 0, modal_bin: 0, wa_sex_ratio: 1,
      stage: 'stationary', flag_male_skew: false, flag_urn: false,
    });
    const b = fakeBrowser('/japan/1992');
    const s = new AppState({ clock: clock2026, data: fakeData(), features: fake, env: { base: '/', history: b.history, location: b.location } });
    s.init();
    await flush();
    expect(s.features?.median_age).toBe(((1992 - YEAR_MIN) % N_DIMS) * 5);
    s.setYear(1993);
    expect(s.features?.median_age).toBe(((1993 - YEAR_MIN) % N_DIMS) * 5);
  });

  it('falls back to the year shard when the entity shard failed', async () => {
    const b = fakeBrowser('/japan/2026');
    const data: DataSource = {
      entityShard: async () => { throw new Error('404 entity'); },
      yearShard: async (year) => parseYearShard(syntheticBuffer(nEntities, (r) => 7000 + r), year),
    };
    const s = new AppState({ clock: clock2026, data, env: { base: '/', history: b.history, location: b.location } });
    s.init();
    await flush();
    expect(s.error).toBeNull();
    expect(s.pyramid?.source).toBe('year');
    expect(s.pyramid?.total).toBe(7000 + idxOf('JPN'));
    expect(s.pyramid?.shares[idxOf('JPN') % N_DIMS]).toBe(1);
    expect(entities[idxOf('JPN')]!.id).toBe('JPN');
  });

  it('surfaces an error when nothing can paint', async () => {
    const b = fakeBrowser('/japan/2026');
    const data: DataSource = {
      entityShard: async () => { throw new Error('404 entity'); },
      yearShard: async () => { throw new Error('404 year'); },
    };
    const s = new AppState({ clock: clock2026, data, env: { base: '/', history: b.history, location: b.location } });
    s.init();
    await flush();
    expect(s.pyramid).toBeNull();
    expect(s.error).toMatch(/404/);
    expect(s.loading).toBe(false);
  });
});

// ---------------------------------------------------------------------------------------------------- M2 search

import type { CorpusView, Engine, Explanation, SearchQuery, SearchResult } from './engine.ts';
import type { Bands, Corpus, Embedding } from './types.ts';
import { defaultBandsSuffice } from './state.svelte.ts';

/**
 * Fake engine: records calls and returns deterministic, well-formed results so the store's DATA FLOW can be
 * asserted (which shards / tiers are fetched for which mode, debounce, readiness) without X1's math.
 */
function fakeEngine(calls: string[]): Engine {
  const ents = entities;
  const nE = ents.length;
  const idxOfId = (id: string) => idxOf(id);
  const shardView = (years: number[], u16: Uint16Array, totals: Float32Array): CorpusView => ({
    u16,
    totals,
    nRows: nE,
    nYears: N_YEARS,
    entityIdx: idxOfId,
    rowOf: (id, year) => {
      const j = years.indexOf(year);
      const e = idxOfId(id);
      return j < 0 || e < 0 ? -1 : j * nE + e;
    },
  });
  const result = (view: CorpusView, q: SearchQuery, i: number, rank: number): SearchResult => {
    const e = ents[(idxOfId(q.id) + 1 + i) % nE]!;
    const year = view.nRows === nE ? q.year : q.year; // fake: candidate year = query year
    return { id: e.id, year, row: view.rowOf(e.id, year), d: 0.1 * (i + 1), rankRaw: rank, dy: 0, band: 'typical', percentile: null };
  };
  const explanation: Explanation = {
    decomposition: { metric: 'blend', sex: '2', d: 0.3, l2Part: 0.2, w1Part: 0.1, w1Years: 1.9, topBinsL2: [[0, 0.2]], topBinsW1: [[1, 0.1]] },
    deltas: { referenceYear: 2026, nReference: 198, all: [], alike: [], differs: [] },
    because: 'alike', differsIn: 'differs', w1Sentence: 'w1', decompositionSentence: 'dec',
  };
  return {
    fromCorpus: (corpus: Corpus) => {
      calls.push('fromCorpus');
      return {
        u16: corpus.u16, totals: corpus.totals, nRows: corpus.nRows, nYears: N_YEARS, entityIdx: idxOfId,
        rowOf: (id, year) => { const e = idxOfId(id); return e < 0 ? -1 : e * N_YEARS + (year - YEAR_MIN); },
      };
    },
    fromShards: (main, others, inject) => {
      calls.push(`fromShards:${[main.year, ...others.map((o) => o.year)].join(',')}${inject ? `+${inject.shard.id}` : ''}`);
      const shards = [main, ...others];
      const u16 = new Uint16Array(shards.length * nE * N_DIMS);
      const totals = new Float32Array(shards.length * nE);
      shards.forEach((s, j) => { u16.set(s.u16, j * nE * N_DIMS); totals.set(s.totals, j * nE); });
      return shardView(shards.map((s) => s.year), u16, totals);
    },
    lagYears: (tau, trend, L) => (trend === null ? [] : (trend === 'motion' ? [L] : Array.from({ length: L / 5 }, (_, i) => 5 * (i + 1))).map((s) => tau - s)),
    candidateMask: (view) => new Uint8Array(view.nRows).fill(1),
    distances: (view) => { calls.push('distances'); return Float64Array.from({ length: view.nRows }, (_, i) => i + 1); },
    similar: (view, q) => { calls.push(`similar:${q.mode}:${q.year}:${q.metric}`); return Array.from({ length: q.k }, (_, i) => result(view, q, i, i + 1)); },
    search: (view, q) => { calls.push(`search:${q.mode}:${q.year}:${q.metric}`); const twins = Array.from({ length: q.k }, (_, i) => result(view, q, i, i + 1)); const opp = Array.from({ length: q.k }, (_, i) => result(view, q, i + 10, i + 1)); return { similar: twins, different: opp, strict: opp, d: Float64Array.from({ length: view.nRows }, (_, i) => i + 1), nCandidates: view.nRows }; },
    different: (view, q) => { calls.push('different'); const rs = Array.from({ length: q.k }, (_, i) => result(view, q, i + 10, i + 1)); return { results: rs, strict: rs }; },
    bestYearPerEntity: (_view, q) => { calls.push(`bestYear:${q.mode}`); return [{ id: 'ITA', bestYear: q.year, row: 0, d: 0.3, dy: 0, boundaryHit: false, band: 'close', percentile: 20 }]; },
    isolation: (_view, year, metric) => { calls.push(`isolation:${year}:${metric}`); return new Map(ents.filter((e) => e.type === 'country').map((e, i) => [e.id, i])); },
    isolationPercentile: () => 91,
    tableMetric: (q) => q.metric,
    bandFor: () => ({ label: 'typical', percentile: null, table: null }),
    featureStats: (_v, year) => { calls.push(`stats:${year}`); return { year, rows: new Int32Array(0), mu: new Float64Array(13), sd: new Float64Array(13).fill(1) }; },
    explain: () => explanation,
  };
}

function fakeCorpus(): Corpus {
  const nRows = nEntities * N_YEARS;
  const u16 = new Uint16Array(nRows * N_DIMS);
  for (let r = 0; r < nRows; r++) u16[r * N_DIMS + (r % N_DIMS)] = U16_TOTAL;
  return { nRows, nEntities, nYears: N_YEARS, u16, totals: new Float32Array(nRows).fill(1000), source: { path: 'gzip-stream', decodeMs: 1, fetchMs: 1 } };
}
const fakeBands = (): Bands => ({ index: {}, values: new Float32Array(0) });
const fakeEmbedding = (model: string): Embedding => ({ model, nRows: nEntities * N_YEARS, dim: 64, values: new Float32Array(nEntities * N_YEARS * 64) });

function makeM2(start: string, opts: { debounceMs?: number } = {}) {
  const b = fakeBrowser(start);
  const log: string[] = [];
  const data = fakeData(log);
  const full: DataSource = {
    ...data,
    bandsDefault: async () => { log.push('B:default'); return fakeBands(); },
    bands: async () => { log.push('B:all'); return fakeBands(); },
    corpus: async () => { log.push('C'); return fakeCorpus(); },
    embedding: async (m) => { log.push(`EMB:${m}`); return fakeEmbedding(m); },
  };
  const calls: string[] = [];
  const s = new AppState({ clock: clock2026, data: full, engine: fakeEngine(calls), debounceMs: opts.debounceMs ?? 30, env: { base: '/', history: b.history, location: b.location, target: b.target } });
  return { s, b, log, calls };
}
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe('AppState M2 — constraints on the URL', () => {
  it('search options come from the query with defaults filled; setOptions replaces and elides', () => {
    const { s, b } = makeM2('/japan/2026');
    s.init();
    expect(s.search).toMatchObject({ mode: 'same', k: 5, div: 0.5, metric: 'blend', era: null, minpop: 100_000 });
    b.log.length = 0;
    s.setOptions({ k: 10, metric: 'w1' });
    expect(b.href()).toBe('/japan/2026?metric=w1&k=10');
    s.setOptions({ mode: 'today' }); // Y == currentYear: resolves to the concrete range all the same
    expect(b.href()).toBe('/japan/2026?mode=range&from=2026&to=2026&via=today&metric=w1&k=10');
    s.resetSearch();
    expect(b.href()).toBe('/japan/2026');
    expect(b.log.every((l) => l.op === 'replace')).toBe(true);
  });

  it('today sugar in the URL is replaceState-d to the concrete range with via=today', () => {
    const { s, b } = makeM2('/japan/1990?mode=today');
    s.init();
    expect(b.log).toEqual([{ op: 'replace', url: '/japan/1990?mode=range&from=2026&to=2026&via=today' }]);
    expect(s.search).toMatchObject({ mode: 'range', from: 2026, to: 2026, via: 'today' });
    expect(s.singleYear).toBe(2026);
  });

  it('J8: the era default follows the year while scrubbing and an explicit value is normalised', () => {
    const { s, b } = makeM2('/japan/2026?mode=any');
    s.init();
    expect(s.searchEra).toBe('obs');
    s.setYear(2050);
    expect(s.searchEra).toBe('all');
    expect(b.href()).toBe('/japan/2050?mode=any');
    s.setOptions({ era: 'obs' });
    expect(b.href()).toBe('/japan/2050?mode=any&era=obs');
    expect(s.searchEra).toBe('obs');
    s.setYear(2026); // era=obs is the default again → elided
    expect(b.href()).toBe('/japan/2026?mode=any');
  });

  it('a trend whose window leaves the corpus is dropped when scrubbing back', () => {
    const { s, b } = makeM2('/japan/2026?trend=motion&L=20');
    s.init();
    s.setYear(1960);
    expect(b.href()).toBe('/japan/1960');
    expect(s.search.trend).toBeNull();
  });
});

describe('AppState M2 — data tiers per mode', () => {
  it('same-year: year shard + bands_default only, results from a shard view, no corpus', async () => {
    const { s, log, calls } = makeM2('/japan/2026');
    s.init();
    await flush();
    expect(log.sort()).toEqual(['B:default', 'E:JPN', 'Y:2026']);
    expect(s.needsCorpus).toBe(false);
    expect(s.requiredYears).toEqual([2026]);
    expect(s.results?.source).toBe('shards');
    expect(s.results?.twins).toHaveLength(5);
    expect(s.results?.twins[0]?.explanation?.because).toBe('alike');
    expect(s.results?.own).toBeNull(); // needs the corpus
    expect(calls.filter((c) => c.startsWith('fromShards'))).toContain('fromShards:2026');
    expect(calls).toContain('search:same:2026:blend');
    expect(calls).toContain('stats:2026');
    expect(s.isolationPercentile).toBe(91);
    expect(s.searchError).toBeNull();
  });

  it('today from 1990: the 2026 shard is the candidate set and the 1990 shard backs the query row / reference year', async () => {
    const { s, log, calls } = makeM2('/japan/1990?mode=today');
    s.init();
    await flush();
    expect(s.requiredYears).toEqual([1990, 2026]);
    expect(log.filter((l) => l.startsWith('Y:')).sort()).toEqual(['Y:1990', 'Y:2026']);
    expect(log).not.toContain('C');
    expect(s.results?.q).toMatchObject({ mode: 'range', from: 2026, to: 2026, year: 1990 });
    expect(calls).toContain('fromShards:2026,1990'); // (the derived is lazy: built on the read above)
    expect(log).toContain('B:all'); // a non-default mode needs the full bands file
  });

  it('trend (motion, 10 y) adds the τ−10 shard; path adds every 5-year lag', async () => {
    const a = makeM2('/china/1990?mode=today&trend=motion');
    a.s.init();
    await flush();
    expect(a.s.requiredYears).toEqual([1980, 1990, 2016, 2026]);
    expect(a.log.filter((l) => l.startsWith('Y:')).sort()).toEqual(['Y:1980', 'Y:1990', 'Y:2016', 'Y:2026']);
    expect(a.s.results?.twins[0]?.trend).toMatch(/U15 .* vs .* pts · 65\+/);
    expect(a.s.results?.twins[0]?.explanation).toBeNull();
    const b = makeM2('/japan/2026?trend=path&L=20');
    b.s.init();
    await flush();
    expect(b.s.requiredYears).toEqual([2006, 2011, 2016, 2021, 2026]);
  });

  it('any-year: loads the corpus (once) and the full bands; results from the corpus view with the own-trajectory row', async () => {
    const { s, log, calls } = makeM2('/japan/2026?mode=any');
    s.init();
    expect(s.needsCorpus).toBe(true);
    expect(s.corpusStatus).toBe('loading');
    expect(s.results).toBeNull();
    await flush();
    expect(log.filter((l) => l === 'C')).toHaveLength(1);
    expect(log).toContain('B:all');
    expect(s.corpusStatus).toBe('ready');
    expect(s.results?.source).toBe('corpus');
    expect(s.results?.own).toMatchObject({ year: expect.any(Number) });
    expect(Math.abs(s.results!.own!.dy)).toBeGreaterThanOrEqual(5);
    expect(calls.some((c) => c.startsWith('search:any:'))).toBe(true);
    s.setOptions({ mode: 'near', n: 5 });
    await flush();
    expect(log.filter((l) => l === 'C')).toHaveLength(1); // still once
  });

  it('the time-shift panel fetches the corpus on open and computes the table', async () => {
    const { s, log, calls } = makeM2('/japan/2026');
    s.init();
    await flush();
    expect(log).not.toContain('C');
    expect(s.timeShift).toBeNull();
    s.setTimeShiftOpen(true);
    expect(s.needsCorpus).toBe(true);
    await flush();
    expect(log).toContain('C');
    expect(log).toContain('B:all');
    expect(s.timeShift).toHaveLength(1);
    expect(calls).toContain('bestYear:any');
    expect(s.results?.source).toBe('corpus'); // once loaded, the corpus serves the same-year search too
    s.setTimeShiftOpen(false);
    expect(s.timeShift).toBeNull();
  });

  it('the Visual metric loads the exposed embedding lazily and waits for it', async () => {
    const { s, log } = makeM2('/japan/2026?metric=visual');
    s.init();
    if (!s.visualModel) return; // build without an exposed image space: the URL falls back to blend
    expect(s.needsEmbedding).toBe(true);
    expect(s.results).toBeNull();
    await flush();
    expect(log).toContain(`EMB:${s.visualModel}`);
    expect(s.embeddingStatus).toBe('ready');
    expect(s.results?.q.metric).toBe('visual');
  });

  it('defaultBandsSuffice only for same / blend / two-sex / no trend', () => {
    expect(defaultBandsSuffice({ mode: 'same', metric: 'blend', sex: '2', trend: null })).toBe(true);
    expect(defaultBandsSuffice({ mode: 'same', metric: 'l2', sex: '2', trend: null })).toBe(false);
    expect(defaultBandsSuffice({ mode: 'same', metric: 'blend', sex: '1', trend: null })).toBe(false);
    expect(defaultBandsSuffice({ mode: 'any', metric: 'blend', sex: '2', trend: null })).toBe(false);
    expect(defaultBandsSuffice({ mode: 'same', metric: 'blend', sex: '2', trend: 'motion' })).toBe(false);
  });
});

describe('AppState M2 — debounce while scrubbing', () => {
  it('the search year trails a drag by debounceMs and then fetches that year shard; commit syncs at once', async () => {
    const { s, log, calls } = makeM2('/japan/2026', { debounceMs: 20 });
    s.init();
    await flush();
    log.length = 0;
    calls.length = 0;
    s.setYear(2000, { commit: false });
    s.setYear(2001, { commit: false });
    expect(s.year).toBe(2001);
    expect(s.searchYear).toBe(2026); // not yet
    expect(s.results?.q.year).toBe(2026);
    await flush();
    expect(log).toEqual([]); // nothing fetched inside the debounce window
    await wait(40);
    expect(s.searchYear).toBe(2001);
    expect(log).toEqual(['Y:2001']); // one shard for the settled year only
    expect(s.results?.q.year).toBe(2001);
    // the derived is lazy: reading results above scanned 2026 once; the settled year scanned exactly once, no 2000
    expect(calls.filter((c) => c.startsWith('search'))).toEqual(['search:same:2026:blend', 'search:same:2001:blend']);
    s.setYear(2010, { commit: true });
    expect(s.searchYear).toBe(2010);
  });
});

// ---------------------------------------------------------------------------------------------------- M3 compare

describe('AppState M3 — compare route', () => {
  it('same-year pair: both entity shards + the year shard + default bands; no corpus; pair computed', async () => {
    const { s, log, calls } = makeM2('/compare/japan/2026/italy/2026');
    s.init();
    expect(s.compare).toMatchObject({ a: 'JPN', ya: 2026, b: 'ITA', yb: 2026, view: 'overlay', from: null });
    expect(s.query).toBeNull(); // not a country page
    expect(s.pairYears).toEqual({ ya: 2026, yb: 2026 });
    expect(s.compareNeedsCorpus).toBe(false);
    expect(s.compareNeedsAllBands).toBe(false);
    await flush();
    expect(log.sort()).toEqual(['B:default', 'E:ITA', 'E:JPN', 'Y:2026']);
    expect(s.pyramidA?.id).toBe('JPN');
    expect(s.pyramidB?.id).toBe('ITA');
    expect(s.pairAxis?.axisPct).toBeGreaterThanOrEqual(10);
    expect(s.pair).not.toBeNull();
    expect(s.pair?.explanation.because).toBe('alike');
    expect(s.pair?.dy).toBe(0);
    expect(s.pair?.bandKind).toBe('same');
    expect(calls).toContain('fromShards:2026');
    expect(calls.some((c) => c.startsWith('stats:2026'))).toBe(true);
    expect(s.corpusStatus).toBe('idle');
    s.dispose();
  });

  it('cross-year pair: both year shards (yb candidates + ya reference) and the full bands file', async () => {
    const { s, log, calls } = makeM2('/compare/south-korea/2026/japan/2008');
    s.init();
    expect(s.compareNeedsAllBands).toBe(true);
    await flush();
    expect(log.sort()).toEqual(['B:all', 'B:default', 'E:JPN', 'E:KOR', 'Y:2008', 'Y:2026']);
    expect(s.pair?.dy).toBe(-18); // reading the lazy derived builds the view
    expect(calls).toContain('fromShards:2008,2026');
    expect(s.pair?.bandKind).toBe('cross');
    expect(s.pyramidB?.year).toBe(2008);
    s.dispose();
  });

  it('best: fetches the corpus, resolves y* and replaceStates the concrete year + ?from=best; the button is lit', async () => {
    const { s, b, log } = makeM2('/compare/japan/2026/italy/best');
    s.init();
    expect(s.compare?.yb).toBe('best');
    expect(s.pairYears).toBeNull();
    expect(s.pyramidB).toBeNull();
    expect(s.compareNeedsCorpus).toBe(true);
    await flush();
    await flush();
    expect(log).toContain('C');
    // fake distances = row index + 1 → Italy's earliest allowed year wins (1950, on the era edge)
    expect(b.href()).toBe('/compare/japan/2026/italy/1950?from=best');
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/compare/japan/2026/italy/1950?from=best' });
    expect(s.compare).toMatchObject({ yb: 1950, from: 'best' });
    expect(s.bestB).toMatchObject({ year: 1950, dy: -76, boundaryHit: true });
    expect(s.bestLit).toBe(true);
    expect(s.pairYears).toEqual({ ya: 2026, yb: 1950 });
    await flush();
    expect(s.pair?.bandKind).toBe('best');
    // moving B off the best year drops from=best (one pushState) and unlights the button
    b.log.length = 0;
    s.setCompareYear('b', 1960);
    expect(b.log).toEqual([{ op: 'push', url: '/compare/japan/2026/italy/1960' }]);
    expect(s.bestLit).toBe(false);
    expect(s.compareNeedsCorpus).toBe(false);
    // "B → best year" again: push best, resolve synchronously (corpus in hand) → replace to the concrete year
    b.log.length = 0;
    s.compareBest();
    await flush();
    expect(b.log.map((l) => l.op)).toEqual(['push', 'replace']);
    expect(b.href()).toBe('/compare/japan/2026/italy/1950?from=best');
    expect(s.bestLit).toBe(true);
    s.dispose();
  });

  it('a pasted from=best whose year is not the best drops the flag once the corpus is in', async () => {
    const { s, b } = makeM2('/compare/japan/2026/italy/2000?from=best');
    s.init();
    expect(s.compare?.from).toBe('best');
    expect(s.bestLit).toBe(true); // provisional until the corpus says otherwise
    await flush();
    await flush();
    expect(b.href()).toBe('/compare/japan/2026/italy/2000');
    expect(s.compare?.from).toBeNull();
    expect(s.bestLit).toBe(false);
    s.dispose();
  });

  it('scrubbing: replaceState while dragging, one pushState on release; lock-offset moves both years', async () => {
    const { s, b } = makeM2('/compare/south-korea/2026/japan/2008');
    s.init();
    await flush();
    b.log.length = 0;
    s.setCompareYear('a', 2027, { commit: false });
    s.setCompareYear('a', 2028, { commit: false });
    expect(b.log.map((l) => l.op)).toEqual(['replace', 'replace']);
    expect(s.compare).toMatchObject({ ya: 2028, yb: 2008 });
    expect(s.pairYears).toEqual({ ya: 2026, yb: 2008 }); // trails the slider
    s.setCompareYear('a', 2030, { commit: true });
    expect(b.log.slice(2)).toEqual([{ op: 'replace', url: '/compare/south-korea/2026/japan/2008' }, { op: 'push', url: '/compare/south-korea/2030/japan/2008' }]);
    expect(s.pairYears).toEqual({ ya: 2030, yb: 2008 });
    b.back();
    expect(s.compare).toMatchObject({ ya: 2026, yb: 2008 });
    // lock: Δ = −18 kept, clamped as a pair
    s.setLockOffset(true);
    s.setCompareYear('b', 2020);
    expect(s.compare).toMatchObject({ ya: 2038, yb: 2020 });
    s.setCompareYear('a', 1950);
    expect(s.compare).toMatchObject({ ya: 1968, yb: 1950 });
    expect(b.href()).toBe('/compare/south-korea/1968/japan/1950');
    s.dispose();
  });

  it('swap, view / option tweaks (replace), metric change drops from=best, entity replace', async () => {
    const { s, b } = makeM2('/compare/south-korea/2026/japan/2008?from=best');
    s.init();
    b.log.length = 0;
    s.setCompareOptions({ view: 'diff' });
    expect(b.log).toEqual([{ op: 'replace', url: '/compare/south-korea/2026/japan/2008?view=diff&from=best' }]);
    s.setCompareOptions({ unit: 'abs', axis: 'noclip' });
    expect(b.href()).toBe('/compare/south-korea/2026/japan/2008?axis=noclip&unit=abs&view=diff&from=best');
    s.setCompareOptions({ metric: 'l2' });
    expect(b.href()).toBe('/compare/south-korea/2026/japan/2008?axis=noclip&unit=abs&view=diff&metric=l2');
    expect(s.compare?.from).toBeNull();
    b.log.length = 0;
    s.swapCompare();
    expect(b.log).toEqual([{ op: 'push', url: '/compare/japan/2008/south-korea/2026?axis=noclip&unit=abs&view=diff&metric=l2' }]);
    expect(s.pairYears).toEqual({ ya: 2008, yb: 2026 });
    s.setCompareEntity('b', 'ITA');
    expect(b.href()).toBe('/compare/japan/2008/italy/2026?axis=noclip&unit=abs&view=diff&metric=l2');
    // era tweak survives canonicalisation only when it differs from the J8 default of A's year
    s.setCompareOptions({ era: 'all' });
    expect(b.href()).toContain('era=all');
    s.setCompareOptions({ era: 'obs' });
    expect(b.href()).not.toContain('era=');
    s.dispose();
  });

  it('respects the GitHub Pages base and canonicalises aliases with replaceState', async () => {
    const b = fakeBrowser('/population-pyramid-explorer/compare/KOR/2026/jpn/best');
    const log: string[] = [];
    const data = fakeData(log);
    const s = new AppState({
      clock: clock2026,
      data: { ...data, bandsDefault: async () => fakeBands(), bands: async () => fakeBands(), corpus: async () => fakeCorpus() },
      engine: fakeEngine([]),
      env: { base: '/population-pyramid-explorer/', history: b.history, location: b.location, target: b.target },
    });
    s.init();
    expect(b.log[0]).toEqual({ op: 'replace', url: '/population-pyramid-explorer/compare/south-korea/2026/japan/best' });
    await flush();
    await flush();
    expect(b.href()).toBe('/population-pyramid-explorer/compare/south-korea/2026/japan/1950?from=best');
    s.dispose();
  });
});
