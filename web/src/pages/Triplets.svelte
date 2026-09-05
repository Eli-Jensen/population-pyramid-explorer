<script lang="ts">
  // /eval/triplets — dev-only human-triplet collector (PLAN §4.6 item 8, protocol.md §3). Not linked from any menu;
  // Z4 mounts it in App.svelte. Blind by construction: the page reads web/src/data/triplets_selection.json (three
  // text-free u16 rows per item, no ids of any kind) and shows the anchor above A and B at one fixed scale. It records
  // the chosen side and the response time, autosaves after every answer (localStorage, resumes on reload) and ends
  // with a JSON export for evals/triplets.json → `make triplets-fit`. Self-agreement is NOT computed here — that would
  // tell the rater which items are repeats.
  import { onMount, tick } from 'svelte';
  import TripletPyramid from '../lib/components/TripletPyramid.svelte';
  import {
    answer,
    clear,
    exportJson,
    EXPORT_FILENAME,
    finish,
    fixedAxis,
    isComplete,
    load,
    newSession,
    nextIndex,
    onSide,
    progressLabel,
    QUESTION,
    questionFor,
    save,
    sequenceWarnings,
    undo,
    validateSelection,
    type Choice,
    type Selection,
    type Session,
  } from '../lib/triplets.ts';

  // The selection file is written by the Python selector and may be absent in a fresh checkout: a glob import
  // resolves to {} instead of failing the build, and the page then renders its empty state.
  const found = import.meta.glob<{ default: unknown }>('../data/triplets_selection.json', { eager: true });
  const selection: Selection | null = validateSelection(Object.values(found)[0]?.default);
  const warnings = selection ? sequenceWarnings(selection) : [];
  const axisPct = selection ? fixedAxis(selection) : 10;
  const total = selection?.items.length ?? 0;

  type Phase = 'empty' | 'intro' | 'run' | 'done';
  let phase = $state<Phase>(selection ? 'intro' : 'empty');
  let session = $state<Session | null>(null);
  let rater = $state('eli');
  let pending = $state<Choice | null>(null);
  let shownAt = 0;
  let copied = $state<'idle' | 'ok' | 'fail'>('idle');
  let stage: HTMLElement | undefined = $state();
  let doneHeading: HTMLElement | undefined = $state();
  let resumable = $state(false);

  const index = $derived(session ? nextIndex(session) : 0);
  const current = $derived(selection && session && index < total ? selection.items[index] : null);
  const progress = $derived(progressLabel(index, total));
  // Left/right placement follows the item's side map (duplicates swap it); buttons sit under their own pyramid.
  const left = $derived(current ? onSide(current, 'left') : null);
  const right = $derived(current ? onSide(current, 'right') : null);
  const PYR = 232;

  onMount(() => {
    if (!selection) return;
    const saved = load(selection);
    if (!saved) return;
    session = saved;
    if (saved.finished) phase = 'done';
    else if (saved.items.length > 0) {
      // "Resume on reload": straight back into the run, no intro.
      resumable = true;
      phase = 'run';
      void showItem();
    }
  });

  async function showItem() {
    pending = null;
    copied = 'idle';
    await tick();
    stage?.focus({ preventScroll: true });
    shownAt = performance.now();
  }

  function start(fresh: boolean) {
    if (!selection) return;
    if (fresh || !session) {
      clear();
      session = newSession(rater, selection);
      save(session);
    }
    phase = 'run';
    void showItem();
  }

  function choose(c: Choice) {
    pending = c;
  }

  function commit(c: Choice | null = pending) {
    if (!selection || !session || !current || !c) return;
    const rt = performance.now() - shownAt;
    session = answer(session, selection, current.item, c, rt);
    if (isComplete(session, selection)) {
      session = finish(session, selection);
      save(session);
      phase = 'done';
      void tick().then(() => doneHeading?.focus({ preventScroll: true }));
      return;
    }
    save(session);
    void showItem();
  }

  function back() {
    if (!session || session.items.length === 0) return;
    session = undo(session);
    save(session);
    phase = 'run';
    void showItem();
  }

  function startOver() {
    if (!ask('Discard every recorded answer and start from item 1?')) return;
    clear();
    session = null;
    pending = null;
    resumable = false;
    phase = 'intro';
  }
  const ask = (msg: string) => (typeof window === 'undefined' ? true : window.confirm(msg));

  function onKey(e: KeyboardEvent) {
    if (phase !== 'run' && phase !== 'done') return;
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'Backspace') {
      e.preventDefault();
      back();
      return;
    }
    if (phase !== 'run') return;
    const k = e.key.toLowerCase();
    if (k === 'a') choose('A');
    else if (k === 'b') choose('B');
    else if (k === 't') choose('tie');
    else if (e.key === 'Enter') {
      e.preventDefault();
      commit();
      return;
    } else return;
    e.preventDefault();
  }

  async function copyJson() {
    if (!session) return;
    try {
      await navigator.clipboard.writeText(exportJson(session));
      copied = 'ok';
    } catch {
      copied = 'fail';
    }
  }

  function download() {
    if (!session) return;
    const blob = new Blob([exportJson(session)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = EXPORT_FILENAME;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const choiceLabel: Record<Choice, string> = { A: 'A', B: 'B', tie: 'Tie' };
  const choiceKey: Record<Choice, string> = { A: 'A', B: 'B', tie: 'T' };
</script>

<svelte:window onkeydown={onKey} />

<section class="mx-auto max-w-3xl py-6" aria-labelledby="triplets-title">
  <header class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
    <h1 id="triplets-title" class="text-2xl font-semibold tracking-tight">Shape judgments</h1>
    <span class="chip">dev-only</span>
    {#if phase === 'run' || phase === 'done'}
      <span class="ml-auto text-sm text-fg-2 tabular-nums" aria-live="polite" aria-atomic="true">{phase === 'done' ? `all ${total} items answered` : progress}</span>
    {/if}
  </header>

  {#if phase === 'empty'}
    <div class="card mt-6 text-sm leading-relaxed">
      <p class="font-medium">No triplet selection found.</p>
      <p class="mt-2 text-fg-2">
        This page reads <code class="rounded bg-surface-2 px-1 py-0.5">web/src/data/triplets_selection.json</code>, written by
        <code class="rounded bg-surface-2 px-1 py-0.5">make triplets-select</code>. Run that first, then reload.
      </p>
    </div>
  {:else if phase === 'intro'}
    <div class="card mt-6 space-y-4 text-sm leading-relaxed">
      <p>
        You will see <strong>{total} items</strong>. Each shows one pyramid on top (the <strong>anchor</strong>) and two below
        (labelled <strong>A</strong> and <strong>B</strong>; which side each sits on varies), all drawn at the same scale. Nothing names a country or a year, on purpose:
        judge the shapes only.
      </p>
      <p>
        Most items ask: <em>“{QUESTION.similar}”</em>
        A few ask the reverse — which is more <em>different</em> — and say so above the pyramids. Read the question every time.
      </p>
      <ul class="list-disc space-y-1 pl-5 text-fg-2">
        <li>Answer with the buttons, or the keys <kbd class="kbd">A</kbd> <kbd class="kbd">B</kbd> <kbd class="kbd">T</kbd> (tie) then <kbd class="kbd">Enter</kbd> to confirm. Clicking a button confirms at once.</li>
        <li><kbd class="kbd">Backspace</kbd> (or “Back”) returns to the previous item and asks it again.</li>
        <li>Response times are recorded, so answer at your natural pace and do not deliberate for long. About a minute per item is normal.</li>
        <li>Every answer is saved in this browser; closing the tab and coming back resumes where you left off.</li>
        <li>Use “tie” only when you genuinely cannot separate them — ties are dropped from the tests.</li>
      </ul>
      <label class="flex flex-wrap items-center gap-2">
        <span class="text-fg-2">Rater</span>
        <input class="w-40 rounded-md border border-border bg-surface px-2 py-1 text-sm text-fg" type="text" bind:value={rater} autocomplete="off" spellcheck="false" />
      </label>
      {#if warnings.length}
        <details class="text-xs text-fg-2">
          <summary>Selection differs from the pre-registered design ({warnings.length})</summary>
          <ul class="mt-1 list-disc pl-5">
            {#each warnings as w (w)}<li>{w}</li>{/each}
          </ul>
        </details>
      {/if}
      <div class="flex flex-wrap gap-2 pt-1">
        <button type="button" class="btn bg-surface-2 px-4 font-medium text-fg" onclick={() => start(true)}>Start</button>
      </div>
    </div>
  {:else if phase === 'run' && current}
    <div class="mt-4" style="outline: none" bind:this={stage} tabindex="-1" aria-labelledby="triplet-question">
      <p id="triplet-question" class="text-center text-lg font-medium {current.question === 'different' ? 'text-fg' : ''}">
        {questionFor(current)}
      </p>

      <figure class="mx-auto mt-3 flex w-fit flex-col items-center" aria-label="Anchor">
        <TripletPyramid row={current.shares.anchor} {axisPct} label="Anchor" size={PYR} />
        <figcaption class="mt-1 text-xs uppercase tracking-wide text-muted">anchor</figcaption>
      </figure>

      {#if left && right}
        <div class="mx-auto mt-4 grid w-full max-w-[34rem] grid-cols-2 justify-items-center gap-x-4 gap-y-1 sm:gap-x-10">
          <TripletPyramid row={left.row} {axisPct} label="Option {left.label}" size={PYR} emphasis={pending === left.label} />
          <TripletPyramid row={right.row} {axisPct} label="Option {right.label}" size={PYR} emphasis={pending === right.label} />
          <button type="button" class="btn min-h-10 w-full text-base font-semibold text-fg" aria-pressed={pending === left.label} onclick={() => commit(left.label)} aria-keyshortcuts={left.label}>{left.label}</button>
          <button type="button" class="btn min-h-10 w-full text-base font-semibold text-fg" aria-pressed={pending === right.label} onclick={() => commit(right.label)} aria-keyshortcuts={right.label}>{right.label}</button>
        </div>
      {/if}

      <div class="mx-auto mt-4 flex w-fit flex-wrap items-center justify-center gap-2 text-sm">
        <button type="button" class="btn" onclick={back} disabled={index === 0} aria-keyshortcuts="Backspace" title="Ask the previous item again">← Back</button>
        <button type="button" class="btn" aria-pressed={pending === 'tie'} onclick={() => commit('tie')} aria-keyshortcuts="T">Tie</button>
        {#if pending}
          <button type="button" class="btn bg-surface-2 font-medium text-fg" onclick={() => commit()} aria-keyshortcuts="Enter">Confirm {choiceLabel[pending]} ⏎</button>
        {:else}
          <span class="text-xs text-muted">keys: {Object.values(choiceKey).join(' · ')} then Enter</span>
        {/if}
      </div>
    </div>
  {:else if phase === 'done' && session}
    <div class="card mt-6 space-y-4 text-sm leading-relaxed">
      <h2 class="text-lg font-semibold outline-none" tabindex="-1" bind:this={doneHeading}>Done — {session.items.length} answers recorded</h2>
      <p class="text-fg-2">
        Rater <strong class="text-fg">{session.rater}</strong>, started {session.started.slice(0, 19).replace('T', ' ')} UTC,
        finished {(session.finished ?? '').slice(0, 19).replace('T', ' ')} UTC. Self-agreement on the repeated items is computed
        by the fit script, not here.
      </p>
      <ol class="list-decimal space-y-1 pl-5">
        <li>Save the JSON as <code class="rounded bg-surface-2 px-1 py-0.5">evals/triplets.json</code> in the repository (copy or download below).</li>
        <li>Run <code class="rounded bg-surface-2 px-1 py-0.5">make triplets-fit</code>; it reports self-agreement first, then the fits and the paired tests into RESULTS.md.</li>
      </ol>
      <div class="flex flex-wrap items-center gap-2">
        <button type="button" class="btn bg-surface-2 font-medium text-fg" onclick={copyJson}>Copy JSON</button>
        <button type="button" class="btn" onclick={download}>Download evals/{EXPORT_FILENAME}</button>
        <span class="text-xs text-muted" role="status" aria-live="polite">
          {#if copied === 'ok'}copied to the clipboard{:else if copied === 'fail'}clipboard blocked — use Download or the text below{/if}
        </span>
      </div>
      <details class="text-xs">
        <summary class="cursor-pointer text-fg-2">Show the JSON</summary>
        <textarea class="mt-2 h-48 w-full rounded-md border border-border bg-surface p-2 font-mono text-xs text-fg" readonly value={exportJson(session)} aria-label="Export JSON"></textarea>
      </details>
      <p class="flex flex-wrap gap-3 text-xs text-fg-2">
        <button type="button" class="underline" onclick={back}>Back to the last item (Backspace)</button>
        <button type="button" class="underline" onclick={startOver}>Start over (discards all answers)</button>
      </p>
    </div>
  {/if}

  {#if phase === 'run'}
    <p class="mt-8 text-center text-xs text-muted">
      {#if resumable}Resumed from this browser’s saved run · {/if}
      <button type="button" class="underline" onclick={startOver}>start over</button>
    </p>
  {/if}
</section>

<style>
  .kbd {
    display: inline-block;
    min-width: 1.4em;
    padding: 0 0.35em;
    border: 1px solid var(--border);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: var(--surface-2);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.85em;
    line-height: 1.5;
    text-align: center;
  }
</style>
