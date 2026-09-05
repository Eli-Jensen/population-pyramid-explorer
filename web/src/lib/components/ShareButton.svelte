<script lang="ts">
  // Share (PLAN §7 J6): Copy link (clipboard, textarea fallback) + the Web Share sheet where the browser has one.
  // All state lives in the URL, so the current href IS the view; callers pass `url` when a resolved/canonical link
  // should be shared instead (the compare page hands in the concrete-year URL so `best` never leaks).
  import { canShare, copyText, share } from '../export.ts';

  interface Props {
    url?: (() => string) | string | null; // default: location.href at click time
    title?: string;
    text?: string;
    compact?: boolean; // icon-only buttons
  }
  let { url = null, title = 'Population Pyramid Explorer', text, compact = false }: Props = $props();

  let copied = $state<'idle' | 'ok' | 'fail'>('idle');
  let status = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;
  const shareable = typeof navigator !== 'undefined' && canShare();

  function target(): string {
    if (typeof url === 'function') return url();
    if (url) return url;
    return typeof location === 'undefined' ? '' : location.href;
  }
  function flash(next: typeof copied, msg: string) {
    copied = next;
    status = msg;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      copied = 'idle';
      status = null;
    }, 1800);
  }
  async function onCopy() {
    const ok = await copyText(target());
    flash(ok ? 'ok' : 'fail', ok ? 'Link copied' : 'Could not copy — select the address bar instead');
  }
  async function onShare() {
    const out = await share({ url: target(), title, text });
    if (out === 'failed') flash('fail', 'Sharing failed');
    else if (out === 'unavailable') void onCopy();
  }
</script>

<div class="inline-flex items-center gap-1" role="group" aria-label="Share">
  <button type="button" class="btn gap-1" onclick={onCopy} title="Copy a link to exactly this view" aria-label={compact ? 'Copy link' : undefined}>
    <span aria-hidden="true">{copied === 'ok' ? '✓' : '⧉'}</span>
    {#if !compact}<span>{copied === 'ok' ? 'Copied' : copied === 'fail' ? 'Copy failed' : 'Copy link'}</span>{/if}
  </button>
  {#if shareable}
    <button type="button" class="btn gap-1" onclick={onShare} title="Share this view" aria-label={compact ? 'Share' : undefined}>
      <span aria-hidden="true">↗</span>
      {#if !compact}<span>Share</span>{/if}
    </button>
  {/if}
  <span class="sr-only" role="status" aria-live="polite">{status ?? ''}</span>
</div>
