import { describe, expect, it } from 'vitest';
import {
  ageLabel,
  fmtInt,
  fmtPct,
  fmtPersons,
  fmtPersonsCompact,
  fmtRatio,
  fmtSignedPct,
  fmtYears,
  sexRatio,
} from './format.ts';

describe('format', () => {
  it.each<[number, string]>([
    [0, '0'],
    [999, '999'],
    [1000, '1,000'],
    [122427733, '122,427,733'],
    [1234.6, '1,235'],
    [NaN, '—'],
  ])('fmtInt(%s) → %s', (n, want) => expect(fmtInt(n)).toBe(want));

  it.each<[number, string]>([
    [122427.733, '122,427,733'],
    [108.168, '108,168'],
    [0.5, '500'],
    [Infinity, '—'],
  ])('fmtPersons(%s thousands) → %s', (n, want) => expect(fmtPersons(n)).toBe(want));

  it.each<[number, string]>([
    [122427.733, '122.4M'],
    [8_000_000, '8B'],
    [108.168, '108.2K'],
    [1.2, '1.2K'],
    [0.05, '50'],
  ])('fmtPersonsCompact(%s) → %s', (n, want) => expect(fmtPersonsCompact(n)).toBe(want));

  it('fmtPct handles fractions and already-percent values', () => {
    expect(fmtPct(0.123)).toBe('12.3%');
    expect(fmtPct(0.123, 0)).toBe('12%');
    expect(fmtPct(4.56, 1, true)).toBe('4.6%');
    expect(fmtPct(NaN)).toBe('—');
  });

  it.each<[number, string]>([
    [0.0234, '+2.3%'],
    [-0.01, '−1.0%'],
    [0, '±0.0%'],
    [0.0004, '±0.0%'],
    [NaN, '—'],
  ])('fmtSignedPct(%s) → %s', (n, want) => expect(fmtSignedPct(n)).toBe(want));

  it('fmtYears', () => {
    expect(fmtYears(49.36)).toBe('49.4');
    expect(fmtYears(NaN)).toBe('—');
  });

  it.each<[number, string]>([
    [0, '0–4'],
    [1, '5–9'],
    [19, '95–99'],
    [20, '100+'],
  ])('ageLabel(%s) → %s', (k, want) => expect(ageLabel(k)).toBe(want));

  it('sexRatio / fmtRatio', () => {
    expect(sexRatio(0.05, 0.05)).toBe(100);
    expect(sexRatio(0.06, 0.05)).toBeCloseTo(120, 6);
    expect(sexRatio(0.01, 0)).toBeNaN();
    expect(fmtRatio(NaN)).toBe('—');
    expect(fmtRatio(1.0567)).toBe('1.06');
  });
});
