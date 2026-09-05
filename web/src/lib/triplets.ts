// Human-triplet collector, pure part (PLAN §4.6 item 8, evals/protocol.md §3; page = pages/Triplets.svelte).
//
// `scripts/select_triplets.py` (Z1, src/pyramid_explorer/triplets.py) writes `web/src/data/triplets_selection.json`:
// 88 items in presentation order — 80 unique, stratified visual 32 / numeric 38 / opposite 10, plus 8 duplicates
// (4 / 3 / 1) placed ≥ 30 positions after their original with the displayed LEFT/RIGHT sides swapped (`side_map`);
// the A/B labels and the share rows are identical to the original's. The file also carries the key (entity ids,
// names, years, metrics, distances) for the fit script — `validateSelection` copies ONLY the blind fields into memory
// (three u16 rows, side map, question, stratum, duplicate index) so nothing else can reach the page. The rater is
// blind; the page records the chosen LABEL (A/B/tie, not the side) and the response time and exports exactly what
// `fit_params.py` reads (`response_format` in the selection file):
//   { rater, started, finished, items: [{ item, choice, rt_ms }] }
// Persistence is localStorage under `ppe:triplets:v1`, behind try/catch, so a reload resumes mid-run.

import { N_DIMS, U16_TOTAL } from './types.ts';
import { fitAxis, maxBinPct } from './math/scale.ts';
import type { AxisPct } from './types.ts';

export const STORAGE_KEY = 'ppe:triplets:v1';
export const EXPORT_FILENAME = 'triplets.json';
export const MIN_DUP_GAP = 30;

export type Choice = 'A' | 'B' | 'tie';
export type Label = 'A' | 'B';
export type Side = 'left' | 'right';
export type Stratum = 'visual' | 'numeric' | 'opposite';
export type Variant = 'similar' | 'different';

export interface SelectionItem {
  /** Stable id = presentation index (0-based); `items` is stored in presentation order. */
  item: number;
  stratum: Stratum;
  variant: Variant;
  /** The exact question text shown (from the selection file; fixed wording per protocol.md §3). */
  question: string;
  /** Which LABEL is drawn on which side; duplicates swap this and nothing else. */
  side_map: Record<Side, Label>;
  /** For the 8 duplicates: the `item` of the original; null otherwise. */
  duplicate_of: number | null;
  shares: { anchor: number[]; A: number[]; B: number[] }; // 42 × u16 each, summing to 65535
}

export interface Selection {
  version: 1;
  /** sha256 of the corpus the items were drawn from — stamps a saved session so a re-selection invalidates it. */
  data_hash: string | null;
  items: SelectionItem[];
}

export interface Answer {
  item: number;
  choice: Choice;
  rt_ms: number;
}

export interface Session {
  rater: string;
  started: string; // ISO
  finished: string | null;
  /** `Selection.data_hash` when the session began; a different selection file invalidates the saved run. */
  selection: string | null;
  items: Answer[];
}

/** The export consumed by `fit_params.py` — nothing else is written. */
export interface Export {
  rater: string;
  started: string;
  finished: string | null;
  items: Answer[];
}

/** Fallback wording when an item carries no question string (protocol.md §3; the file's own text wins). */
export const QUESTION: Record<Variant, string> = {
  similar: 'Which of A or B is more similar in shape to the anchor?',
  different: 'Which of A or B is more different from the anchor?',
};

export const CHOICES: readonly Choice[] = ['A', 'B', 'tie'];
export const DESIGN = { unique: 80, duplicates: 8, strata: { visual: 32, numeric: 38, opposite: 10 } as Record<Stratum, number> };

// ---------------------------------------------------------------- selection

const STRATA: readonly Stratum[] = ['visual', 'numeric', 'opposite'];
const VARIANTS: readonly Variant[] = ['similar', 'different'];

function isU16Row(v: unknown): v is number[] {
  return Array.isArray(v) && v.length === N_DIMS && v.every((x) => Number.isInteger(x) && x >= 0 && x <= U16_TOTAL);
}

function isLabel(v: unknown): v is Label {
  return v === 'A' || v === 'B';
}

/**
 * Type-check a parsed selection file and copy out ONLY the blind fields; null when the shape is off (the page then
 * shows its empty state). Entity ids, names, years, metrics and distances present in the file are dropped here.
 */
export function validateSelection(raw: unknown): Selection | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  if (r.version !== 1 || !Array.isArray(r.items) || r.items.length === 0) return null;
  const items: SelectionItem[] = [];
  for (let i = 0; i < r.items.length; i++) {
    const it = r.items[i] as Record<string, unknown> | null;
    if (!it || typeof it !== 'object') return null;
    if (it.item !== i) return null; // ids double as positions
    if (!STRATA.includes(it.stratum as Stratum) || !VARIANTS.includes(it.variant as Variant)) return null;
    const dup = it.duplicate_of ?? null;
    if (dup !== null && !(Number.isInteger(dup) && (dup as number) >= 0 && (dup as number) < i)) return null;
    const sm = it.side_map as Record<string, unknown> | null;
    if (!sm || typeof sm !== 'object' || !isLabel(sm.left) || !isLabel(sm.right) || sm.left === sm.right) return null;
    const sh = it.shares as Record<string, unknown> | null;
    if (!sh || typeof sh !== 'object' || !isU16Row(sh.anchor) || !isU16Row(sh.A) || !isU16Row(sh.B)) return null;
    const variant = it.variant as Variant;
    const question = typeof it.question === 'string' && it.question.trim() ? it.question : QUESTION[variant];
    items.push({
      item: i,
      stratum: it.stratum as Stratum,
      variant,
      question,
      side_map: { left: sm.left, right: sm.right },
      duplicate_of: dup as number | null,
      shares: { anchor: sh.anchor, A: sh.A, B: sh.B },
    });
  }
  return { version: 1, data_hash: typeof r.data_hash === 'string' ? r.data_hash : null, items };
}

/** Design checks that do not block the run (reported on the intro screen): duplicate gap / swap and stratum counts. */
export function sequenceWarnings(sel: Selection): string[] {
  const out: string[] = [];
  const n: Record<Stratum, number> = { visual: 0, numeric: 0, opposite: 0 };
  let dups = 0;
  for (const it of sel.items) {
    if (it.duplicate_of === null) n[it.stratum]++;
    else {
      dups++;
      const orig = sel.items[it.duplicate_of];
      if (it.item - it.duplicate_of < MIN_DUP_GAP) out.push(`item ${it.item} repeats item ${it.duplicate_of} only ${it.item - it.duplicate_of} positions later (design: ≥ ${MIN_DUP_GAP})`);
      const sameRows = (['anchor', 'A', 'B'] as const).every((k) => orig.shares[k].every((v, j) => v === it.shares[k][j]));
      if (!sameRows) out.push(`item ${it.item} does not repeat item ${it.duplicate_of}'s pyramids`);
      if (orig.side_map.left !== it.side_map.right || orig.side_map.right !== it.side_map.left) out.push(`item ${it.item} does not swap item ${it.duplicate_of}'s sides`);
    }
  }
  const unique = sel.items.length - dups;
  if (unique !== DESIGN.unique || dups !== DESIGN.duplicates) out.push(`${unique} unique + ${dups} repeats (design: ${DESIGN.unique} + ${DESIGN.duplicates})`);
  const d = DESIGN.strata;
  if (n.visual !== d.visual || n.numeric !== d.numeric || n.opposite !== d.opposite) out.push(`strata ${n.visual}/${n.numeric}/${n.opposite} (design: ${d.visual}/${d.numeric}/${d.opposite})`);
  return out;
}

/** One axis for the whole sitting: the smallest fixed choice covering the largest bin anywhere in the set. */
export function fixedAxis(sel: Selection): AxisPct {
  let m = 0;
  for (const it of sel.items) for (const row of [it.shares.anchor, it.shares.A, it.shares.B]) m = Math.max(m, maxBinPct(toShares(row)));
  return fitAxis(m);
}

/** Dequantise exactly as the corpus path does: u / 65535. */
export function toShares(row: ArrayLike<number>): Float32Array {
  const out = new Float32Array(row.length);
  for (let i = 0; i < row.length; i++) out[i] = row[i] / U16_TOTAL;
  return out;
}

export function questionFor(it: SelectionItem): string {
  return it.question || QUESTION[it.variant];
}

/** The label drawn on `side` and its u16 row — the page never touches `shares.A`/`shares.B` by slot. */
export function onSide(it: SelectionItem, side: Side): { label: Label; row: number[] } {
  const label = it.side_map[side];
  return { label, row: it.shares[label] };
}

// ---------------------------------------------------------------- session

export function newSession(rater: string, sel: Selection, now: Date = new Date()): Session {
  return { rater: rater.trim() || 'anonymous', started: now.toISOString(), finished: null, selection: sel.data_hash, items: [] };
}

/** Index of the next unanswered item (= number answered); equals `sel.items.length` when the run is complete. */
export function nextIndex(s: Session): number {
  return s.items.length;
}

export function isComplete(s: Session, sel: Selection): boolean {
  return s.items.length >= sel.items.length;
}

/** Record the answer for the item at `nextIndex`; refuses out-of-order or duplicate answers. */
export function answer(s: Session, sel: Selection, item: number, choice: Choice, rt_ms: number): Session {
  if (s.finished) throw new Error('session already finished');
  if (item !== nextIndex(s)) throw new Error(`expected item ${nextIndex(s)}, got ${item}`);
  if (item >= sel.items.length) throw new Error('no items left');
  if (!CHOICES.includes(choice)) throw new Error(`bad choice ${String(choice)}`);
  const rt = Math.max(0, Math.round(rt_ms));
  return { ...s, items: [...s.items, { item, choice, rt_ms: rt }] };
}

/** Backspace: drop the last answer so that item is asked again (also re-opens a finished session). */
export function undo(s: Session): Session {
  if (s.items.length === 0) return s;
  return { ...s, finished: null, items: s.items.slice(0, -1) };
}

export function finish(s: Session, sel: Selection, now: Date = new Date()): Session {
  if (!isComplete(s, sel)) throw new Error(`cannot finish: ${s.items.length} of ${sel.items.length} answered`);
  return { ...s, finished: now.toISOString() };
}

export function progressLabel(index: number, total: number): string {
  return `item ${Math.min(index + 1, total)} of ${total}`;
}

// ---------------------------------------------------------------- persistence

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function storage(): StorageLike | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function save(s: Session, store: StorageLike | null = storage()): void {
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* private mode / quota — the run still works, it just will not survive a reload */
  }
}

export function clear(store: StorageLike | null = storage()): void {
  try {
    store?.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function isAnswer(v: unknown): v is Answer {
  if (!v || typeof v !== 'object') return false;
  const a = v as Record<string, unknown>;
  return Number.isInteger(a.item) && (a.item as number) >= 0 && CHOICES.includes(a.choice as Choice) && typeof a.rt_ms === 'number' && Number.isFinite(a.rt_ms) && a.rt_ms >= 0;
}

/**
 * Load a saved session. Returns null when absent, corrupt, or when it belongs to a different selection file
 * (data_hash differs, or answers do not line up with item positions / the item count).
 */
export function load(sel: Selection, store: StorageLike | null = storage()): Session | null {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<Session>;
    if (typeof v.rater !== 'string' || typeof v.started !== 'string' || !Array.isArray(v.items)) return null;
    if (v.finished !== null && v.finished !== undefined && typeof v.finished !== 'string') return null;
    const selection = typeof v.selection === 'string' ? v.selection : null;
    if (sel.data_hash !== selection) return null;
    if (v.items.length > sel.items.length) return null;
    for (let i = 0; i < v.items.length; i++) if (!isAnswer(v.items[i]) || v.items[i].item !== i) return null;
    return { rater: v.rater, started: v.started, finished: v.finished ?? null, selection, items: v.items as Answer[] };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------- export

export function toExport(s: Session): Export {
  return { rater: s.rater, started: s.started, finished: s.finished, items: s.items.map(({ item, choice, rt_ms }) => ({ item, choice, rt_ms })) };
}

export function exportJson(s: Session): string {
  return JSON.stringify(toExport(s), null, 2) + '\n';
}
