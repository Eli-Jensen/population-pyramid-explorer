<script lang="ts">
  // Entity picker (PLAN §2): search box with fuzzy match on name / ISO3 / aliases, countries and aggregates
  // in separate groups, keyboard navigable (combobox pattern). Flag emoji aria-hidden in a fixed-width span;
  // the ISO3 chip is always present.
  import { entities, flagEmoji } from '../entities.ts';
  import type { Entity } from '../types.ts';
  import { flatten, search, type Hit } from '../fuzzy.ts';
  import { fmtPersonsCompact } from '../format.ts';

  interface Props {
    onpick: (e: Entity) => void;
    placeholder?: string;
    autofocus?: boolean;
    size?: 'md' | 'lg';
    id?: string;
  }
  let { onpick, placeholder = 'Search a country or region…', autofocus = false, size = 'md', id = 'picker' }: Props = $props();

  let q = $state('');
  let open = $state(false);
  let active = $state(0);
  let inputEl: HTMLInputElement | undefined = $state();

  const groups = $derived(search(entities, q, q ? 8 : 6));
  const flat = $derived(flatten(groups));
  const listId = $derived(`${id}-list`);
  const optId = (e: Entity) => `${id}-opt-${e.id}`;

  function choose(h: Hit | undefined) {
    if (!h) return;
    onpick(h.entity);
    q = '';
    open = false;
    inputEl?.blur();
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      open = true;
      active = Math.min(flat.length - 1, active + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      active = Math.max(0, active - 1);
    } else if (e.key === 'Enter') {
      if (open && flat[active]) {
        e.preventDefault();
        choose(flat[active]);
      }
    } else if (e.key === 'Escape') {
      open = false;
    }
  }
  $effect(() => {
    void q;
    active = 0;
  });
  const chip = (e: Entity) => (e.type === 'country' ? e.id : (e.agg_kind ?? 'group'));
</script>

<div class="picker relative">
  <!-- svelte-ignore a11y_autofocus (the home page's only action is the search box) -->
  <input
    bind:this={inputEl}
    bind:value={q}
    {id}
    type="search"
    role="combobox"
    aria-expanded={open}
    aria-controls={listId}
    aria-autocomplete="list"
    aria-activedescendant={open && flat[active] ? optId(flat[active].entity) : undefined}
    autocomplete="off"
    spellcheck="false"
    {placeholder}
    {autofocus}
    class="w-full rounded-md border border-border bg-surface text-fg placeholder:text-muted {size === 'lg' ? 'px-4 py-3 text-lg' : 'px-3 py-1.5 text-sm'}"
    onfocus={() => (open = true)}
    oninput={() => (open = true)}
    onblur={() => setTimeout(() => (open = false), 120)}
    onkeydown={onKey}
  />
  {#if open}
    <ul
      id={listId}
      role="listbox"
      aria-label="Countries and regions"
      class="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-md border border-border bg-surface py-1 text-sm shadow-lg"
    >
      {#if flat.length === 0}
        <li class="px-3 py-2 text-muted" role="option" aria-selected="false" aria-disabled="true">No match for “{q}”</li>
      {/if}
      {#each [['Countries', groups.countries], ['Regions & groups', groups.aggregates]] as const as [label, hits] (label)}
        {#if hits.length}
          <li role="presentation" class="px-3 pt-2 pb-1 text-[10px] font-medium uppercase tracking-wide text-muted">{label}</li>
          {#each hits as h (h.entity.id)}
            {@const i = flat.indexOf(h)}
            <!-- svelte-ignore a11y_click_events_have_key_events (keyboard is handled on the combobox input) -->
            <li
              id={optId(h.entity)}
              role="option"
              aria-selected={i === active}
              class="flex cursor-pointer items-center gap-2 px-3 py-1.5 {i === active ? 'bg-surface-2' : ''}"
              onpointerenter={() => (active = i)}
              onpointerdown={(e) => e.preventDefault()}
              onclick={() => choose(h)}
            >
              <span class="inline-block w-6 text-center" aria-hidden="true">{flagEmoji(h.entity)}</span>
              <span class="chip w-14 justify-center font-mono text-[10px] uppercase">{chip(h.entity)}</span>
              <span class="truncate">{h.entity.short_name}</span>
              {#if h.entity.name !== h.entity.short_name}<span class="truncate text-xs text-muted">{h.entity.name}</span>{/if}
              <span class="ml-auto text-xs text-muted tabular-nums">{fmtPersonsCompact(h.entity.pop_2026)}</span>
            </li>
          {/each}
        {/if}
      {/each}
    </ul>
  {/if}
</div>
