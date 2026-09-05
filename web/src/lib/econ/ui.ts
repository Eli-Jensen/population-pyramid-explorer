// The econ components live in ONE dynamic chunk (PLAN §7: `econ-[hash].js`): nothing under components/econ/ is imported
// statically by the country page, so the first paint of /japan/2026 is unchanged. `loadEconUi()` is memoised.

import { href } from '../url.ts';

let chunk: Promise<typeof import('../components/econ/index.ts')> | null = null;
export const loadEconUi = () => (chunk ??= import('../components/econ/index.ts'));

/** Anchors on /evidence the small "evidence" links point at. */
export type EvidenceAnchor = 'question' | 'links' | 'china' | 'backtest' | 'returns' | 'decision' | 'investability' | 'vintage' | 'sources' | 'never';

export function evidenceHref(anchor: EvidenceAnchor = 'question'): string {
  return `${href({ kind: 'static', page: 'evidence' })}#${anchor}`;
}
