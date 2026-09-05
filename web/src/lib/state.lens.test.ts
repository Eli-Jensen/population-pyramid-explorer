// M5 store behaviour: the sticky market lens (URL + carry-over + localStorage memory + first-activation banner) and the
// tier-2b econ load that starts only after the first paint has settled.
import { describe, expect, it } from 'vitest';
import { nEntities, N_DIMS, N_YEARS, U16_TOTAL } from './entities.ts';
import { parseEntityShard, parseYearShard } from './data.ts';
import type { EconData } from './econ.ts';
import { parse } from './router.ts';
import { AppState, LENS_BANNER_KEY, LENS_KEY, type DataSource, type StorageLike } from './state.svelte.ts';
import { fakeBrowser } from './url.test.ts';

const ROW_BYTES = N_DIMS * 2 + 4;
function syntheticBuffer(nRows: number): ArrayBuffer {
  const buf = new ArrayBuffer(nRows * ROW_BYTES);
  const u16 = new Uint16Array(buf, 0, nRows * N_DIMS);
  for (let r = 0; r < nRows; r++) u16[r * N_DIMS + (r % N_DIMS)] = U16_TOTAL;
  return buf;
}
function econStub(): EconData {
  const ids = ['JPN'];
  const n = 75;
  return { header: { version: 1, year_min: 1950, year_max: 2024, ids, last_econ_year: 2024 }, yearMin: 1950, yearMax: 2024, nYears: n, ids, gdppc: new Float32Array(n).fill(1000), growth: new Float32Array(n).fill(NaN), growth10Shipped: null, tfr: new Float32Array(n).fill(NaN), income: new Uint8Array(n), stage: new Uint8Array(n), index: new Map([['JPN', 0]]) };
}
function fakeData(econ: () => Promise<EconData | null>, log: string[] = []): DataSource & { log: string[] } {
  return {
    log,
    entityShard: async (id) => parseEntityShard(syntheticBuffer(N_YEARS), id),
    yearShard: async (year) => parseYearShard(syntheticBuffer(nEntities), year),
    econ: () => {
      log.push('econ');
      return econ();
    },
  };
}
function fakeStorage(init: Record<string, string> = {}): StorageLike & { map: Map<string, string> } {
  const map = new Map(Object.entries(init));
  return { map, getItem: (k) => map.get(k) ?? null, setItem: (k, v) => void map.set(k, v) };
}
const flush = async (n = 3) => {
  for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 0));
};
const clock2026 = () => new Date(2026, 5, 1);

function make(start: string, opts: { storage?: StorageLike | null; econ?: () => Promise<EconData | null> } = {}) {
  const b = fakeBrowser(start);
  const data = fakeData(opts.econ ?? (async () => null));
  const storage = opts.storage === undefined ? fakeStorage() : opts.storage;
  const s = new AppState({ clock: clock2026, data, storage, env: { base: '/', history: b.history, location: b.location, target: b.target }, engine: null });
  return { s, b, data, storage };
}

describe('market lens (M5)', () => {
  it('is off by default; the toggle writes the URL (replaceState), the memory and shows the banner once', () => {
    const { s, b, storage } = make('/japan/2026');
    s.init();
    expect(s.lens).toBeNull();
    expect(s.lensOn).toBe(false);
    s.setLens(true);
    expect(s.lensOn).toBe(true);
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/japan/2026?lens=econ' });
    expect(storage!.getItem(LENS_KEY)).toBe('econ');
    expect(s.lensBanner).toBe(true);
    s.dismissLensBanner();
    expect(s.lensBanner).toBe(false);
    expect(storage!.getItem(LENS_BANNER_KEY)).toBe('1');
    s.setLens(false);
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/japan/2026' });
    expect(storage!.getItem(LENS_KEY)).toBe('off');
    s.setLens(true);
    expect(s.lensBanner).toBe(false); // dismissed once, stays dismissed
  });

  it('a remembered lens is applied to the first route and replaceState makes the URL say so', () => {
    const { s, b } = make('/japan/2026', { storage: fakeStorage({ [LENS_KEY]: 'econ' }) });
    s.init();
    expect(s.lens).toBe('econ');
    expect(b.log).toEqual([{ op: 'replace', url: '/japan/2026?lens=econ' }]);
    // a remembered 'off' (or nothing) leaves the URL alone
    const off = make('/japan/2026', { storage: fakeStorage({ [LENS_KEY]: 'off' }) });
    off.s.init();
    expect(off.s.lens).toBeNull();
    expect(off.b.log).toEqual([]);
  });

  it('carries the lens onto in-app routes that lack it, but never onto a history entry; a pasted lens does not write the memory', () => {
    const { s, b, storage } = make('/japan/2026?lens=econ');
    s.init();
    expect(s.lensOn).toBe(true);
    expect(storage!.getItem(LENS_KEY)).toBeNull(); // pasted URL, not the toggle
    expect(s.lensBanner).toBe(true); // a pasted lens is a first activation too — the banner shows until dismissed once
    s.dismissLensBanner();
    const again = make('/japan/2026?lens=econ', { storage: fakeStorage({ [LENS_BANNER_KEY]: '1' }) });
    again.s.init();
    expect(again.s.lensBanner).toBe(false);
    // an in-app link without the param (result card → country page)
    s.applyRoute(parse('/italy/2008', '', '/', { clock: clock2026 }));
    expect(s.query).toMatchObject({ id: 'ITA', year: 2008, lens: 'econ' });
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/italy/2008?lens=econ' });
    // compare route too
    s.applyRoute(parse('/compare/japan/2026/italy/2008', '', '/', { clock: clock2026 }));
    expect(s.compare?.lens).toBe('econ');
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/compare/japan/2026/italy/2008?lens=econ' });
    // Back to an entry whose URL has no lens: the URL is authoritative
    s.applyRoute(parse('/japan/1990', '', '/', { clock: clock2026 }), { fromHistory: true });
    expect(s.lens).toBeNull();
    // and with the lens off, in-app routes stay off
    s.applyRoute(parse('/italy/2008', '', '/', { clock: clock2026 }));
    expect(s.lens).toBeNull();
  });

  it('setYear / setEntity / setOptions keep the lens in the URL', () => {
    const { s, b } = make('/japan/2026?lens=econ');
    s.init();
    s.setYear(1990);
    expect(b.log.at(-1)).toEqual({ op: 'push', url: '/japan/1990?lens=econ' });
    s.setEntity('ITA');
    expect(b.log.at(-1)).toEqual({ op: 'push', url: '/italy/1990?lens=econ' });
    s.setOptions({ unit: 'abs' });
    expect(b.log.at(-1)).toEqual({ op: 'replace', url: '/italy/1990?unit=abs&lens=econ' });
  });

  it('works without storage (private mode) and without an econ loader', () => {
    const b = fakeBrowser('/japan/2026');
    const s = new AppState({ clock: clock2026, data: { entityShard: async (id) => parseEntityShard(syntheticBuffer(N_YEARS), id), yearShard: async (y) => parseYearShard(syntheticBuffer(nEntities), y) }, storage: null, env: { base: '/', history: b.history, location: b.location, target: b.target }, engine: null });
    s.init();
    s.setLens(true);
    expect(s.lensOn).toBe(true);
    expect(s.rememberedLens()).toBeNull();
    expect(s.econStatus).toBe('idle'); // no loader → nothing to load
  });
});

describe('tier 2b econ load', () => {
  it('starts after the first paint settled, once, and reports absent / ready / error', async () => {
    const absent = make('/japan/2026');
    absent.s.init();
    expect(absent.s.econStatus).toBe('idle'); // not in the first-paint set
    await flush();
    expect(absent.data.log.filter((x) => x === 'econ').length).toBe(1);
    expect(absent.s.econStatus).toBe('absent');
    absent.s.setYear(1990);
    await flush();
    expect(absent.data.log.filter((x) => x === 'econ').length).toBe(1); // never re-fetched

    const ready = make('/japan/2026', { econ: async () => econStub() });
    ready.s.init();
    await flush();
    expect(ready.s.econStatus).toBe('ready');
    expect(ready.s.econ?.ids).toEqual(['JPN']);
    expect(ready.s.econLib?.gdppc(ready.s.econ!, 'JPN', 2000)).toBe(1000);
    expect(ready.s.lastEconYear).toBe(2024);

    const failing = make('/japan/2026', { econ: async () => Promise.reject(new Error('HTTP 404')) });
    failing.s.init();
    await flush();
    expect(failing.s.econStatus).toBe('error');
    expect(failing.s.econError).toMatch(/404/);
    // the toggle triggers a retry
    failing.s.setLens(true);
    await flush();
    expect(failing.data.log.filter((x) => x === 'econ').length).toBe(2);
  });
});
