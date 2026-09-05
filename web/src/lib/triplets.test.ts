import { describe, expect, it } from 'vitest';
import { N_DIMS, U16_TOTAL } from './types.ts';
import {
  answer,
  clear,
  exportJson,
  finish,
  fixedAxis,
  isComplete,
  load,
  MIN_DUP_GAP,
  newSession,
  nextIndex,
  progressLabel,
  QUESTION,
  questionFor,
  save,
  sequenceWarnings,
  STORAGE_KEY,
  toExport,
  toShares,
  undo,
  validateSelection,
  type Selection,
  type SelectionItem,
  type StorageLike,
  type Stratum,
  onSide,
} from './triplets.ts';

// ---- fixture: a tiny selection with the real schema (Z1's file has 88 items; sequencing does not care about n)

/** A u16 row that sums to exactly 65535 with a single bulge at bin `peak` (male side) — deterministic per seed. */
function row(seed: number, peak = 3): number[] {
  const w = Array.from({ length: N_DIMS }, (_, i) => 1 + ((i * 7 + seed * 13) % 11) + (i % 21 === peak ? 40 : 0));
  const sum = w.reduce((a, b) => a + b, 0);
  const out = w.map((x) => Math.floor((x / sum) * U16_TOTAL));
  let deficit = U16_TOTAL - out.reduce((a, b) => a + b, 0);
  for (let i = 0; deficit > 0; i = (i + 1) % N_DIMS, deficit--) out[i]++;
  return out;
}

function item(i: number, stratum: Stratum, dup_of: number | null = null): SelectionItem {
  const src = dup_of ?? i;
  const variant = stratum === 'opposite' ? 'different' : 'similar';
  const left = src % 2 === 0 ? 'A' : 'B';
  const side_map = dup_of === null ? { left, right: left === 'A' ? 'B' : 'A' } : { left: left === 'A' ? 'B' : 'A', right: left };
  return { item: i, stratum, variant, question: QUESTION[variant], side_map: side_map as SelectionItem['side_map'], duplicate_of: dup_of, shares: { anchor: row(src * 3), A: row(src * 3 + 1), B: row(src * 3 + 2) } };
}

/** What the selector actually writes: the blind fields plus the key that must never reach the page. */
function rawItem(it: SelectionItem): Record<string, unknown> {
  return { ...it, anchor: { id: 'JPN', year: 2024, name: 'Japan' }, A: { id: 'ITA', year: 2020, name: 'Italy', metric: 'blend' }, B: { id: 'DEU', year: 2024, name: 'Germany', metric: 'visual:x' }, pair: ['blend', 'visual:x'], distances: { blend: { A: 0.1, B: 0.2 } }, components: {} };
}

function fixture(n = 6): Selection {
  const items: SelectionItem[] = [];
  for (let i = 0; i < n - 1; i++) items.push(item(i, i % 3 === 0 ? 'visual' : i % 3 === 1 ? 'numeric' : 'opposite'));
  items.push(item(n - 1, items[0].stratum, 0)); // one swapped-side duplicate of item 0 at the end
  return { version: 1, data_hash: 'e2bf14d5', items };
}

function rawFixture(n = 6): Record<string, unknown> {
  const f = fixture(n);
  return { ...f, seed: 0, n_items: n, items: f.items.map(rawItem) };
}

function mem(): StorageLike & { m: Map<string, string> } {
  const m = new Map<string, string>();
  return { m, getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) };
}

describe('selection validation', () => {
  it('accepts the selector output, keeps only the blind fields, rejects broken shapes', () => {
    const sel = fixture();
    const raw = rawFixture();
    expect(validateSelection(JSON.parse(JSON.stringify(raw)))).toEqual(sel);
    expect(validateSelection(null)).toBeNull();
    expect(validateSelection({})).toBeNull();
    expect(validateSelection({ ...raw, version: 2 })).toBeNull();
    expect(validateSelection({ version: 1, items: [] })).toBeNull();
    const items = raw.items as Record<string, unknown>[];
    const it0 = items[0];
    const sh = it0.shares as SelectionItem['shares'];
    // ids must equal positions
    expect(validateSelection({ version: 1, items: [items[1]] })).toBeNull();
    // 42 ints ≤ 65535
    expect(validateSelection({ version: 1, items: [{ ...it0, shares: { ...sh, A: sh.A.slice(1) } }] })).toBeNull();
    expect(validateSelection({ version: 1, items: [{ ...it0, shares: { ...sh, B: [...sh.B.slice(1), 70000] } }] })).toBeNull();
    expect(validateSelection({ version: 1, items: [{ ...it0, shares: { ...sh, anchor: [...sh.anchor.slice(1), 1.5] } }] })).toBeNull();
    // duplicate_of must point backwards; side map must name both labels
    expect(validateSelection({ version: 1, items: [{ ...it0, duplicate_of: 0 }] })).toBeNull();
    expect(validateSelection({ version: 1, items: [{ ...it0, side_map: { left: 'A', right: 'A' } }] })).toBeNull();
    expect(validateSelection({ version: 1, items: [{ ...it0, stratum: 'blend_vs_visual' }] })).toBeNull();
    expect(validateSelection({ version: 1, items: [{ ...it0, variant: 'looks' }] })).toBeNull();
    // missing question falls back to the fixed wording; data_hash optional
    const v = validateSelection({ version: 1, items: [{ ...it0, question: undefined }] })!;
    expect(v.items[0].question).toBe(QUESTION.similar);
    expect(v.data_hash).toBeNull();
  });

  it('never carries names, years, metrics or distances — only the blind fields', () => {
    const v = validateSelection(rawFixture())!;
    for (const it of v.items) expect(Object.keys(it).sort()).toEqual(['duplicate_of', 'item', 'question', 'shares', 'side_map', 'stratum', 'variant']);
    expect(JSON.stringify(v)).not.toMatch(/Japan|JPN|2024|blend|distances/);
  });

  it('places labels by the side map; a duplicate shows the same rows on swapped sides', () => {
    const sel = fixture();
    const orig = sel.items[0];
    const dup = sel.items[5];
    expect(dup.duplicate_of).toBe(0);
    expect(onSide(orig, 'left')).toEqual({ label: 'A', row: orig.shares.A });
    expect(onSide(orig, 'right')).toEqual({ label: 'B', row: orig.shares.B });
    expect(onSide(dup, 'left')).toEqual({ label: 'B', row: orig.shares.B });
    expect(onSide(dup, 'right')).toEqual({ label: 'A', row: orig.shares.A });
  });

  it('warns about design deviations without blocking', () => {
    const w = sequenceWarnings(fixture());
    expect(w.some((s) => s.includes(`design: ≥ ${MIN_DUP_GAP}`))).toBe(true); // gap 5 in the fixture
    expect(w.some((s) => s.includes('design: 80 + 8'))).toBe(true);
    const bad = fixture();
    bad.items[5] = { ...bad.items[5], side_map: { ...bad.items[0].side_map } }; // sides not swapped
    expect(sequenceWarnings(bad).some((s) => s.includes('swap'))).toBe(true);
    const bad2 = fixture();
    bad2.items[5] = { ...bad2.items[5], shares: { ...bad2.items[5].shares, A: row(99) } }; // different pyramids
    expect(sequenceWarnings(bad2).some((s) => s.includes('pyramids'))).toBe(true);
  });

  it('a conforming 88-item design produces no warnings', () => {
    const items: SelectionItem[] = [];
    const strata: Stratum[] = [...Array<Stratum>(10).fill('opposite'), ...Array<Stratum>(32).fill('visual'), ...Array<Stratum>(38).fill('numeric')];
    for (let i = 0; i < 80; i++) items.push(item(i, strata[i]));
    const dupSrc = [0, 10, 11, 12, 13, 42, 43, 44]; // 1 opposite, 4 visual, 3 numeric — all ≥ 36 positions before the repeats
    for (let j = 0; j < 8; j++) items.push(item(80 + j, strata[dupSrc[j]], dupSrc[j]));
    expect(sequenceWarnings({ version: 1, data_hash: null, items })).toEqual([]);
  });

  it('question text follows the item kind; fixed wording', () => {
    const sel = fixture();
    expect(questionFor(sel.items[1])).toBe('Which of A or B is more similar in shape to the anchor?');
    expect(questionFor(sel.items[2])).toBe(QUESTION.different);
    expect(QUESTION.different).toMatch(/more different/);
    expect(questionFor({ ...sel.items[1], question: '' })).toBe(QUESTION.similar);
  });

  it('fixedAxis is one of the fixed choices and covers every bar; toShares dequantises to a row summing to 1', () => {
    const sel = fixture();
    const ax = fixedAxis(sel);
    expect([10, 12, 14, 17]).toContain(ax);
    for (const it of sel.items) for (const r of [it.shares.anchor, it.shares.A, it.shares.B]) for (const v of r) expect((v / U16_TOTAL) * 100).toBeLessThanOrEqual(ax);
    const s = toShares(sel.items[0].shares.anchor);
    expect(s).toBeInstanceOf(Float32Array);
    expect(s.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 5);
  });
});

describe('sequencing', () => {
  const sel = fixture();

  it('walks items in order, refuses skips and repeats, undoes one at a time', () => {
    let s = newSession('eli', sel, new Date('2026-09-04T10:00:00Z'));
    expect(s.started).toBe('2026-09-04T10:00:00.000Z');
    expect(s.selection).toBe(sel.data_hash);
    expect(nextIndex(s)).toBe(0);
    expect(progressLabel(nextIndex(s), sel.items.length)).toBe('item 1 of 6');
    s = answer(s, sel, 0, 'A', 1234.6);
    expect(s.items).toEqual([{ item: 0, choice: 'A', rt_ms: 1235 }]);
    expect(() => answer(s, sel, 0, 'B', 1)).toThrow(/expected item 1/);
    expect(() => answer(s, sel, 2, 'B', 1)).toThrow(/expected item 1/);
    expect(() => answer(s, sel, 1, 'C' as never, 1)).toThrow(/bad choice/);
    s = answer(s, sel, 1, 'tie', -5);
    expect(s.items[1].rt_ms).toBe(0);
    expect(progressLabel(nextIndex(s), sel.items.length)).toBe('item 3 of 6');
    s = undo(s);
    expect(nextIndex(s)).toBe(1);
    s = undo(undo(s));
    expect(s.items).toEqual([]);
    expect(undo(s)).toBe(s);
  });

  it('finishes only when complete; undo re-opens a finished session', () => {
    let s = newSession('', sel);
    expect(s.rater).toBe('anonymous');
    expect(() => finish(s, sel)).toThrow(/cannot finish/);
    for (let i = 0; i < sel.items.length; i++) s = answer(s, sel, i, i % 2 ? 'B' : 'A', 900 + i);
    expect(isComplete(s, sel)).toBe(true);
    expect(() => answer(s, sel, sel.items.length, 'A', 1)).toThrow(/no items left/);
    s = finish(s, sel, new Date('2026-09-04T11:15:00Z'));
    expect(s.finished).toBe('2026-09-04T11:15:00.000Z');
    expect(() => answer(s, sel, 6, 'A', 1)).toThrow(/finished/);
    const back = undo(s);
    expect(back.finished).toBeNull();
    expect(nextIndex(back)).toBe(sel.items.length - 1);
    expect(progressLabel(sel.items.length, sel.items.length)).toBe('item 6 of 6');
  });
});

describe('persistence', () => {
  const sel = fixture();

  it('round-trips under the versioned key and resumes at the right index', () => {
    const store = mem();
    let s = newSession('eli', sel);
    s = answer(s, sel, 0, 'B', 800);
    s = answer(s, sel, 1, 'tie', 1200);
    save(s, store);
    expect(store.m.has(STORAGE_KEY)).toBe(true);
    expect(STORAGE_KEY).toBe('ppe:triplets:v1');
    const back = load(sel, store);
    expect(back).toEqual(s);
    expect(nextIndex(back!)).toBe(2);
    clear(store);
    expect(load(sel, store)).toBeNull();
  });

  it('rejects corrupt, foreign-selection, or misaligned saves', () => {
    const store = mem();
    expect(load(sel, store)).toBeNull();
    store.m.set(STORAGE_KEY, '{nope');
    expect(load(sel, store)).toBeNull();
    const s = answer(newSession('eli', sel), sel, 0, 'A', 1);
    store.m.set(STORAGE_KEY, JSON.stringify({ ...s, selection: 'some-other-build' }));
    expect(load(sel, store)).toBeNull();
    store.m.set(STORAGE_KEY, JSON.stringify({ ...s, items: [{ item: 3, choice: 'A', rt_ms: 1 }] }));
    expect(load(sel, store)).toBeNull();
    store.m.set(STORAGE_KEY, JSON.stringify({ ...s, items: [{ item: 0, choice: 'maybe', rt_ms: 1 }] }));
    expect(load(sel, store)).toBeNull();
    store.m.set(STORAGE_KEY, JSON.stringify({ ...s, items: Array.from({ length: 7 }, (_, i) => ({ item: i, choice: 'A', rt_ms: 1 })) }));
    expect(load(sel, store)).toBeNull();
    store.m.set(STORAGE_KEY, JSON.stringify({ ...s, finished: 42 }));
    expect(load(sel, store)).toBeNull();
  });

  it('swallows storage errors and a missing store', () => {
    const boom: StorageLike = {
      getItem: () => {
        throw new Error('denied');
      },
      setItem: () => {
        throw new Error('denied');
      },
      removeItem: () => {
        throw new Error('denied');
      },
    };
    const s = newSession('eli', sel);
    expect(() => save(s, boom)).not.toThrow();
    expect(() => clear(boom)).not.toThrow();
    expect(load(sel, boom)).toBeNull();
    expect(load(sel, null)).toBeNull();
    expect(() => save(s, null)).not.toThrow();
  });
});

describe('export', () => {
  it('matches the fit_params input shape exactly: {rater, started, finished, items:[{item, choice, rt_ms}]}', () => {
    const sel = fixture();
    let s = newSession('eli', sel, new Date('2026-09-04T10:00:00Z'));
    for (let i = 0; i < sel.items.length; i++) s = answer(s, sel, i, (['A', 'B', 'tie'] as const)[i % 3], 1000 + i);
    s = finish(s, sel, new Date('2026-09-04T11:00:00Z'));
    const e = toExport(s);
    expect(Object.keys(e)).toEqual(['rater', 'started', 'finished', 'items']);
    expect(e).not.toHaveProperty('selection');
    expect(e.items).toHaveLength(6);
    for (const a of e.items) expect(Object.keys(a)).toEqual(['item', 'choice', 'rt_ms']);
    expect(e.items[2]).toEqual({ item: 2, choice: 'tie', rt_ms: 1002 });
    const text = exportJson(s);
    expect(text.endsWith('\n')).toBe(true);
    expect(JSON.parse(text)).toEqual(e);
    // an unfinished export is still well-formed (finished: null)
    expect(toExport(undo(s)).finished).toBeNull();
  });
});

describe('real selection file (when the selector has run)', () => {
  const found = import.meta.glob<{ default: unknown }>('../data/triplets_selection.json', { eager: true });
  const raw = Object.values(found)[0]?.default;
  it.skipIf(raw === undefined)('validates, matches the pre-registered design, and fits one fixed axis', () => {
    const sel = validateSelection(raw);
    expect(sel).not.toBeNull();
    expect(sel!.items).toHaveLength(88);
    expect(sequenceWarnings(sel!)).toEqual([]);
    expect([10, 12, 14, 17]).toContain(fixedAxis(sel!));
    expect(sel!.data_hash).toMatch(/^[0-9a-f]{64}$/);
    for (const it of sel!.items) expect(it.question).toBe(QUESTION[it.variant]);
  });
});
