import { describe, expect, it } from 'vitest';
import {
  csvEscape,
  filename,
  fmtNum,
  footerText,
  PYRAMID_CSV_HEADER,
  pyramidToCsv,
  RESULTS_CSV_HEADER,
  resultsToCsv,
  slugPart,
  toCsv,
  type ResultsCsvRow,
} from './export.ts';

describe('filename scheme', () => {
  it.each<[string | number, string]>([
    ['Japan', 'japan'],
    ['South Korea', 'south-korea'],
    ["Côte d'Ivoire", 'cote-d-ivoire'],
    ['Réunion', 'reunion'],
    ['São Tomé and Príncipe', 'sao-tome-and-principe'],
    ['Türkiye', 'turkiye'],
    [2026, '2026'],
    ['  --weird__name!! ', 'weird-name'],
    ['', ''],
  ])('slugPart(%j) → %j', (input, want) => expect(slugPart(input)).toBe(want));

  it.each<[ReadonlyArray<string | number | null | undefined>, string, string]>([
    [['Japan', 2026, 'pyramid'], 'png', 'japan-2026-pyramid.png'],
    [['South Korea', 2026, 'vs', 'Japan', 2008, 'compare'], 'svg', 'south-korea-2026-vs-japan-2008-compare.svg'],
    [['Japan', 2026, 'similar'], '.CSV', 'japan-2026-similar.csv'],
    [['', null, undefined, 'x'], 'csv', 'x.csv'],
    [['!!!'], 'png', 'export.png'],
    [[], 'png', 'export.png'],
  ])('filename(%j, %j) → %j', (parts, ext, want) => expect(filename(parts, ext)).toBe(want));

  it('caps the stem at 120 characters without a dangling dash', () => {
    const f = filename(['a'.repeat(119), 'bcd'], 'csv');
    expect(f.length).toBeLessThanOrEqual(124);
    expect(f).toMatch(/^a{119}\.csv$|^a{119}-?\.csv$/);
    expect(f).not.toContain('-.');
  });
});

describe('footer text', () => {
  it('matches the PLAN §7 template', () => {
    expect(footerText('Japan', 2026, 122427.733)).toBe('Japan · 2026 · Pop 122.4M · Source: UN WPP 2024 · Population Pyramid Explorer');
    expect(footerText('Niue', 1950, 4.6)).toBe('Niue · 1950 · Pop 4.6K · Source: UN WPP 2024 · Population Pyramid Explorer');
  });
});

describe('CSV primitives', () => {
  it.each<[unknown, string]>([
    ['plain', 'plain'],
    ['has,comma', '"has,comma"'],
    ['has "quote"', '"has ""quote"""'],
    ['line\nbreak', '"line\nbreak"'],
    [' padded', '" padded"'],
    [null, ''],
    [undefined, ''],
    [0.1 + 0.2, '0.3'],
    [1994, '1994'],
    [-18, '-18'],
    [NaN, ''],
  ])('csvEscape(%j) → %j', (v, want) => expect(csvEscape(v)).toBe(want));

  it('fmtNum keeps six decimals at most', () => {
    expect(fmtNum(0.43456789123)).toBe('0.434568');
    expect(fmtNum(2)).toBe('2');
    expect(fmtNum(Infinity)).toBe('');
  });

  it('toCsv writes header + rows with a trailing newline', () => {
    expect(toCsv(['a', 'b'], [[1, 'x'], [2, 'y,z']])).toBe('a,b\n1,x\n2,"y,z"\n');
    expect(toCsv(['a'], [])).toBe('a\n');
  });
});

describe('resultsToCsv', () => {
  const rows: ResultsCsvRow[] = [
    { rank: 1, raw_rank: 1, id: 'TWN', name: 'Taiwan', year: 2026, d: 0.2264, band: 'very_close', dy: 0 },
    { rank: 2, raw_rank: 7, id: 'JPN', name: 'Japan', year: 2008, d: 0.4346, band: 'close', dy: -18 },
  ];
  it('has the PLAN §7 columns in order', () => {
    expect([...RESULTS_CSV_HEADER]).toEqual(['rank', 'raw_rank', 'id', 'name', 'year', 'd', 'band', 'dy']);
    const csv = resultsToCsv(rows);
    const lines = csv.trimEnd().split('\n');
    expect(lines[0]).toBe('rank,raw_rank,id,name,year,d,band,dy');
    expect(lines[1]).toBe('1,1,TWN,Taiwan,2026,0.2264,very_close,0');
    expect(lines[2]).toBe('2,7,JPN,Japan,2008,0.4346,close,-18');
    expect(lines).toHaveLength(3);
  });
  it('quotes names that contain commas', () => {
    const csv = resultsToCsv([{ ...rows[0]!, name: 'Bonaire, Sint Eustatius and Saba' }]);
    expect(csv).toContain('"Bonaire, Sint Eustatius and Saba"');
  });
});

describe('pyramidToCsv', () => {
  // a synthetic two-bin pyramid: 30 % male 0–4, 20 % female 0–4, 50 % female 100+; total 1,000 thousand
  const shares = new Float32Array(42);
  shares[0] = 0.3;
  shares[21] = 0.2;
  shares[41] = 0.5;
  const focal = { id: 'XXX', name: 'Testland', year: 2000, shares, total: 1000 };

  it('emits 21 rows per pyramid with persons and percent columns', () => {
    const lines = pyramidToCsv(focal).trimEnd().split('\n');
    expect(lines[0]).toBe(PYRAMID_CSV_HEADER.join(','));
    expect(lines).toHaveLength(1 + 21);
    expect(lines[1]).toBe('Testland 2000,XXX,2000,0,0-4,300000,200000,30,20');
    expect(lines[21]).toBe('Testland 2000,XXX,2000,100,100+,0,500000,0,50');
    expect(lines[5]).toBe('Testland 2000,XXX,2000,20,20-24,0,0,0,0');
  });

  it('appends the overlay pyramid as a second block', () => {
    const overlay = { ...focal, id: 'YYY', name: 'Otherland', year: 1990, total: 10 };
    const lines = pyramidToCsv(focal, overlay).trimEnd().split('\n');
    expect(lines).toHaveLength(1 + 42);
    expect(lines[22]).toBe('Otherland 1990,YYY,1990,0,0-4,3000,2000,30,20');
  });

  it('rounds shares to the u16 resolution, not float noise', () => {
    const s = new Float32Array(42);
    s[3] = 1 / 3;
    const line = pyramidToCsv({ id: 'Z', name: 'Z', year: 1, shares: s, total: 3 }).trimEnd().split('\n')[4]!;
    expect(line).toBe('Z 1,Z,1,15,15-19,1000,0,33.3333,0');
  });
});
