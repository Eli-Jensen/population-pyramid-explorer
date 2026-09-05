<script lang="ts">
  import { href } from '../lib/url.ts';
  import { app } from '../lib/state.svelte.ts';
  import { countryQuery } from '../lib/router.ts';
  import Picker from '../lib/components/Picker.svelte';

  interface Props {
    path: string;
  }
  let { path }: Props = $props();
</script>

<div class="mx-auto max-w-xl py-16">
  <h1 class="text-2xl font-semibold">Nothing here</h1>
  <p class="mt-2 text-fg-2">
    <code class="rounded bg-surface-2 px-1 py-0.5 text-sm">{path}</code> is not a country, region or year we know. Pages look like
    <code class="rounded bg-surface-2 px-1 py-0.5 text-sm">/japan/2026</code> — any ISO code or common name works.
  </p>
  <div class="mt-4"><Picker id="nf-picker" onpick={(e) => app.go(countryQuery(e.id, app.currentYear))} /></div>
  <p class="mt-4 text-sm"><a class="underline" href={href({ kind: 'home' })}>← Home</a></p>
</div>
