<script lang="ts">
  // ⤓ export menu (PLAN §7 J7): PNG 2× (footer band) · SVG · CSV, attached to any chart through a target-element
  // getter so the same component sits on the pyramid, the compare chart and the results sections (CSV only).
  // Real <button>s, role=menu with roving arrow-key focus, Escape closes, click-outside closes, an aria-live
  // status line reports the outcome. Downloads run client-side from the live SVG (lib/export.ts).
  import { tick } from 'svelte';
  import { download, filename, svgToBlob, svgToPngBlob } from '../export.ts';

  export interface CsvItem {
    label: string; // menu text, e.g. 'Most similar (CSV)'
    suffix: string; // filename suffix, e.g. 'similar'
    text: () => string | null; // CSV text, null when nothing to export yet
  }

  interface Props {
    /** Filename stem parts (slugified + joined): ['Japan', 2026, 'pyramid'] → japan-2026-pyramid.png */
    basename: ReadonlyArray<string | number | null | undefined>;
    /** The live chart to export (resolved at click time); omit for a CSV-only menu. */
    svg?: (() => SVGSVGElement | null | undefined) | null;
    /** PNG footer band text (PLAN §7: '{Name} · {Year} · Pop {N} · Source: UN WPP 2024 · Population Pyramid Explorer'). */
    footer?: string;
    /** CSV entries, in menu order. */
    csv?: readonly CsvItem[];
    label?: string;
    title?: string;
  }
  let { basename, svg = null, footer, csv = [], label = '⤓ Export', title = 'Download this as PNG, SVG or CSV' }: Props = $props();

  let open = $state(false);
  let busy = $state(false);
  let status = $state<string | null>(null);
  let root = $state<HTMLDivElement | null>(null);
  let button = $state<HTMLButtonElement | null>(null);
  let menu = $state<HTMLDivElement | null>(null);
  let statusTimer: ReturnType<typeof setTimeout> | null = null;

  type Item = { key: string; label: string; run: () => Promise<void> | void; disabled: boolean };
  const items = $derived.by<Item[]>(() => {
    const out: Item[] = [];
    if (svg) {
      out.push({ key: 'png', label: 'PNG 2×', disabled: false, run: () => savePng() });
      out.push({ key: 'svg', label: 'SVG', disabled: false, run: () => saveSvg() });
    }
    for (const c of csv) out.push({ key: `csv:${c.suffix}`, label: c.label, disabled: false, run: () => saveCsv(c) });
    return out;
  });

  function say(msg: string, ms = 4000) {
    status = msg;
    if (statusTimer) clearTimeout(statusTimer);
    statusTimer = setTimeout(() => (status = null), ms);
  }
  function saved(name: string) {
    say(`Saved ${name}. If nothing arrived, this viewer blocks downloads — open the page in a browser tab.`, 6000);
  }
  function chart(): SVGSVGElement {
    const el = svg?.();
    if (!el) throw new Error('the chart is not on screen yet');
    return el;
  }
  async function savePng() {
    const name = filename([...basename], 'png');
    const blob = await svgToPngBlob(chart(), { scale: 2, footer });
    download(blob, name);
    saved(name);
  }
  function saveSvg() {
    const name = filename([...basename], 'svg');
    download(svgToBlob(chart()), name);
    saved(name);
  }
  function saveCsv(c: CsvItem) {
    const text = c.text();
    if (!text) throw new Error('nothing to export yet');
    const name = filename([...basename, c.suffix], 'csv');
    download(new Blob([text], { type: 'text/csv;charset=utf-8' }), name);
    saved(name);
  }
  async function run(it: Item) {
    open = false;
    busy = true;
    try {
      await it.run();
    } catch (e) {
      say(`Export failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      busy = false;
      button?.focus();
    }
  }

  async function toggle(focusIndex: number | null = 0) {
    open = !open;
    if (open && focusIndex !== null) {
      await tick();
      focusItem(focusIndex);
    }
  }
  function focusItem(i: number) {
    const els = menu?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]');
    if (!els || els.length === 0) return;
    const n = els.length;
    els[((i % n) + n) % n]?.focus();
  }
  function onButtonKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) open = true;
      void tick().then(() => focusItem(e.key === 'ArrowDown' ? 0 : -1));
    }
  }
  function onMenuKey(e: KeyboardEvent) {
    const els = Array.from(menu?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? []);
    const i = els.findIndex((el) => el === document.activeElement);
    switch (e.key) {
      case 'Escape':
        e.preventDefault();
        open = false;
        button?.focus();
        break;
      case 'ArrowDown':
        e.preventDefault();
        focusItem(i + 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        focusItem(i - 1);
        break;
      case 'Home':
        e.preventDefault();
        focusItem(0);
        break;
      case 'End':
        e.preventDefault();
        focusItem(-1);
        break;
      case 'Tab':
        open = false; // let focus move on naturally
        break;
    }
  }
  function onDocPointer(e: PointerEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
  $effect(() => {
    if (!open) return;
    document.addEventListener('pointerdown', onDocPointer, true);
    return () => document.removeEventListener('pointerdown', onDocPointer, true);
  });
</script>

<div class="relative inline-flex" bind:this={root}>
  <button
    type="button"
    class="btn gap-1"
    bind:this={button}
    aria-haspopup="menu"
    aria-expanded={open}
    aria-controls="{'export-menu-' + items.map((i) => i.key).join('-')}"
    disabled={busy || items.length === 0}
    {title}
    onclick={() => toggle(null)}
    onkeydown={onButtonKey}
  >
    {#if busy}<span aria-hidden="true">…</span><span class="sr-only">exporting</span>{:else}{label}{/if}
  </button>
  {#if open}
    <div
      class="absolute right-0 top-full z-20 mt-1 min-w-36 rounded-md border border-border bg-surface p-1 shadow-lg"
      role="menu"
      tabindex="-1"
      id="{'export-menu-' + items.map((i) => i.key).join('-')}"
      aria-label="Export"
      bind:this={menu}
      onkeydown={onMenuKey}
    >
      {#each items as it (it.key)}
        <button
          type="button"
          role="menuitem"
          class="block w-full rounded px-2.5 py-1.5 text-left text-sm text-fg-2 hover:bg-surface-2 hover:text-fg focus-visible:bg-surface-2 disabled:opacity-40"
          disabled={it.disabled}
          onclick={() => run(it)}
        >
          {it.label}
        </button>
      {/each}
    </div>
  {/if}
</div>
<span class="sr-only" role="status" aria-live="polite">{status ?? ''}</span>
{#if status}
  <span class="ml-2 max-w-64 text-[11px] text-muted" aria-hidden="true">{status}</span>
{/if}
