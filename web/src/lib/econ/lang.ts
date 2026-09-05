/**
 * The only way a growth or market CLAIM reaches the DOM (PLAN §7 language rules; PREREG §7): "what happened", the null
 * result, "vs VT", investability and the disconnect sentences are rendered here or copied verbatim from decision.json.
 * Table cells and chips (TimeShiftTable, CohortOutcomes, InstrumentBadge, the Evidence tables) print numbers with their
 * window and VT beside them without a template; the deny-list scan in lang.test.ts covers every such string.
 *
 * `render(id, vars)` fills a template from `ui_sentences.json` (a copy of evals/econ/ui_sentences.yaml) and refuses
 * every sentence id that `econ_decision.json#allowed_sentence_ids` does not list — decide.py granted L0 only, so
 * L1.growth_association / L2.returns_signal can never render, whatever a component asks for. In dev the refusal
 * throws (so a wrong id fails the page loudly); in production it returns null and the caller renders nothing.
 * Placeholders use Python's str.format spellings as written in the yaml: `{x}`, `{x:+.1f}`, `{x:.0%}`, `{x:.2f}`.
 * The deny list is exported for lang.test.ts, which scans every string literal under web/src.
 */

import decisionJson from '../../data/econ_decision.json';
import sentencesJson from '../../data/ui_sentences.json';

export interface SentenceSpec {
  level: string;
  placeholders: string[];
  template?: string;
  variants?: Record<string, string>;
  benchmark_note_values?: Record<string, string>;
  fallback_no_msci?: string;
  wa_addendum_if_p2_met?: string;
  wa_addendum_otherwise?: string;
}
export interface SentenceBank {
  version: number;
  deny_list: string[];
  levels: Record<string, { name: string; requires: string[] }>;
  sentences: Record<string, SentenceSpec>;
}
export interface Decision {
  prereg_commit: string;
  levels_granted: string[];
  allowed_sentence_ids: string[];
  levels: Record<string, { name: string; granted: boolean; requires: string[]; failed: string[]; unavailable: string[]; note: string | null }>;
  conditions: Record<string, { value: unknown; ok: boolean; available: boolean; detail: string }>;
  rendered: Record<string, string[]>;
  deny_list: string[];
  run: { generated_at: string; git_rev: string; seed: number; B: number; prereg_commit: string };
}

export const sentences = sentencesJson as unknown as SentenceBank;
export const decision = decisionJson as unknown as Decision;

/** Sentence ids the decision grants (sorted). */
export const ALLOWED_IDS: readonly string[] = [...decision.allowed_sentence_ids].sort();
const allowedSet = new Set(ALLOWED_IDS);

/** Case-insensitive deny-list regexes (single source: ui_sentences.yaml, copied to both JSON files). */
export const DENY_LIST: readonly RegExp[] = sentences.deny_list.map((s) => new RegExp(s, 'i'));

const DEV = !!(import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV;

export function isAllowed(id: string): boolean {
  return allowedSet.has(id);
}

/** First deny-list hit in `text`, or null. */
export function denyHit(text: string): { pattern: string; match: string } | null {
  for (let i = 0; i < DENY_LIST.length; i++) {
    const m = DENY_LIST[i]!.exec(text);
    if (m) return { pattern: sentences.deny_list[i]!, match: m[0] };
  }
  return null;
}

export type Vars = Record<string, string | number | null | undefined>;

/** Python-style `{name}` / `{name:spec}` substitution; unknown or null values render "n/a". */
export function fill(template: string, vars: Vars): string {
  return template.replace(/\{(\w+)(?::([^}]*))?\}/g, (_m, name: string, spec: string | undefined) => formatValue(vars[name], spec));
}

export function formatValue(v: string | number | null | undefined, spec?: string): string {
  if (v === null || v === undefined) return 'n/a';
  if (typeof v === 'string') return v;
  if (!Number.isFinite(v)) return 'n/a';
  if (!spec) return Number.isInteger(v) ? String(v) : String(v);
  const m = /^([+ ]?)(?:\.(\d+))?([f%d]?)$/.exec(spec);
  if (!m) return String(v);
  const sign = m[1] === '+';
  const digits = m[2] !== undefined ? Number(m[2]) : m[3] === 'f' ? 6 : 0;
  const type = m[3];
  let out: string;
  if (type === '%') out = (v * 100).toFixed(digits) + '%';
  else if (type === 'd') out = String(Math.round(v));
  else out = v.toFixed(digits);
  if (sign && v >= 0 && !out.startsWith('-')) out = '+' + out;
  return out.replace(/^-/, '-'); // ASCII minus, as in RESULTS.md
}

/**
 * Render an allowed sentence. `variant` selects a `variants` entry (L0.investability); `note` selects a
 * `benchmark_note_values` entry (L0.vs_vt). Returns null (prod) / throws (dev) for a non-allowed id.
 */
export function render(id: string, vars: Vars = {}, opts: { variant?: string; note?: string } = {}): string | null {
  if (!isAllowed(id)) {
    if (DEV) throw new Error(`lang: sentence id "${id}" is not in decision.json allowed_sentence_ids (${ALLOWED_IDS.join(', ')})`);
    return null;
  }
  const spec = sentences.sentences[id];
  if (!spec) {
    if (DEV) throw new Error(`lang: no template for allowed id "${id}"`);
    return null;
  }
  let template: string | undefined;
  if (opts.variant !== undefined) template = spec.variants?.[opts.variant];
  else template = spec.template;
  if (!template) {
    if (DEV) throw new Error(`lang: id "${id}" has no template${opts.variant ? ` for variant "${opts.variant}"` : ''}`);
    return null;
  }
  const merged: Vars = { ...vars };
  if (spec.benchmark_note_values) merged.benchmark_note = spec.benchmark_note_values[opts.note ?? 'vt'] ?? '';
  const text = fill(template.trim(), merged).replace(/\s+/g, ' ');
  const hit = denyHit(text);
  if (hit) throw new Error(`lang: rendered sentence hits the deny list (${hit.pattern} → "${hit.match}")`);
  return text;
}

// ------------------------------------------------------------------------------------------- convenience

/** L0.investability per the four cases. */
export function investability(kind: 'live' | 'liquidated' | 'none_at_T' | 'none_ever', vars: Vars): string | null {
  return render('L0.investability', vars, { variant: kind });
}

/** L0.vs_vt: `{ticker} total return {y1}–{y2}: {r} %/yr · VT over the same window: {r_vt} %/yr{note}`. */
export function vsVt(vars: { ticker: string; y1: number; y2: number; r: number | null; r_vt: number | null }, note: 'vt' | 'vt_proxy' | 'none'): string | null {
  return render('L0.vs_vt', vars, { note });
}

/** The pre-rendered sentences decide.py wrote for an id (the Evidence page shows them verbatim), or []. */
export function rendered(id: string): string[] {
  return isAllowed(id) ? (decision.rendered[id] ?? []) : [];
}

export { FOOTER_DISCLAIMER, LENS_BANNER } from './copy.ts';
