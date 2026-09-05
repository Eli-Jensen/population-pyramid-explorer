<script lang="ts">
  // Shell: routes via the pure router through the store (popstate + same-origin link interception),
  // renders Home / Country / Compare / About (lazy) / NotFound, keeps document.title in sync.
  import { onMount } from 'svelte';
  import { app } from './lib/state.svelte.ts';
  import { parse } from './lib/router.ts';
  import { BASE, href, navigateTo } from './lib/url.ts';
  import Home from './pages/Home.svelte';
  import Country from './pages/Country.svelte';
  // Compare and About are lazy chunks: neither belongs in the country page's first paint (PLAN §7 budget ≤ 175 KB
  // on the wire for /japan/2026). Vite splits them out; the import() runs the first time its route renders and the
  // promise is memoised so route flips do not re-fetch.
  let compareChunk: Promise<typeof import('./pages/Compare.svelte')> | null = null;
  let aboutChunk: Promise<typeof import('./pages/About.svelte')> | null = null;
  const loadCompare = () => (compareChunk ??= import('./pages/Compare.svelte'));
  const loadAbout = () => (aboutChunk ??= import('./pages/About.svelte'));
  import NotFound from './pages/NotFound.svelte';

  onMount(() => app.init());

  function onClick(e: MouseEvent) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as Element | null)?.closest('a[href]');
    if (!(a instanceof HTMLAnchorElement) || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || !url.pathname.toLowerCase().startsWith(BASE.toLowerCase())) return;
    e.preventDefault();
    const route = parse(url.pathname, url.search, BASE);
    navigateTo(url.pathname + url.search);
    app.applyRoute(route);
    window.scrollTo({ top: 0 });
  }

  const title = $derived.by(() => {
    const r = app.route;
    if (r.kind === 'country' && app.entity) return `${app.entity.short_name} ${app.year} · Population Pyramid Explorer`;
    if (r.kind === 'compare' && app.entityA && app.entityB) return `${app.entityA.short_name} ${r.ya} vs ${app.entityB.short_name} ${r.yb} · Population Pyramid Explorer`;
    if (r.kind === 'static') return `About · Population Pyramid Explorer`;
    if (r.kind === 'notfound') return 'Not found · Population Pyramid Explorer';
    return 'Population Pyramid Explorer';
  });
  $effect(() => {
    document.title = title;
  });
</script>

<svelte:document onclick={onClick} />

<div class="min-h-dvh bg-bg text-fg">
  <nav class="border-b border-border">
    <div class="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2 text-sm">
      <a href={href({ kind: 'home' })} class="font-semibold tracking-tight">▲ Population Pyramid Explorer</a>
      <span class="ml-auto text-xs text-muted">UN WPP 2024</span>
    </div>
  </nav>
  <main class="mx-auto max-w-6xl px-4 py-4">
    {#if app.route.kind === 'country'}
      <Country />
    {:else if app.route.kind === 'compare'}
      {#await loadCompare()}
        <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading the compare page…</p>
      {:then m}
        <m.default />
      {/await}
    {:else if app.route.kind === 'static'}
      {#await loadAbout()}
        <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading…</p>
      {:then m}
        <m.default />
      {/await}
    {:else if app.route.kind === 'notfound'}
      <NotFound path={app.route.path} />
    {:else if app.route.kind === 'placeholder'}
      <div class="py-16 text-center text-fg-2">
        <h1 class="text-xl font-semibold">/{app.route.route} arrives in a later milestone</h1>
        <p class="mt-2 text-sm"><a class="underline" href={href({ kind: 'home' })}>← Home</a></p>
      </div>
    {:else}
      <Home />
    {/if}
  </main>
</div>
