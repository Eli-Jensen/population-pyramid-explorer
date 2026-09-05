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
