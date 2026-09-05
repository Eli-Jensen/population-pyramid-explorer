// Shape + consistency of web/src/data/evals.json (scripts/export_evals.py) against meta.json — the About page
// renders every number from these two files, so they must agree with each other and with the pre-registered gates.
import { describe, expect, it } from 'vitest';
import { evals, g1Of, imageSpace, orderedMetrics, fmt, fmtPctOf } from './evals.ts';
import { meta } from './data.ts';

const VERDICTS = ['default', 'menu', 'advanced', 'lab', 'rejected'];

describe('evals.json shape', () => {
  it('carries the documented top-level keys', () => {
    for (const k of [
      'built', 'stage', 'informational', 'data_hash', 'gates', 'prereg', 'g1', 'g2', 'verdicts', 'exposed_visual',
      'image_spaces', 'notes', 'n_countries', 'n_entities', 'n_rows',
    ]) {
      expect(evals, k).toHaveProperty(k);
    }
    expect(evals.built).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(evals.data_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(evals.informational).toBe(true);
    expect(evals.notes.length).toBeGreaterThan(0);
  });

  it('g1 rows: one per metric, numbers in [0, 1], gate = (C1 ≥ c1) ∧ (C5 ≥ c5)', () => {
    expect(evals.g1.length).toBeGreaterThanOrEqual(9);
    const { c1, c5 } = evals.prereg.continuity_gate;
    expect(c1).toBe(evals.gates.c1);
    expect(c5).toBe(evals.gates.c5);
    for (const r of evals.g1) {
      for (const k of ['c1_obs', 'c5_obs', 'c1_proj', 'c5_proj'] as const) {
        const v = r[k];
        expect(v, `${r.metric}.${k}`).not.toBeNull();
        expect(v!).toBeGreaterThanOrEqual(0);
        expect(v!).toBeLessThanOrEqual(1);
      }
      expect(r.gate, r.metric).toBe(r.c1_obs! >= c1 && r.c5_obs! >= c5);
    }
    expect(new Set(evals.g1.map((r) => r.metric)).size).toBe(evals.g1.length);
  });

  it('g2 rows mirror g1 metrics and carry the gate breakdown', () => {
    expect(evals.g2.map((r) => r.metric)).toEqual(evals.g1.map((r) => r.metric));
    for (const r of evals.g2) {
      expect(r.gates).toHaveProperty('G1');
      expect(r.gates).toHaveProperty('G2');
      expect(r.gates).toHaveProperty('G4');
      expect(r.gate).toBe(r.gates.G2);
    }
  });

  it('verdicts: a valid word per metric, and the same word meta.json ships to the menu', () => {
    const metricsInMeta = meta.verdicts?.metrics ?? {};
    for (const [m, v] of Object.entries(evals.verdicts)) {
      expect(VERDICTS, m).toContain(v.verdict);
      expect(typeof v.provisional).toBe('boolean');
      // the UI ships `shipped` (build_data.py caps evaluation-only metrics without bands at `lab`); the record keeps
      // the evaluation verdict and says when the two differ
      const inMeta = metricsInMeta[m];
      expect(v.shipped ?? null, `${m}: shipped verdict`).toBe(inMeta?.verdict ?? null);
      if (v.shipped && v.shipped !== v.verdict) expect(v.shipped_note, m).toBeTruthy();
      else expect(v.shipped_note, m).toBeUndefined();
    }
    expect(evals.verdicts.blend?.verdict).toBe('default');
    expect(Object.keys(evals.verdicts).sort()).toEqual(evals.g1.map((r) => r.metric).sort());
  });

  it('the exposed image space is the one meta.json exposes and it did not pass continuity', () => {
    expect(evals.exposed_visual).not.toBeNull();
    const ev = evals.exposed_visual!;
    expect(ev.model).toBe(meta.verdicts?.exposed_visual?.model);
    expect(ev.metric).toBe(`visual:${ev.model}`);
    const row = g1Of(ev.metric);
    expect(row).toBeDefined();
    expect(row!.c1_obs).toBeCloseTo(ev.C1_obs, 6);
    expect(row!.gate).toBe(false);
    expect(row!.c1_obs!).toBeLessThan(evals.gates.c1);
  });

  it('image spaces: every visual metric has a row with the embed-script diagnostics merged in', () => {
    const visual = evals.g1.filter((r) => r.metric.startsWith('visual:'));
    expect(evals.image_spaces.length).toBe(visual.length);
    for (const s of evals.image_spaces) {
      expect(s.metric).toBe(`visual:${s.model}`);
      expect(VERDICTS).toContain(s.verdict);
      expect(s.c1).toBeCloseTo(g1Of(s.metric)!.c1_obs!, 9);
      expect(s.spearman_vs_blend).not.toBeNull();
      expect(s.top10_overlap).not.toBeNull();
      expect(s.top10_overlap!).toBeLessThanOrEqual(1);
      expect(s.expected_verdict).toBe(evals.prereg.expected_visual_verdict);
      expect(s.prediction_met).toBe(s.verdict === s.expected_verdict);
      expect(s.predictions_scored.length).toBeGreaterThan(0);
      for (const p of s.predictions_scored) expect(typeof p.met).toBe('boolean');
    }
    expect(imageSpace(evals.exposed_visual!.model)).toBeDefined();
  });

  it('pre-registered predictions P1…P7 are present in order', () => {
    expect(evals.prereg.image_predictions.map((p) => p.id)).toEqual(['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']);
    for (const p of evals.prereg.image_predictions) {
      expect(p.prediction.length).toBeGreaterThan(5);
      expect(p.gate.length).toBeGreaterThan(0);
    }
    // the escaped `\|Δy\|` cell must survive the markdown parse intact
    expect(evals.prereg.image_predictions[0]!.measured_by).toContain('|Δy| ≤ 1');
  });

  it('corpus counts agree with meta.json', () => {
    expect(evals.n_countries).toBe(meta.n_countries);
    expect(evals.n_entities).toBe(meta.n_entities);
    expect(evals.n_rows).toBe(meta.n_rows);
  });

  it('findings blocks the About page reads are present', () => {
    expect(evals.div_presets).toEqual({ strict: 0, balanced: 0.5, spread: 2 });
    expect(evals.blend_w1_share).not.toBeNull();
    expect(evals.beta_sweep!.length).toBeGreaterThan(3);
  });
});

describe('evals helpers', () => {
  it('orderedMetrics puts image spaces last', () => {
    const m = orderedMetrics();
    const firstVisual = m.findIndex((x) => x.startsWith('visual:'));
    expect(firstVisual).toBeGreaterThan(0);
    expect(m.slice(firstVisual).every((x) => x.startsWith('visual:'))).toBe(true);
  });
  it('fmt / fmtPctOf', () => {
    expect(fmt(0.55)).toBe('0.550');
    expect(fmt(null)).toBe('—');
    expect(fmt(0.9933, 2)).toBe('0.99');
    expect(fmtPctOf(0.302)).toBe('30 %');
    expect(fmtPctOf(null)).toBe('—');
  });
});
