<script lang="ts">
  // Shell: routes via the pure router through the store (popstate + same-origin link interception),
  // renders Home / Country / Compare / About / Evidence (lazy) / Triplets (dev-only, lazy) / NotFound, keeps
  // document.title in sync, carries the market-lens toggle + its first-activation banner and the footer disclaimer
  // that stands on every page (PLAN §7 language rules).
  import { onMount, type Component } from 'svelte';
  import { app } from './lib/state.svelte.ts';
  import { parse } from './lib/router.ts';
  import { BASE, href, navigateTo } from './lib/url.ts';
  import { FOOTER_DISCLAIMER, LENS_BANNER } from './lib/econ/copy.ts';
  import LensToggle from './lib/components/econ/LensToggle.svelte';
  import Home from './pages/Home.svelte';
  import Country from './pages/Country.svelte';
  // Compare, About and Evidence are lazy chunks: none belongs in the country page's first paint (PLAN §7 budget ≤ 175 KB
  // on the wire for /japan/2026). Vite splits them out; the import() runs the first time its route renders and the
  // promise is memoised so route flips do not re-fetch.
  let compareChunk: Promise<typeof import('./pages/Compare.svelte')> | null = null;
  let aboutChunk: Promise<typeof import('./pages/About.svelte')> | null = null;
  let evidenceChunk: Promise<typeof import('./pages/Evidence.svelte')> | null = null;
  const loadCompare = () => (compareChunk ??= import('./pages/Compare.svelte'));
  const loadAbout = () => (aboutChunk ??= import('./pages/About.svelte'));
  const loadEvidence = () => (evidenceChunk ??= import('./pages/Evidence.svelte'));
  // /eval/triplets (dev-only, PLAN §4.6 item 8): a glob import so the shell builds whether or not pages/Triplets.svelte
  // exists yet, and the tool never enters a production bundle path.
  const DEV = import.meta.env.DEV;
  const tripletModules = import.meta.glob<{ default: Component }>('./pages/Triplets.svelte');
  const loadTriplets: (() => Promise<{ default: Component }>) | null = tripletModules['./pages/Triplets.svelte'] ?? null;
  const hasTriplets = loadTriplets !== null;
  import NotFound from './pages/NotFound.svelte';

  onMount(() => app.init());

  function onClick(e: MouseEvent) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as Element | null)?.closest('a[href]');
    if (!(a instanceof HTMLAnchorElement) || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || !url.pathname.toLowerCase().startsWith(BASE.toLowerCase())) return;
    if (url.hash && url.pathname === location.pathname && url.search === location.search) return; // in-page anchor
    e.preventDefault();
    const route = parse(url.pathname, url.search, BASE);
    navigateTo(url.pathname + url.search + url.hash);
    app.applyRoute(route);
    if (url.hash) {
      requestAnimationFrame(() => document.getElementById(url.hash.slice(1))?.scrollIntoView());
    } else window.scrollTo({ top: 0 });
  }

  const lensRoute = $derived(app.route.kind === 'country' || app.route.kind === 'compare');
  const evidenceHref = href({ kind: 'static', page: 'evidence' });

  const title = $derived.by(() => {
    const r = app.route;
    if (r.kind === 'country' && app.entity) return `${app.entity.short_name} ${app.year} · Population Pyramid Explorer`;
    if (r.kind === 'compare' && app.entityA && app.entityB) return `${app.entityA.short_name} ${r.ya} vs ${app.entityB.short_name} ${r.yb} · Population Pyramid Explorer`;
    if (r.kind === 'static') return `${r.page === 'evidence' ? 'Evidence' : 'About'} · Population Pyramid Explorer`;
    if (r.kind === 'eval') return `Triplets (dev) · Population Pyramid Explorer`;
    if (r.kind === 'notfound') return 'Not found · Population Pyramid Explorer';
    return 'Population Pyramid Explorer';
  });
  $effect(() => {
    document.title = title;
  });
</script>

<svelte:document onclick={onClick} />

<div class="flex min-h-dvh flex-col bg-bg text-fg">
  <nav class="border-b border-border">
    <div class="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2 text-sm">
      <a href={href({ kind: 'home' })} class="font-semibold tracking-tight">▲ Population Pyramid Explorer</a>
      <span class="ml-auto text-xs text-muted">UN WPP 2024</span>
      {#if lensRoute}
        <LensToggle on={app.lensOn} onchange={(on) => app.setLens(on)} />
      {/if}
    </div>
  </nav>
  {#if app.lensBanner}
    <div class="border-b border-border bg-surface-2" role="status">
      <div class="mx-auto flex max-w-6xl items-start gap-3 px-4 py-2 text-sm">
        <p class="min-w-0 flex-1 text-fg-2">{LENS_BANNER} <a class="underline" href={evidenceHref}>→ Evidence</a></p>
        <button type="button" class="btn shrink-0 text-xs" onclick={() => app.dismissLensBanner()} aria-label="Dismiss this notice">✕ dismiss</button>
      </div>
    </div>
  {/if}
  <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-4">
    {#if app.route.kind === 'country'}
      <Country />
    {:else if app.route.kind === 'compare'}
      {#await loadCompare()}
        <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading the compare page…</p>
      {:then m}
        <m.default />
      {/await}
    {:else if app.route.kind === 'static' && app.route.page === 'evidence'}
      {#await loadEvidence()}
        <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading the evidence page…</p>
      {:then m}
        <m.default />
      {/await}
    {:else if app.route.kind === 'static'}
      {#await loadAbout()}
        <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading…</p>
      {:then m}
        <m.default />
      {/await}
    {:else if app.route.kind === 'eval'}
      {#if DEV && loadTriplets}
        {#await loadTriplets()}
          <p class="py-8 text-center text-sm text-muted" aria-busy="true">loading the triplet tool…</p>
        {:then m}
          <m.default />
        {/await}
      {:else}
        <div class="py-16 text-center text-fg-2">
          <h1 class="text-xl font-semibold">/eval/{app.route.tool} is a development-only tool</h1>
          <p class="mt-2 text-sm">{hasTriplets ? 'Run the site with `npm run dev` to use it.' : 'Its page is not part of this build.'} <a class="underline" href={href({ kind: 'home' })}>← Home</a></p>
        </div>
      {/if}
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
  <footer class="border-t border-border">
    <p class="mx-auto max-w-6xl px-4 py-4 text-xs leading-relaxed text-muted">
      {FOOTER_DISCLAIMER} <a class="underline" href={evidenceHref}>→ Evidence</a>
    </p>
  </footer>
</div>
