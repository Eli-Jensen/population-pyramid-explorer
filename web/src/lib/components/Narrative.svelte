<script lang="ts">
  // Prose summary — the text comes from lib/narrative.ts (pure, tested); this is markup only.
  interface Props {
    paragraphs: string[];
  }
  let { paragraphs }: Props = $props();
</script>

<section class="card" aria-label="Summary">
  <h2 class="text-xs font-medium uppercase tracking-wide text-muted">In words</h2>
  <div class="mt-2 space-y-2 text-sm leading-relaxed text-fg">
    {#each paragraphs as p, i (i)}
      <p>{p}</p>
    {/each}
  </div>
</section>
