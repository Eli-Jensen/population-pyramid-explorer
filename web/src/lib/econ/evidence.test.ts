// Evidence-page traceability (review fixes): the exported JSON carries every fund figure in both units, so the page's
// %/yr (CAGR) numbers equal the L0.vs_vt sentence's, the RESULTS §1 vintage table parsed cleanly, the disconnect
// rows carry the level series and a same-unit VT for the too-short window, and the frozen liquidation date is annotated.
import { describe, expect, it } from 'vitest';
import { ciCovers0, evidence as ev, logToCagr, logToTotal, pct, pp, topShare } from './evidence.ts';
import { rendered } from './lang.ts';

const VINTAGE_FAMILIES = new Set(['curated', 'maddison', 'oghist', 'pwt', 'wdi', 'wpp']);

describe('evidence.json units and traceability', () => {
  it('the NGE member of the returns row prints the same numbers as the allowed L0.vs_vt sentence', () => {
    const t2015 = ev.backtest.returns.per_T.find((t) => t.T === 2015)!;
    const nge = t2015.members.find((m) => m.ticker === 'NGE')!;
    expect(nge.status).toBe('liquidated_in_window');
    // the export carries log pp/yr AND CAGR; the CAGR is 100·(e^r − 1) of the log figure
    expect(nge.r_cagr).toBeCloseTo(logToCagr(nge.r_pp! / 100)!, 9);
    expect(nge.r_vt_cagr).toBeCloseTo(logToCagr(nge.r_vt_pp! / 100)!, 9);
    expect(nge.r_pp).toBeCloseTo(-7.34, 2); // RESULTS §8: NGE 2015–2025 −7.34 pp/yr log
    expect(nge.r_vt_pp).toBeCloseTo(11.12, 2); // VT +11.12 pp/yr log
    const sentence = rendered('L0.vs_vt').find((s) => s.startsWith('NGE '))!;
    expect(sentence).toBe(`NGE total return 2015–2025: ${pp(nge.r_cagr)} %/yr · VT over the same window: ${pp(nge.r_vt_cagr)} %/yr.`);
    // the row's VT column is the member's VT (identical window, identical unit)
    expect(t2015.r_vt_cagr).toBeCloseTo(nge.r_vt_cagr!, 9);
    expect(pp(t2015.r_vt_cagr)).toBe('+11.8');
    // the benchmarks table prints the same CAGR for the same window
    const b2015 = ev.backtest.benchmarks.find((b) => b.T === 2015)!;
    expect(b2015.r_vt_cagr).toBeCloseTo(t2015.r_vt_cagr, 6);
    expect(b2015.r_vt_cagr).toBeCloseTo(logToCagr(b2015.r_vt_ann)!, 9);
    expect(b2015.ew.r_cagr).toBeCloseTo(logToCagr(b2015.ew.r_ann)!, 9);
  });

  it('a liquidated member carries the SEC-filing last trading day beside the frozen universe date', () => {
    const nge = ev.backtest.returns.per_T.flatMap((t) => t.members).find((m) => m.ticker === 'NGE')!;
    expect(nge.delisted_universe).toBe('2023-07-28');
    expect(nge.last_trading_day).toBe('2024-03-25');
    const inv = ev.investability.rows.find((r) => r.ticker === 'NGE')!;
    expect(inv.last_trading_day).toBe(nge.last_trading_day);
    // the frozen decision sentence is annotated, not edited
    expect(ev.decision.rendered['L0.investability']).toContain('NGE was liquidated on 2023-07-28 (issuer notice).');
    expect(ev.decision.rendered_notes).toEqual([{ sentence: 'NGE was liquidated on 2023-07-28 (issuer notice).', ticker: 'NGE', universe_date: '2023-07-28', last_trading_day: '2024-03-25' }]);
  });

  it('the RESULTS §1 vintage table parsed only vintage rows (no candidate-set rows), shipped sources only', () => {
    expect(ev.data_vintages.length).toBe(7);
    for (const v of ev.data_vintages) {
      expect(VINTAGE_FAMILIES.has(v.family), `${v.source} / ${v.family}`).toBe(true);
      expect(v.shipped).toBe('yes');
      expect(/^\d+, (growth|returns)$/.test(v.source)).toBe(false);
    }
    expect(ev.data_vintages_note).toMatch(/1 build-time-only source/);
  });

  it('disconnect rows name the level series and pair a too-short fund total with VT in the same unit', () => {
    const chn = ev.china.row!;
    expect(chn.levels.source).toBe('PWT 11.0 rgdpe/pop, 2017 PPP $');
    expect(chn.levels.y_t).toBeCloseTo(1934.77, 2);
    expect(chn.fund.cagr_pct).toBeCloseTo(logToCagr(chn.fund.ann_log_return)!, 9);
    expect(chn.fund.vt_cagr_pct).toBeCloseTo(logToCagr(chn.fund.vt)!, 9);
    for (const r of ev.disconnect.rows.filter((r) => r.kind === 'history')) expect(r.levels.source, r.iso3).toBeTruthy();
    const twn = ev.disconnect.rows.find((r) => r.iso3 === 'TWN' && r.year === 1970)!;
    expect(twn.fund.too_short_to_annualise).toBe(true);
    expect(twn.fund.vt_total_log).toBeCloseTo(-0.0902, 4); // RESULTS §6: VT −9.02 pp total for that row
    expect(pct(logToTotal(twn.fund.vt_total_log), 1)).toBe('-8.6 %');
    expect(pct(twn.fund.total_return, 1)).toBe('-42.9 %');
    expect(twn.fund.vt_total_pct).toBeCloseTo(100 * logToTotal(twn.fund.vt_total_log)!, 9);
  });

  it('interpretive words are derived, and the never-does list matches what the code enforces', () => {
    expect(ciCovers0(ev.backtest.growth.ci_headline)).toBe('includes 0');
    expect(ciCovers0([0.1, 0.5])).toBe('excludes 0');
    expect(ciCovers0([-0.5, -0.1])).toBe('excludes 0');
    expect(topShare(0.9)).toBe('top-decile');
    expect(topShare(0.75)).toBe('top-quartile');
    expect(topShare(0.95)).toBe('top-5 %');
    expect(ev.backtest.partial_note).toBe('PWT h = 8 → 2023, Maddison h = 7 → 2022');
    expect(ev.vintage.spearman).toBeTruthy();
    expect(ev.vintage.spearman!.min).toBeGreaterThan(0.8);
    expect(ev.vintage.spearman!.max).toBeLessThan(1);
    expect(ev.vintage.spearman!.n).toBe(15);
    expect(ev.backtest.predictions.P3b.met).toBe(true);
    expect(ev.never_does.some((n) => /ranks results by return/.test(n))).toBe(false);
    expect(ev.never_does.some((n) => /result lists/.test(n) && /rank\)/.test(n))).toBe(true);
    expect(ev.never_does.some((n) => /claim outside the pre-registered templates/.test(n) && /deny list/.test(n))).toBe(true);
    expect(ev.units_note).toMatch(/compound annual growth rate/);
  });
});
