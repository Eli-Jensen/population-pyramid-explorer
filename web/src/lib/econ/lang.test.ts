// Language lint (PLAN §7 language rules): every string literal under web/src (+ the two JSON banks and evidence.json)
// is scanned with the deny list of evals/econ/ui_sentences.yaml; lang.ts renders only granted sentence ids.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ALLOWED_IDS, DENY_LIST, denyHit, fill, formatValue, FOOTER_DISCLAIMER, investability, isAllowed, LENS_BANNER, render, rendered, sentences, vsVt } from './lang.ts';

const SRC = join(__dirname, '..', '..'); // web/src
const DATA = join(SRC, 'data');

/** Test files are fixtures (they name the forbidden words on purpose); this file plants a violation below. */
const ALLOW = [/\.test\.ts$/];

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(svelte|ts)$/.test(name)) out.push(p);
  }
  return out;
}

/**
 * String literals ('…', "…", `…`) of a TS / script source, found by a small tokenizer that skips // and /* comments
 * (a quote inside a comment must not open a bogus literal); template literals are scanned whole.
 */
export function stringLiterals(src: string): string[] {
  const out: string[] = [];
  let i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i]!;
    const d = src[i + 1];
    if (c === '/' && d === '/') {
      const e = src.indexOf('\n', i);
      i = e < 0 ? n : e + 1;
      continue;
    }
    if (c === '/' && d === '*') {
      const e = src.indexOf('*/', i + 2);
      i = e < 0 ? n : e + 2;
      continue;
    }
    if (c === '/' && /[(,=:[!&|?{};\n]\s*$/.test(src.slice(Math.max(0, i - 40), i))) {
      // a regex literal: skip to its unescaped closing slash (brackets may hold quotes and slashes)
      let j = i + 1;
      let cls = false;
      for (; j < n && src[j] !== '\n'; j++) {
        const ch = src[j]!;
        if (ch === '\\') {
          j++;
          continue;
        }
        if (ch === '[') cls = true;
        else if (ch === ']') cls = false;
        else if (ch === '/' && !cls) break;
      }
      i = j + 1;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      let j = i + 1;
      let buf = '';
      while (j < n && src[j] !== c) {
        if (src[j] === '\\') {
          buf += src[j]! + (src[j + 1] ?? '');
          j += 2;
          continue;
        }
        if (c !== '`' && src[j] === '\n') break; // an unterminated single-line literal (a regex or an apostrophe): stop
        buf += src[j]!;
        j++;
      }
      if (src[j] === c) {
        out.push(buf);
        i = j + 1;
      } else i = j; // not a literal after all
      continue;
    }
    i++;
  }
  return out;
}

/** Replace every balanced `{…}` expression block of Svelte markup with the string literals it contains. */
export function foldExpressions(markup: string): string {
  let out = '';
  let i = 0;
  while (i < markup.length) {
    if (markup[i] !== '{') {
      out += markup[i];
      i++;
      continue;
    }
    let depth = 0;
    let j = i;
    let quote: string | null = null;
    for (; j < markup.length; j++) {
      const ch = markup[j]!;
      if (quote) {
        if (ch === '\\') j++;
        else if (ch === quote) quote = null;
        continue;
      }
      if (ch === "'" || ch === '"' || ch === '`') quote = ch;
      else if (ch === '{') depth++;
      else if (ch === '}') {
        depth--;
        if (depth === 0) break;
      }
    }
    out += ' ' + stringLiterals(markup.slice(i + 1, j)).join(' ') + ' ';
    i = j + 1;
  }
  return out;
}

/** Text a .svelte file can put on screen: script string literals + the markup (attributes and text nodes; expressions folded to their literals). */
export function svelteText(src: string): string[] {
  const scripts = [...src.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]!);
  let markup = src.replace(/<script[^>]*>[\s\S]*?<\/script>/g, '').replace(/<style[^>]*>[\s\S]*?<\/style>/g, '');
  markup = markup.replace(/<!--[\s\S]*?-->/g, '');
  return [...scripts.flatMap(stringLiterals), foldExpressions(markup)];
}

function scan(text: string, where: string, hits: string[]): void {
  const h = denyHit(text);
  if (h) hits.push(`${where}: /${h.pattern}/ matched "${h.match}" in ${JSON.stringify(text.slice(0, 120))}`);
}

function scanTree(): string[] {
  const hits: string[] = [];
  for (const file of walk(SRC)) {
    const rel = relative(SRC, file);
    if (ALLOW.some((re) => re.test(rel))) continue;
    const src = readFileSync(file, 'utf8');
    const texts = file.endsWith('.svelte') ? svelteText(src) : stringLiterals(src);
    for (const t of texts) scan(t, rel, hits);
  }
  for (const json of ['evidence.json', 'ui_sentences.json', 'econ_decision.json']) {
    const walkJson = (v: unknown, path: string) => {
      if (typeof v === 'string') scan(v, `data/${json}#${path}`, hits);
      else if (Array.isArray(v)) v.forEach((x, i) => walkJson(x, `${path}[${i}]`));
      else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) if (k !== 'deny_list') walkJson(x, `${path}.${k}`);
    };
    walkJson(JSON.parse(readFileSync(join(DATA, json), 'utf8')), '');
  }
  return hits;
}

describe('deny-list scan over web/src', () => {
  it('the deny list is the yaml one (9 patterns) and matches the canonical bad phrases', () => {
    expect(DENY_LIST.length).toBe(9);
    for (const bad of ['You should invest here', 'expected to outperform', 'a top 10 pick', 'an opportunity', 'outsized gains', 'undervalued market', 'it will rise', 'buy INDA', 'seeking alpha']) {
      expect(denyHit(bad), bad).not.toBeNull();
    }
    for (const ok of ['GDP per capita 9.4× in 30 years', 'NGE total return 2015–2025: -7.1 %/yr · VT over the same window: +11.8 %/yr.', 'top-quartile rate', 'the working-age share']) {
      expect(denyHit(ok), ok).toBeNull();
    }
  });

  it('no string literal under web/src, nor evidence.json / ui_sentences.json / econ_decision.json, hits the deny list', () => {
    const hits = scanTree();
    expect(hits, hits.join('\n')).toEqual([]);
  });

  it('negative control: a planted violation IS caught by the same scanner', () => {
    const planted = `<script lang="ts">const label = 'India looks undervalued';</script><p>You should invest now.</p>`;
    const hits: string[] = [];
    for (const t of svelteText(planted)) scan(t, 'planted.svelte', hits);
    expect(hits.length).toBe(2);
    expect(hits[0]).toMatch(/undervalued/);
    expect(hits[1]).toMatch(/should\\s\+invest/);
    const ts = `export const x = "an outsized opportunity"; // buy`;
    const tsHits: string[] = [];
    for (const t of stringLiterals(ts)) scan(t, 'planted.ts', tsHits);
    expect(tsHits.length).toBe(1);
    // a quote inside a comment does not open a literal; an expression's identifier is not text, its literal is
    expect(stringLiterals(`// don't\nconst a = 'x'; /* it's */ const b = "y";`)).toEqual(['x', 'y']);
    expect(stringLiterals(`const q = /[",]|^"/.test(s) ? \`"\${s}"\` : 'z';`)).toEqual(['"${s}"', 'z']);
    expect(foldExpressions(`{#each t.picks as pk}<b title={ok ? 'sell now' : 'b'}>{pk.name}</b>{/each}`)).not.toMatch(/picks/);
    expect(foldExpressions(`<b title={ok ? 'sell now' : 'b'}>x</b>`)).toMatch(/sell now/);
  });
});

describe('lang.ts renders only granted sentence ids', () => {
  it('the decision granted L0 only', () => {
    expect(ALLOWED_IDS).toEqual(['L0.disconnect', 'L0.investability', 'L0.null', 'L0.vs_vt', 'L0.what_happened']);
    expect(isAllowed('L1.growth_association')).toBe(false);
    expect(isAllowed('L2.returns_signal')).toBe(false);
    expect(sentences.sentences['L1.growth_association']).toBeDefined(); // the template exists but is never rendered
  });

  it('refuses a non-allowed id (throws in dev, which vitest is)', () => {
    expect(() => render('L1.growth_association', { mu: 1 })).toThrow(/not in decision\.json/);
    expect(() => render('L2.returns_signal', {})).toThrow(/not in decision\.json/);
    expect(() => render('L9.made_up', {})).toThrow();
    expect(rendered('L1.growth_association')).toEqual([]);
  });

  it('fills python-style placeholders exactly like decide.py did', () => {
    const s = render('L0.vs_vt', { ticker: 'NGE', y1: 2015, y2: 2025, r: -7.0801, r_vt: 11.76 }, { note: 'vt' });
    expect(s).toBe('NGE total return 2015–2025: -7.1 %/yr · VT over the same window: +11.8 %/yr.');
    expect(rendered('L0.vs_vt')).toContain(s!);
    expect(vsVt({ ticker: 'EWY', y1: 2000, y2: 2010, r: 16.8, r_vt: 2.7 }, 'vt_proxy')).toMatch(/\(VT proxy before 2008-06-24/);
    expect(vsVt({ ticker: 'EWJ', y1: 1996, y2: 2006, r: 1, r_vt: null }, 'none')).toMatch(/n\/a %\/yr \(VT did not exist for this window\)/);
    expect(investability('none_at_T', { T: 2000 })).toBe('No US-listed single-country fund existed in 2000.');
    expect(investability('none_ever', {})).toBe('No US-listed single-country fund exists for this country.');
    expect(investability('liquidated', { ticker: 'NGE', delisted: '2024-03-25' })).toBe('NGE was liquidated on 2024-03-25 (issuer notice).');
    expect(investability('live', { ticker: 'INDA', issuer: 'iShares', inception: '2012-02-02' })).toBe('INDA (iShares) has existed since 2012-02-02.');
    const w = render('L0.what_happened', { k: 10, T: 1990, h: 10, mu_g: -0.5, median_g: 1.6, n_candidates: 148, n_eff: 10, hit_rate: 0.4 });
    expect(w).toBe(rendered('L0.what_happened')[0]);
    expect(render('L0.null', { k: 10, B: 5000, share_n1: 0.65, p_n1: 0.65, share_n2: 0.9834, p_n2: 0.9834 })).toBe(rendered('L0.null')[0]);
    expect(formatValue(9.386, '.1f')).toBe('9.4');
    expect(formatValue(88.63, '.0f')).toBe('89');
    expect(formatValue(0.4, '.0%')).toBe('40%');
    expect(formatValue(null, '+.1f')).toBe('n/a');
    expect(fill('{a} and {b:.2f}', { a: 'x', b: 1 })).toBe('x and 1.00');
  });

  it('the fixed UI texts pass the deny list', () => {
    expect(denyHit(LENS_BANNER)).toBeNull();
    expect(denyHit(FOOTER_DISCLAIMER)).toBeNull();
    for (const [id, spec] of Object.entries(sentences.sentences)) {
      for (const t of [spec.template, ...Object.values(spec.variants ?? {}), ...Object.values(spec.benchmark_note_values ?? {})]) if (t) expect(denyHit(t), id).toBeNull();
    }
  });
});
