/** Unit tests for explain.ts / explain.templates.ts on synthetic vectors (real-pair parity + snapshots: search.integration.test.ts). */
import { describe, expect, test } from 'vitest';
import { meta } from './data.ts';
import { decompose, decomposeMetric, explainSentence, featureDeltas } from './explain.ts';
import { becauseSentence, binLabel, decompositionSentence, differsSentence, formatFeature, joinList, percentileClause, w1Sentence } from './explain.templates.ts';
import { fromCorpus } from './search.ts';
import { N_BINS, N_DIMS, N_YEARS, U16_TOTAL, YEAR_MIN, type Corpus, type Entity } from './types.ts';

const sigma = meta.sigma;

/** Two-entity corpus: entity 0 = flat profile, entity 1 = the same profile shifted one bin older (male share 0.6). */
function corpus(): Corpus {
  const ents = 2;
  const nRows = ents * N_YEARS;
  const u16 = new Uint16Array(nRows * N_DIMS);
  const totals = new Float32Array(nRows).fill(5000);
  for (let e = 0; e < ents; e++) {
    for (let i = 0; i < N_YEARS; i++) {
      const row = new Float64Array(N_DIMS);
      for (let k = 0; k < N_BINS; k++) {
        const a = k < 12 + e ? 1 : k < 16 + e ? 0.5 : 0.1;
        row[k] = (e ? 0.6 : 0.5) * a;
        row[N_BINS + k] = (e ? 0.4 : 0.5) * a;
      }
      const s = row.reduce((x, y) => x + y, 0);
      let used = 0;
      const r = e * N_YEARS + i;
      for (let k = 0; k < N_DIMS; k++) {
        u16[r * N_DIMS + k] = Math.floor((row[k] / s) * U16_TOTAL);
        used += u16[r * N_DIMS + k];
      }
      u16[r * N_DIMS] += U16_TOTAL - used;
    }
  }
  return { nRows, nEntities: ents, nYears: N_YEARS, u16, totals, source: { path: 'u16-fallback', decodeMs: 0, fetchMs: 0 } };
}
const ents = [{ id: 'A', type: 'country' }, { id: 'B', type: 'country' }] as unknown as Entity[];
const view = fromCorpus(corpus(), ents);
const qa = view.rowOf('A', 2000);
const qb = view.rowOf('B', 2000);

describe('decompose', () => {
  test('blend: l2Part + w1Part = d; parts follow the σ normalisation; top bins are the shifted ones', () => {
    const dec = decompose(view, { metric: 'blend', sex: '2' }, qa, qb, sigma);
    expect(dec.metric).toBe('blend');
    expect(dec.d).toBeCloseTo(dec.l2Part + dec.w1Part, 12);
    expect(dec.l2Part).toBeGreaterThan(0);
    expect(dec.w1Part).toBeGreaterThan(0);
    expect(dec.w1Years).toBeCloseTo((2 * dec.w1Part * sigma.w1sex['2']) / 1, 9);
    expect(dec.topBinsL2.length).toBe(3);
    expect(dec.topBinsL2.map(([, f]) => f).reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(1 + 1e-12);
    expect(dec.topBinsL2[0][1]).toBeGreaterThanOrEqual(dec.topBinsL2[1][1]);
    expect(dec.topBinsW1[0][1]).toBeGreaterThanOrEqual(dec.topBinsW1[1][1]);
    // the query on itself decomposes to zero everywhere
    const self = decompose(view, { metric: 'blend', sex: '2' }, qa, qa, sigma);
    expect(self.d).toBe(0);
    expect(self.topBinsL2.map(([k]) => k)).toEqual([0, 1, 2]); // all fractions 0 → index order
  });

  test('l2 / w1 / w1sex report the foreign term as 0; sex=1 uses s21 bins; other metrics fall back to blend', () => {
    const l2 = decompose(view, { metric: 'l2', sex: '2' }, qa, qb, sigma);
    expect(l2.w1Part).toBe(0);
    expect(l2.l2Part).toBe(l2.d);
    const w1 = decompose(view, { metric: 'w1', sex: '2' }, qa, qb, sigma);
    expect(w1.l2Part).toBe(0);
    expect(w1.w1Part).toBe(w1.d);
    const w1sex = decompose(view, { metric: 'w1sex', sex: '2' }, qa, qb, sigma);
    expect(w1sex.d).toBeCloseTo(w1sex.w1Years, 12);
    expect(w1.d).not.toBeCloseTo(w1sex.d, 6); // sex-blind vs per-sex transport differ when the sex mix differs
    const w1sex1 = decompose(view, { metric: 'w1sex', sex: '1' }, qa, qb, sigma);
    expect(w1sex1.d).toBeCloseTo(decompose(view, { metric: 'w1', sex: '1' }, qa, qb, sigma).d, 12);
    const s1 = decompose(view, { metric: 'blend', sex: '1' }, qa, qb, sigma);
    expect(s1.topBinsL2.every(([k]) => k < N_BINS)).toBe(true);
    for (const m of ['l2s', 'hel', 'feat', 'w1bal', 'visual'] as const) expect(decompose(view, { metric: m, sex: '2' }, qa, qb, sigma).metric).toBe('blend');
    expect(decomposeMetric('l2', 'motion')).toBe('blend');
    expect(decomposeMetric('w1sex')).toBe('w1sex');
  });
});

describe('featureDeltas + sentences', () => {
  test('z-scores against the reference year (both entities), alike = 2 smallest |Δz|, differs = the largest', () => {
    const fd = featureDeltas(view, ents, qa, qb, 2000, { minpop: 0 });
    expect(fd.referenceYear).toBe(2000);
    expect(fd.nReference).toBe(2);
    expect(fd.all.length).toBe(6);
    expect(fd.alike.length).toBe(2);
    expect(fd.differs.length).toBe(1);
    for (let i = 1; i < fd.all.length; i++) expect(fd.all[i].dz).toBeGreaterThanOrEqual(fd.all[i - 1].dz);
    // two-member reference: z-scores are ±1 (or 0 where equal), so |Δz| ∈ {0, 2}
    for (const f of fd.all) expect([0, 2].some((v) => Math.abs(f.dz - v) < 1e-9)).toBe(true);
    expect(() => featureDeltas(view, ents, qa, qb, 2000, { minpop: 0, stats: { year: 1999, rows: new Int32Array(), mu: new Float64Array(13), sd: new Float64Array(13) } })).toThrow(/stats are for 1999/);
    const sent = explainSentence(decompose(view, { metric: 'blend', sex: '2' }, qa, qb, sigma), fd);
    expect(sent.because).toMatch(/^Alike in .+ \(.+ vs .+\)\.$/);
    expect(sent.differsIn).toMatch(/^Differs most in .+\.$/);
    expect(sent.w1Sentence).toMatch(/years of average age movement separate them\.$/);
    expect(sent.decompositionSentence).toMatch(/^Shape distance [\d.]+ = bin-by-bin [\d.]+ \+ age-shift [\d.]+; largest bin gaps /);
  });

  test('templates', () => {
    expect(formatFeature('median_age', 47.29)).toBe('47.3');
    expect(formatFeature('o65', 0.21431)).toBe('21.4 %');
    expect(formatFeature('base_slope_20', 0.478)).toBe('0.48');
    expect(formatFeature('modal_bin', 55)).toBe('55–59');
    expect(formatFeature('modal_bin', 100)).toBe('100+');
    expect(formatFeature('wa_sex_ratio', NaN)).toBe('n/a');
    expect(binLabel(0)).toBe('M 0-4');
    expect(binLabel(20)).toBe('M 100+');
    expect(binLabel(21)).toBe('F 0-4');
    expect(binLabel(41)).toBe('F 100+');
    expect(binLabel(4, '1')).toBe('20-24');
    expect(joinList(['a'])).toBe('a');
    expect(joinList(['a', 'b'])).toBe('a and b');
    expect(joinList(['a', 'b', 'c'])).toBe('a, b and c');
    expect(becauseSentence([])).toBe('');
    expect(differsSentence([{ name: 'u15', rawQ: 0.098, rawC: 0.135 }])).toBe('Differs most in under-15 share (9.8 % vs 13.5 %).');
    expect(w1Sentence(1.9)).toBe('Only 1.90 years of average age movement separate them.');
    expect(w1Sentence(2.61)).toBe('2.61 years of average age movement separate them.');
    expect(decompositionSentence({ metric: 'l2', d: 0.0239, l2Part: 0.0239, w1Part: 0, w1Years: 1.9, topBinsL2: [33, 12], topBinsW1: [], sex: '2' })).toBe('Bin-by-bin distance 0.024; largest bin gaps F 60-64, M 60-64.');
    expect(decompositionSentence({ metric: 'w1', d: 1.897, l2Part: 0, w1Part: 1.897, w1Years: 1.9, topBinsL2: [], topBinsW1: [13], sex: '1' })).toBe('Age-shift distance 1.90 years; most movement at 65-69.');
    expect(percentileClause(99.62, false)).toBe('farther than 99.6 % of random pairs');
    expect(percentileClause(7, true, 'best-year matches')).toBe('closer than 93 % of best-year matches');
    expect(percentileClause(null, true)).toBe('');
  });
});
