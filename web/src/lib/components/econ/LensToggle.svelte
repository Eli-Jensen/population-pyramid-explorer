<script lang="ts">
  // Header toggle for the market lens (`?lens=econ`, PLAN §7). A real button with aria-pressed; the store owns the URL
  // + memory + first-activation banner. Tiny, so it sits in the shell rather than the lazy econ chunk.
  interface Props {
    on: boolean;
    onchange: (on: boolean) => void;
  }
  let { on, onchange }: Props = $props();
</script>

<button
  type="button"
  class="btn text-xs"
  class:lit={on}
  aria-pressed={on}
  onclick={() => onchange(!on)}
  title="Market lens: what happened afterwards to GDP per capita and to US-listed single-country funds (past figures beside VT; no forecast)"
>
  <span aria-hidden="true">◐</span><span class="ml-1">Market lens{on ? ' on' : ''}</span>
</button>

<style>
  .lit {
    background: color-mix(in srgb, var(--accent) 16%, var(--surface));
    border-color: var(--accent);
    color: var(--fg);
    font-weight: 500;
  }
</style>
