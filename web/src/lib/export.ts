/**
 * Client-side export + share helpers (PLAN §7 J6/J7): PNG 2× with a footer band, SVG, CSV, download, copy link,
 * Web Share. Everything is computed from the live SVG in the page — no server, no render step.
 *
 * Two halves, kept apart on purpose:
 *  · PURE (vitest, node): the CSV builders, the filename scheme, the footer text. No DOM.
 *  · DOM: `serializeSvg` / `svgToBlob` / `svgToPngBlob` (computed colours + fonts inlined so the PNG matches the
 *    theme the viewer is looking at — CSS custom properties such as `var(--male)` do not resolve inside a
 *    standalone SVG image), `download`, `copyText`, `share`. Guarded so importing this module never touches
 *    `window` at load time.
 *
 * NOTE on downloads: `<a download>` clicks and blob:/data: URLs are INERT inside some sandboxed viewers (artifact
 * iframes, some in-app webviews, print/thumbnail contexts). Nothing is thrown there — the click is swallowed — so
 * `download()` can only report that it *tried*; the ExportMenu tells the reader to open the page in a full browser
 * tab if nothing was saved.
 */

import { fmtPersonsCompact } from './format.ts';

export const SITE_NAME = 'Population Pyramid Explorer';
export const SOURCE_LINE = 'Source: UN WPP 2024';

// ------------------------------------------------------------------------------------------------- filenames

/** One filename part: NFKD → strip marks → lowercase → `[^a-z0-9]+` → '-' → trim (same rule as entity slugs). */
export function slugPart(s: string | number): string {
  return String(s)
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Safe filename: `filename(['Japan', 2026, 'pyramid'], 'png')` → 'japan-2026-pyramid.png'. Empty parts are dropped,
 * the stem is capped at 120 characters, and a stem that slugifies to nothing becomes 'export'.
 */
export function filename(parts: ReadonlyArray<string | number | null | undefined>, ext: string): string {
  const stem = parts
    .filter((p): p is string | number => p !== null && p !== undefined && String(p) !== '')
    .map(slugPart)
    .filter((p) => p.length > 0)
    .join('-')
    .slice(0, 120)
    .replace(/-+$/g, '');
  const e = ext.replace(/^\.+/, '').toLowerCase();
  return `${stem || 'export'}.${e}`;
}

/** The PNG footer band: '{Name} · {Year} · Pop {N} · Source: UN WPP 2024 · Population Pyramid Explorer'. */
export function footerText(name: string, year: number, popThousands: number): string {
  return `${name} · ${year} · Pop ${fmtPersonsCompact(popThousands)} · ${SOURCE_LINE} · ${SITE_NAME}`;
}

// ------------------------------------------------------------------------------------------------------- CSV

/** RFC 4180 cell: quotes when the value holds a comma, quote, CR/LF or leading/trailing space; null → ''. */
export function csvEscape(v: unknown): string {
  if (v === null || v === undefined) return '';
  const s = typeof v === 'number' ? fmtNum(v) : String(v);
  return /[",\r\n]|^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Numbers with at most 6 decimals and no float noise (0.1 + 0.2 → '0.3'); non-finite → ''. */
export function fmtNum(n: number): string {
  if (!Number.isFinite(n)) return '';
  return String(Number(n.toFixed(6)));
}

/** Header + rows joined with '\n' (trailing newline). UTF-8, no BOM — spreadsheets open it as-is. */
export function toCsv(header: readonly string[], rows: ReadonlyArray<ReadonlyArray<unknown>>): string {
  const lines = [header.map(csvEscape).join(',')];
  for (const r of rows) lines.push(r.map(csvEscape).join(','));
  return lines.join('\n') + '\n';
}

/** One row of a results CSV (twins, opposites, time-shift): PLAN §7 'rank, raw_rank, id, year, d, band, Δy' + name. */
export interface ResultsCsvRow {
  rank: number; // 1-based position in the list as shown
  raw_rank: number; // position in the plain (undiversified) ordering
  id: string; // ISO3 / agg-*
  name: string;
  year: number;
  d: number;
  band: string;
  dy: number; // candidate year − query year
}
export const RESULTS_CSV_HEADER = ['rank', 'raw_rank', 'id', 'name', 'year', 'd', 'band', 'dy'] as const;

export function resultsToCsv(rows: readonly ResultsCsvRow[]): string {
  return toCsv(
    RESULTS_CSV_HEADER,
    rows.map((r) => [r.rank, r.raw_rank, r.id, r.name, r.year, r.d, r.band, r.dy]),
  );
}

/** A pyramid for CSV export: 42 shares of total (male 0..20, female 21..41) + total in THOUSANDS. */
export interface PyramidCsvInput {
  id: string;
  name: string;
  year: number;
  shares: ArrayLike<number>;
  total: number; // thousands
}
export const PYRAMID_CSV_HEADER = ['pyramid', 'id', 'year', 'age_start', 'age', 'male', 'female', 'male_pct', 'female_pct'] as const;
const N_BINS = 21;

/**
 * Focal (+ optional overlay) pyramid as long-format CSV: 21 rows per pyramid — persons per sex (rounded) and the
 * share of TOTAL population per sex in percent (4 decimals, the shipped u16 resolution is ≈ 0.0015 pt).
 */
export function pyramidToCsv(focal: PyramidCsvInput, overlay?: PyramidCsvInput | null): string {
  const rows: unknown[][] = [];
  for (const p of overlay ? [focal, overlay] : [focal]) {
    const persons = p.total * 1000;
    for (let k = 0; k < N_BINS; k++) {
      const m = p.shares[k] ?? 0;
      const f = p.shares[N_BINS + k] ?? 0;
      const start = k * 5;
      rows.push([
        `${p.name} ${p.year}`,
        p.id,
        p.year,
        start,
        k === N_BINS - 1 ? `${start}+` : `${start}-${start + 4}`,
        Math.round(m * persons),
        Math.round(f * persons),
        Number((m * 100).toFixed(4)),
        Number((f * 100).toFixed(4)),
      ]);
    }
  }
  return toCsv(PYRAMID_CSV_HEADER, rows);
}

// ------------------------------------------------------------------------------------------------ SVG → blob

const SVG_NS = 'http://www.w3.org/2000/svg';
const FOOTER_H = 28; // CSS px at scale 1
const FONT_STACK = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

/** A CSS custom property as the viewer's browser resolves it on `el` (theme-aware), or the fallback. */
export function cssVar(el: Element, name: string, fallback: string): string {
  if (typeof getComputedStyle === 'undefined') return fallback;
  const v = getComputedStyle(el).getPropertyValue(name).trim();
  return v || fallback;
}

export interface SerializedSvg {
  xml: string;
  width: number; // user units == CSS px at scale 1
  height: number;
  background: string;
}

/**
 * Serialise a live SVG so it renders identically on its own: `fill`/`stroke` values written as `var(--…)` are
 * replaced by the computed colour of the corresponding live element, the font stack is pinned on the root, an
 * opaque background (`--surface`) is inserted, and width/height come from the viewBox so `<img>` sizes it.
 */
export function serializeSvg(svg: SVGSVGElement, opts: { background?: string | null } = {}): SerializedSvg {
  const vb = svg.viewBox?.baseVal;
  const width = vb && vb.width > 0 ? vb.width : svg.clientWidth || 640;
  const height = vb && vb.height > 0 ? vb.height : svg.clientHeight || 480;
  const background = opts.background === null ? 'none' : (opts.background ?? cssVar(svg, '--surface', '#ffffff'));

  const clone = svg.cloneNode(true) as SVGSVGElement;
  const orig = svg.querySelectorAll<SVGElement>('*');
  const copy = clone.querySelectorAll<SVGElement>('*');
  const paint = ['fill', 'stroke'] as const;
  for (let i = 0; i < orig.length && i < copy.length; i++) {
    const o = orig[i]!;
    const c = copy[i]!;
    let cs: CSSStyleDeclaration | null = null;
    for (const p of paint) {
      const raw = c.getAttribute(p);
      if (raw && raw.includes('var(')) {
        cs ??= getComputedStyle(o);
        c.setAttribute(p, cs.getPropertyValue(p) || 'none');
      }
    }
    // event-only or focus-only attributes have no meaning in a file
    c.removeAttribute('tabindex');
  }
  clone.setAttribute('xmlns', SVG_NS);
  clone.setAttribute('width', String(width));
  clone.setAttribute('height', String(height));
  clone.setAttribute('font-family', FONT_STACK);
  clone.removeAttribute('class');
  clone.removeAttribute('style');
  if (background !== 'none') {
    const bg = clone.ownerDocument.createElementNS(SVG_NS, 'rect');
    bg.setAttribute('width', '100%');
    bg.setAttribute('height', '100%');
    bg.setAttribute('fill', background);
    clone.insertBefore(bg, clone.firstChild);
  }
  const xml = new XMLSerializer().serializeToString(clone);
  return { xml: xml.startsWith('<?xml') ? xml : `<?xml version="1.0" encoding="UTF-8"?>\n${xml}`, width, height, background };
}

/** The SVG as a downloadable file (theme colours inlined). */
export function svgToBlob(svg: SVGSVGElement): Blob {
  return new Blob([serializeSvg(svg).xml], { type: 'image/svg+xml;charset=utf-8' });
}

export interface PngOptions {
  scale?: number; // device pixels per CSS px (2 = retina-sharp)
  footer?: string; // PLAN §7 footer band; omit for no band
}

/**
 * Rasterise the SVG to PNG at `scale`× with an optional footer band ('{Name} · {Year} · Pop {N} · Source … ').
 * Uses a data: URL (never tainted, unlike blob: in some engines) → <img> → <canvas>.
 */
export async function svgToPngBlob(svg: SVGSVGElement, { scale = 2, footer }: PngOptions = {}): Promise<Blob> {
  const ser = serializeSvg(svg);
  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error('the SVG could not be rasterised'));
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(ser.xml)}`;
  });
  const bandH = footer ? FOOTER_H : 0;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(ser.width * scale);
  canvas.height = Math.round((ser.height + bandH) * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2d context unavailable');
  ctx.fillStyle = ser.background === 'none' ? '#ffffff' : ser.background;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, ser.width * scale, ser.height * scale);
  if (footer) {
    const y0 = ser.height * scale;
    ctx.fillStyle = cssVar(svg, '--surface-2', '#f0efec');
    ctx.fillRect(0, y0, canvas.width, bandH * scale);
    ctx.fillStyle = cssVar(svg, '--border', 'rgba(0,0,0,0.1)');
    ctx.fillRect(0, y0, canvas.width, Math.max(1, Math.round(scale / 2)));
    ctx.fillStyle = cssVar(svg, '--fg-2', '#52514e');
    ctx.textBaseline = 'middle';
    const pad = 10 * scale;
    let size = 12 * scale;
    ctx.font = `${size}px ${FONT_STACK}`;
    while (size > 7 * scale && ctx.measureText(footer).width > canvas.width - 2 * pad) {
      size -= scale;
      ctx.font = `${size}px ${FONT_STACK}`;
    }
    ctx.fillText(footer, pad, y0 + (bandH * scale) / 2, canvas.width - 2 * pad);
  }
  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas.toBlob returned nothing'))), 'image/png'),
  );
}

// ----------------------------------------------------------------------------------------- download / share

/**
 * Trigger a download. Returns false when there is no document to click in. See the module note: a sandboxed
 * viewer may swallow the click without any signal, so `true` means "attempted", not "saved".
 */
export function download(blob: Blob, name: string): boolean {
  if (typeof document === 'undefined' || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') return false;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name; // App.svelte's link interceptor skips anchors with a `download` attribute
  a.rel = 'noopener';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return true;
}

/** Copy text: async clipboard first, hidden-textarea + execCommand fallback. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the textarea path */
  }
  if (typeof document === 'undefined') return false;
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  ta.style.pointerEvents = 'none';
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  ta.remove();
  return ok;
}

/** Whether the Web Share API is available (secure context, supporting browser). */
export function canShare(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function';
}

export type ShareOutcome = 'shared' | 'cancelled' | 'unavailable' | 'failed';

/** navigator.share with the three outcomes a UI cares about (a user dismissing the sheet is not an error). */
export async function share(data: { url: string; title?: string; text?: string }): Promise<ShareOutcome> {
  if (!canShare()) return 'unavailable';
  try {
    await navigator.share(data);
    return 'shared';
  } catch (e) {
    return e instanceof DOMException && e.name === 'AbortError' ? 'cancelled' : 'failed';
  }
}
