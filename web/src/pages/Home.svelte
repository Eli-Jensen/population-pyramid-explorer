<script lang="ts">
  // '/' — search box, "continue with {last}", start with World / your country, source line (PLAN §7).
  import { app } from '../lib/state.svelte.ts';
  import { byId, countries, meta, resolve } from '../lib/entities.ts';
  import { countryQuery } from '../lib/router.ts';
  import { href } from '../lib/url.ts';
  import { readLast } from '../lib/last.ts';
  import Picker from '../lib/components/Picker.svelte';

  const last = $derived.by(() => {
    const l = readLast();
    const e = l ? byId(l.id) : undefined;
    return e && l ? { entity: e, year: l.year } : null;
  });
  const world = resolve('agg-900') ?? resolve('world');
  const yours = $derived.by(() => {
    if (typeof navigator === 'undefined') return null;
    for (const lang of navigator.languages ?? [navigator.language]) {
      const region = new Intl.Locale(lang).region;
      const e = region ? resolve(region) : undefined;
      if (e && e.type === 'country') return e;
    }
    return null;
  });
  const starters = $derived(
    ['IND', 'CHN', 'USA', 'NGA', 'JPN', 'NER', 'QAT', 'KOR']
      .map((id) => byId(id))
      .filter((e): e is NonNullable<typeof e> => !!e),
  );
  const nCountries = countries.length;
</script>

<div class="mx-auto max-w-2xl py-10 sm:py-16">
  <h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">Population Pyramid Explorer</h1>
  <p class="mt-2 text-fg-2">
    Every country's age structure, 1950–2100. {nCountries} countries and {meta.n_entities - nCountries} regions from the UN World Population Prospects 2024.
  </p>

  <div class="mt-6">
    <label for="home-picker" class="sr-only">Search a country or region</label>
    <Picker id="home-picker" size="lg" autofocus onpick={(e) => app.go(countryQuery(e.id, app.currentYear))} />
  </div>

  <div class="mt-6 flex flex-wrap gap-2 text-sm">
    {#if last}
      <a class="btn" href={href(countryQuery(last.entity.id, last.year))}>Continue with {last.entity.short_name} {last.year} →</a>
    {/if}
    {#if world}
      <a class="btn" href={href(countryQuery(world.id, app.currentYear))}>Start with World</a>
    {/if}
    {#if yours}
      <a class="btn" href={href(countryQuery(yours.id, app.currentYear))}>Your country: {yours.short_name}</a>
    {/if}
  </div>

  <h2 class="mt-8 text-xs font-medium uppercase tracking-wide text-muted">Try one</h2>
  <ul class="mt-2 flex flex-wrap gap-2 text-sm">
    {#each starters as e (e.id)}
      <li><a class="chip hover:text-fg" href={href(countryQuery(e.id, app.currentYear))}>{e.short_name}</a></li>
    {/each}
  </ul>

  <p class="mt-10 text-xs text-muted">
    Source: {meta.attribution[0]} Built {meta.built.slice(0, 10)}; last observed year {meta.last_observed_year}, later years are medium-variant projections.
  </p>
</div>
