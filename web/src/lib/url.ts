// Browser history helpers over the pure router (PLAN §7). Everything that touches `window` is here and
// injectable (HistoryLike / LocationLike / EventTarget) so vitest can drive it without a DOM.

import { canonical, parse, type Query, type Route, type ParseOptions, defaultEra, elideDefaults } from './router.ts';

export { defaultEra, elideDefaults };

/** Vite's base ('/population-pyramid-explorer/' on GitHub Pages, '/' locally with VITE_BASE=/). */
export const BASE: string = import.meta.env.BASE_URL ?? '/';

export interface HistoryLike {
  pushState(data: unknown, unused: string, url?: string | null): void;
  replaceState(data: unknown, unused: string, url?: string | null): void;
}
export interface LocationLike {
  pathname: string;
  search: string;
}

export interface Env {
  base?: string;
  history?: HistoryLike;
  location?: LocationLike;
  target?: EventTarget; // popstate source (window by default)
}

const win = () => (typeof window === 'undefined' ? null : window);
const envHistory = (e: Env): HistoryLike | null => e.history ?? win()?.history ?? null;
const envLocation = (e: Env): LocationLike | null => e.location ?? win()?.location ?? null;

/** Canonical href for a query with the base prefix — use for every emitted link. */
export function href(query: Query, base: string = BASE): string {
  return canonical(query, base);
}

/** pathname + search of the current location ('' when there is no window). */
export function currentHref(env: Env = {}): string {
  const loc = envLocation(env);
  return loc ? loc.pathname + loc.search : '';
}

/** Parse the current location. */
export function currentRoute(env: Env = {}, opts: ParseOptions = {}): Route {
  const loc = envLocation(env);
  if (!loc) return { kind: 'home' };
  return parse(loc.pathname, loc.search, env.base ?? BASE, opts);
}

/**
 * Put a raw URL into history. No-op (returns false) when it equals the current href, so scrubbing never
 * spams identical entries. `replace` → replaceState, else pushState.
 */
export function navigateTo(url: string, { replace = false, ...env }: { replace?: boolean } & Env = {}): boolean {
  const h = envHistory(env);
  if (!h) return false;
  if (currentHref(env) === url) return false;
  if (replace) h.replaceState(null, '', url);
  else h.pushState(null, '', url);
  return true;
}

/** Navigate to a query's canonical URL. Returns whether the URL changed. */
export function navigate(query: Query, opts: { replace?: boolean } & Env = {}): boolean {
  return navigateTo(href(query, opts.base ?? BASE), opts);
}

/**
 * Subscribe to popstate (Back/Forward). The callback receives the parsed Route of the new location.
 * Returns an unsubscribe function. Pass `target` (an EventTarget) for tests.
 */
export function onPopState(
  cb: (route: Route) => void,
  { parseOpts = {}, ...env }: { parseOpts?: ParseOptions } & Env = {},
): () => void {
  const t = env.target ?? win();
  if (!t) return () => {};
  const handler = () => cb(currentRoute(env, parseOpts));
  t.addEventListener('popstate', handler);
  return () => t.removeEventListener('popstate', handler);
}
