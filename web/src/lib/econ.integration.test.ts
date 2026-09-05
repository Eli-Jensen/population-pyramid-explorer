// The REAL econ file (web/public/data/wpp2024/econ.*.ecz, written by econ/export_econ.py) through the decoder: header
// contract, a few known magnitudes, the market-row cases on real instruments. Skipped when the build shipped no file.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { gdppc, growth10, growthAnnual, hasEcon, income, instruments, lastEconYear, marketRow, mobility, parseEcon, stage, thenWhat, tfr, vtFlag } from './econ.ts';
import metaJson from '../data/meta.json';

const DIR = join(__dirname, '..', '..', 'public', 'data', 'wpp2024');
const file = existsSync(DIR) ? readdirSync(DIR).find((f) => /^econ\.[0-9a-f]{8}\.ecz$/.test(f)) : undefined;

describe.skipIf(!file)('econ.*.ecz (real file)', () => {
  const raw = readFileSync(join(DIR, file!));
  const buf = raw[0] === 0x1f && raw[1] === 0x8b ? gunzipSync(raw) : raw;
  const e = parseEcon(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer);

  it('is the file meta.json points at, on the wire ≤ 160 KB, 1950–2024, countries only', () => {
    expect((metaJson as { files: { econ?: string } }).files.econ).toBe(`data/wpp2024/${file}`);
    expect(raw.byteLength).toBeLessThanOrEqual(160_000);
    expect(e.yearMin).toBe(1950);
    expect(e.yearMax).toBe(2024);
    expect(e.ids.length).toBeGreaterThan(150);
    expect(e.ids.every((id) => /^[A-Z]{3}$/.test(id))).toBe(true);
    expect(lastEconYear(e)).toBe(2024);
    expect(e.growth10Shipped).not.toBeNull(); // the export ships both g_rgdp (10-y) and g_rgdp_1y
  });

  it('known magnitudes: Japan and China GDP/cap, income groups, stages, TFR', () => {
    const jp1990 = gdppc(e, 'JPN', 1990)!;
    expect(jp1990).toBeGreaterThan(20_000); // Maddison 2011$: ≈ 30k
    expect(jp1990).toBeLessThan(45_000);
    const cn = thenWhat(e, 'CHN', 1990);
    expect(cn.gdppcThen).toBeGreaterThan(1000);
    expect(cn.gdppcThen).toBeLessThan(3000);
    expect(cn.horizons.find((h) => h.h === 30)?.multiple).toBeGreaterThan(4); // RESULTS §6: ×9.4 on the PWT level; the Maddison-based series gives ≈ ×5.8
    expect(income(e, 'JPN', 2000)?.short).toBe('H');
    expect(income(e, 'JPN', 1980)).toBeNull(); // before OGHIST
    expect(income(e, 'IND', 2000)?.short).toBe('L');
    expect(stage(e, 'JPN', 2020)?.label).toBe('post-dividend');
    expect(stage(e, 'NER', 2020)?.label).toBe('pre-dividend');
    expect(tfr(e, 'NER', 2000)).toBeGreaterThan(6);
    expect(growth10(e, 'CHN', 2010)).toBeGreaterThan(7);
    expect(growthAnnual(e, 'CHN', 2010)).toBeGreaterThan(5);
    expect(hasEcon(e, 'JPN')).toBe(true);
  });

  it('instruments + market rows on real funds', () => {
    const ind = instruments(e, 'IND');
    expect(ind.map((i) => i.ticker)).toEqual(['EPI', 'INDA']); // earliest inception first
    expect(ind[1]!.windows.map((w) => w.label)).toContain('10y');
    const cn1990 = marketRow(e, 'CHN', 1990);
    expect(cn1990.kind).toBe('later'); // FXI since 2004
    expect(cn1990.instrument?.ticker).toBe('FXI');
    expect(cn1990.note).toBe('1990');
    const kor2005 = marketRow(e, 'KOR', 2005);
    expect(kor2005.kind).toBe('existed');
    expect(kor2005.window).toMatchObject({ y1: 2005, y2: 2015, vt: 'vt_proxy' });
    expect(kor2005.window!.rVt).not.toBeNull();
    const nga2015 = marketRow(e, 'NGA', 2015);
    expect(nga2015.kind).toBe('liquidated');
    expect(nga2015.instrument?.ticker).toBe('NGE');
    expect(nga2015.note).toBe('2024-03-25');
    expect(mobility(e, 'NGA')).toBe('closed');
    expect(marketRow(e, 'NPL', 2000).kind).toBe('none');
    expect(vtFlag(e, 2010, 2020)).toBe('vt');
    expect(vtFlag(e, 2000, 2010)).toBe('vt_proxy');
  });
});
