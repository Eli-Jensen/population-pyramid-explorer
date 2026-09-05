// Fixed econ copy that the SHELL needs (footer, banner) — kept free of the JSON sentence banks so App.svelte's chunk
// does not carry them. lang.ts re-exports both and lang.test.ts runs the deny list over them.

/** The banner shown on the first activation of the lens (PLAN §7). */
export const LENS_BANNER = 'This lens shows what happened afterwards in published data. Across countries, faster GDP growth has gone with lower equity returns.';

/** Footer on every page (PLAN §7 language rules; "Pyramid-twins" → the site name per DECISION 5's 1:1 rename). */
export const FOOTER_DISCLAIMER =
  'Population Pyramid Explorer shows demographic shapes and what happened afterwards in published data. It is not investment advice, makes no forecasts, and names funds only as examples of what exists or existed. Past index returns do not predict future returns; across countries, faster GDP growth has historically gone with lower equity returns (Ritter 2005, 2012).';
