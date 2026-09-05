import { describe, expect, it } from 'vitest';
import type { Features } from './math/features.ts';
import { narrative, tense, type NarrativeInput } from './narrative.ts';

function feats(over: Partial<Features> = {}): Features {
  return {
    median_age: 49.4,
    mean_age: 48,
    u15: 0.113,
    wa: 0.58,
    o65: 0.307,
    o80: 0.11,
    child_dep: 0.113 / 0.58,
    old_dep: 0.307 / 0.58,
    total_dep: 0.42 / 0.58,
    base_slope_20: 0.65,
    base_slope_10: 0.8,
    modal_bin: 50,
    wa_sex_ratio: 1.02,
    stage: 'constrictive',
    flag_male_skew: false,
    flag_urn: true,
    ...over,
  };
}

function input(over: Partial<NarrativeInput> = {}): NarrativeInput {
  return {
    name: 'Japan',
    isAggregate: false,
    year: 2026,
    era: 'nowcast',
    total: 122427.733,
    features: feats(),
    change: { from: 2016, to: 2026, fraction: -0.035 },
    lastObservedYear: 2023,
    ...over,
  };
}

describe('narrative', () => {
  it('Japan 2026 (nowcast, constrictive, urn)', () => {
    const p = narrative(input());
    expect(p.length).toBeGreaterThanOrEqual(3);
    expect(p[0]).toBe('Japan has a population of about 122.43M in 2026, down 3.5% since 2016.');
    expect(p[1]).toContain('median age is 49.4 years');
    expect(p[1]).toContain('constrictive');
    expect(p[1]).toContain('11% of the population');
    expect(p[1]).toContain('11.0% aged 80+');
    expect(p[2]).toMatch(/^For every 100 people of working age there are 72 dependants — mostly older people \(19 under 15, 53 aged 65\+\)\.$/);
    expect(p[3]).toContain('urn-shaped');
    expect(p[3]).toContain('2026 is a UN nowcast');
  });

  it('observed year uses the past tense and no caveat', () => {
    const p = narrative(input({ year: 1990, era: 'observed', change: { from: 1980, to: 1990, fraction: 0.056 } }));
    expect(p[0]).toBe('Japan had a population of about 122.43M in 1990, up 5.6% since 1980.');
    expect(p[1]).toContain('median age was');
    expect(p.join(' ')).not.toContain('nowcast');
    expect(p.join(' ')).not.toContain('projection');
  });

  it('projected year flags projections; distant years get the convergence note', () => {
    const near = narrative(input({ year: 2040, era: 'projected' })).join(' ');
    expect(near).toContain('is projected to be');
    expect(near).toContain('Figures after 2023 are UN medium-variant projections.');
    const far = narrative(input({ year: 2080, era: 'projected' })).join(' ');
    expect(far).toContain('converge');
  });

  it('expansive with male skew (Gulf-style) and forward-looking change', () => {
    const p = narrative(
      input({
        name: 'Qatar',
        year: 1955,
        era: 'observed',
        total: 40,
        change: { from: 1955, to: 1965, fraction: 0.9 },
        features: feats({
          median_age: 21,
          stage: 'expansive',
          u15: 0.4,
          wa: 0.55,
          o65: 0.05,
          o80: 0.005,
          child_dep: 0.4 / 0.55,
          old_dep: 0.05 / 0.55,
          total_dep: 0.45 / 0.55,
          wa_sex_ratio: 2.4,
          flag_male_skew: true,
          flag_urn: false,
          modal_bin: 0,
          base_slope_20: 1.5,
        }),
      }),
    );
    expect(p[0]).toBe('Qatar had a population of about 40K in 1955, heading up 90.0% by 1965.');
    expect(p[1]).toContain('expansive');
    expect(p[1]).not.toContain('aged 80+');
    expect(p[2]).toContain('almost all of them children');
    expect(p[3]).toContain('Men outnumber women 2.40 to 1');
  });

  it('flat change and missing change', () => {
    expect(narrative(input({ change: { from: 2016, to: 2026, fraction: 0.0001 } }))[0]).toContain('essentially unchanged over the previous 10 years');
    expect(narrative(input({ change: null }))[0]).toBe('Japan has a population of about 122.43M in 2026.');
  });

  it('tense table', () => {
    expect(tense('observed').be).toBe('was');
    expect(tense('nowcast').be).toBe('is');
    expect(tense('projected').be).toBe('is projected to be');
  });
});
