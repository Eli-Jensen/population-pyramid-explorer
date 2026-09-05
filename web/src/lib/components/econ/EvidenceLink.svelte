<script lang="ts">
  // The small "evidence" link every econ number carries (PLAN §7): → /evidence#anchor.
  import { evidenceHref, type EvidenceAnchor } from '../../econ/ui.ts';
  interface Props {
    anchor?: EvidenceAnchor;
    title?: string;
  }
  let { anchor = 'question', title = 'How this number was made, its source and what the literature found' }: Props = $props();
</script>

<a class="ml-1 align-baseline text-[10px] font-normal text-muted underline decoration-dotted underline-offset-2 hover:text-fg" href={evidenceHref(anchor)} {title}>evidence</a>
