// App store (PLAN §7/§8): one class with $state runes, in Eli's retiremap style.
// Owns the route/query, the current-year clock, the tier-1 shards (entity shard + year shard) and the
// derived pyramid/features/axis. Pure math lives in lib/math/*, fetching in lib/data.ts. History semantics:
// replaceState while dragging the year slider, one pushState on release (Back returns to the pre-drag
// year); pushState on entity change; replaceState for display-option tweaks and canonicalising redirects.

import {
  byId,
  currentYear as clockYear,
  eraOf,
  idxOf,
  meta,
  N_DIMS,
  YEAR_MIN,
  clampYear,
  systemClock,
  type Clock,
  type Entity,
  type Era,
} from './entities.ts';
import { entityShardPyramid, loadEntityShard, loadYearShard, yearShardPyramid } from './data.ts';
import { features as computeFeatures, type Features } from './math/features.ts';
import { axisFor, maxBinPct, type AxisChoice, type AxisMode } from './math/scale.ts';
import {
  countryQuery,
  isCountry,
  type Axis,
  type CountryQuery,
  type DisplayOptions,
  type Query,
  type Route,
} from './router.ts';
import type { EntityShard, Pyramid, YearShard } from './types.ts';
import { currentHref, currentRoute, navigate, navigateTo, onPopState, type Env } from './url.ts';

export type { EntityShard, Features, Pyramid, YearShard };

/** The pyramid on screen: `Pyramid` (42 shares of total + total in thousands) plus provenance. */
export interface PyramidView extends Pyramid {
  id: string;
  year: number;
  u16: Uint16Array; // the quantised row (view into the shard), Σ = 65535
  source: 'entity' | 'year'; // which shard it came from
}

export function pyramidFromEntityShard(shard: EntityShard, year: number): PyramidView {
  const row = year - YEAR_MIN;
  return {
    ...entityShardPyramid(shard, year),
    id: shard.id,
    year,
    u16: shard.u16.subarray(row * N_DIMS, (row + 1) * N_DIMS),
    source: 'entity',
  };
}
export function pyramidFromYearShard(shard: YearShard, id: string): PyramidView | null {
  const row = idxOf(id);
  if (row < 0 || row >= shard.n) return null;
  return {
    ...yearShardPyramid(shard, row),
    id,
    year: shard.year,
    u16: shard.u16.subarray(row * N_DIMS, (row + 1) * N_DIMS),
    source: 'year',
  };
}

/** URL axis vocabulary (router) → math/scale.ts mode. */
export function toAxisMode(axis: Axis): AxisMode {
  return axis === 'noclip' ? 'never' : axis;
}

// ---- injectable collaborators ------------------------------------------------------------------------

export interface DataSource {
  entityShard(id: string): Promise<EntityShard>;
  yearShard(year: number): Promise<YearShard>;
}
/** Production source: lib/data.ts tier-1 loaders (memoised, BASE_URL-aware). */
export const dataSource: DataSource = { entityShard: loadEntityShard, yearShard: loadYearShard };

export type FeaturesFn = (shares: Float32Array) => Features;

export interface AppStateOptions {
  clock?: Clock;
  data?: DataSource;
  env?: Env; // history/location/popstate-target/base injection for tests
  features?: FeaturesFn; // defaults to math/features.ts
}

// ---- store ----------------------------------------------------------------------------------------------

export class AppState {
  route = $state<Route>({ kind: 'home' });
  currentYear = $state(clockYear());
  entityShard = $state<EntityShard | null>(null);
  yearShard = $state<YearShard | null>(null);
  loading = $state(false);
  error = $state<string | null>(null);

  readonly lastObservedYear = meta.last_observed_year;

  // collaborators (declared before the $derived fields that read them)
  private clock: Clock = systemClock;
  private data: DataSource = dataSource;
  private env: Env = {};
  private featuresFn: FeaturesFn = computeFeatures;
  private entityCache = new Map<string, EntityShard>();
  private yearCache = new Map<number, YearShard>();
  private gen = 0; // staleness token for in-flight loads
  private dragFrom: string | null = null; // href before the current slider drag
  private unsub: (() => void) | null = null;

  query = $derived<CountryQuery | null>(isCountry(this.route) ? this.route : null);
  entity = $derived<Entity | null>(this.query ? (byId(this.query.id) ?? null) : null);
  year = $derived(this.query?.year ?? this.currentYear);
  options = $derived<DisplayOptions>({ axis: this.query?.axis ?? 'fit', unit: this.query?.unit ?? 'pct' });
  era = $derived<Era>(eraOf(this.year, this.currentYear, this.lastObservedYear));
  isProjected = $derived(this.year > this.currentYear);

  /** The pyramid on screen: entity shard first (scrubbing needs no fetch), year shard as a fallback. */
  pyramid = $derived.by<PyramidView | null>(() => {
    const q = this.query;
    if (!q) return null;
    if (this.entityShard?.id === q.id) return pyramidFromEntityShard(this.entityShard, q.year);
    if (this.yearShard?.year === q.year) return pyramidFromYearShard(this.yearShard, q.id);
    return null;
  });
  features = $derived<Features | null>(this.pyramid ? this.featuresFn(this.pyramid.shares) : null);

  axisMode = $derived<AxisMode>(toAxisMode(this.options.axis));
  /** Fixed symmetric axis (PLAN §2): fit → entities[].axis_pct (widened only if the drawn year overflows),
   *  pin10 → 10 % with a clip marker, never → 17 %. `clips` tells the chart to draw the ▸ marker. */
  axis = $derived<AxisChoice>(
    axisFor(this.axisMode, this.entity?.axis_pct ?? 10, this.pyramid ? maxBinPct(this.pyramid.shares) : 0),
  );
  axisPct = $derived(this.axis.axisPct);

  constructor(opts: AppStateOptions = {}) {
    this.clock = opts.clock ?? systemClock;
    this.data = opts.data ?? dataSource;
    this.env = opts.env ?? {};
    this.featuresFn = opts.features ?? computeFeatures;
    this.currentYear = clockYear(this.clock);
  }

  /** Read the current location, canonicalise it, subscribe to Back/Forward and start loading. */
  init(): () => void {
    this.applyRoute(currentRoute(this.env, { clock: this.clock }));
    this.unsub?.();
    this.unsub = onPopState((r) => this.applyRoute(r, { fromHistory: true }), {
      ...this.env,
      parseOpts: { clock: this.clock },
    });
    return () => this.dispose();
  }

  dispose() {
    this.unsub?.();
    this.unsub = null;
    this.gen++;
  }

  /** Adopt a parsed route. Redirects are applied with replaceState (aliases, case, hub year, defaults). */
  applyRoute(r: Route, { fromHistory = false }: { fromHistory?: boolean } = {}) {
    if (r.kind === 'redirect') {
      navigateTo(r.to, { replace: true, ...this.env });
      r = r.query;
    }
    this.route = r;
    this.dragFrom = null;
    if (!fromHistory) this.currentYear = clockYear(this.clock); // a long-lived tab crossing New Year
    void this.load();
  }

  /**
   * Set the year. `commit: false` while dragging → replaceState only (no fetch); `commit: true` (release,
   * keyboard step, play tick) → one pushState relative to the pre-drag URL, then the year shard loads.
   */
  setYear(y: number, { commit = true }: { commit?: boolean } = {}) {
    const q = this.query;
    if (!q) return;
    const year = clampYear(y);
    const next: CountryQuery = { ...q, year };
    if (!commit) {
      this.dragFrom ??= currentHref(this.env);
      this.route = next;
      navigate(next, { replace: true, ...this.env });
      return;
    }
    this.route = next;
    if (this.dragFrom !== null) {
      // rewind the replaceState trail so Back lands on the pre-drag year, then push the final one
      navigateTo(this.dragFrom, { replace: true, ...this.env });
      this.dragFrom = null;
    }
    navigate(next, { ...this.env });
    void this.load();
  }

  /** Switch entity, keeping year and options (pushState). Unknown ids are ignored. */
  setEntity(id: string) {
    const e = byId(id);
    if (!e) return;
    const q = this.query;
    const next = countryQuery(e.id, q?.year ?? this.currentYear, q ?? {});
    this.dragFrom = null;
    this.route = next;
    navigate(next, { ...this.env });
    void this.load();
  }

  /** Change a display option (replaceState — a view tweak, not a navigation step). */
  setOptions(o: Partial<DisplayOptions>) {
    const q = this.query;
    if (!q) return;
    const next = countryQuery(q.id, q.year, { ...q, ...o });
    this.route = next;
    navigate(next, { replace: true, ...this.env });
  }

  /** Navigate to any query (pushState) — for the picker / links handled in-app. */
  go(q: Query) {
    this.dragFrom = null;
    this.route = q;
    navigate(q, { ...this.env });
    void this.load();
  }

  /** Tier-1 loads for the current query: entity shard (paint + scrubbing) and year shard (same-year set). */
  private async load(): Promise<void> {
    const q = this.query;
    const gen = ++this.gen;
    if (!q) {
      this.loading = false;
      return;
    }
    const cachedE = this.entityCache.get(q.id);
    const cachedY = this.yearCache.get(q.year);
    if (cachedE) this.entityShard = cachedE;
    if (cachedY) this.yearShard = cachedY;
    if (cachedE && cachedY) {
      this.loading = false;
      this.error = null;
      return;
    }
    this.loading = !cachedE; // the page can paint from either shard; report loading only until one lands
    this.error = null;
    const tasks: Promise<void>[] = [];
    if (!cachedE) {
      tasks.push(
        this.data.entityShard(q.id).then((s) => {
          this.entityCache.set(q.id, s);
          if (gen === this.gen) {
            this.entityShard = s;
            this.loading = false;
          }
        }),
      );
    }
    if (!cachedY) {
      tasks.push(
        this.data.yearShard(q.year).then((s) => {
          this.yearCache.set(q.year, s);
          if (gen === this.gen) {
            this.yearShard = s;
            this.loading = false;
          }
        }),
      );
    }
    const results = await Promise.allSettled(tasks);
    if (gen !== this.gen) return;
    const failed = results.find((r): r is PromiseRejectedResult => r.status === 'rejected');
    if (failed && !this.pyramid) {
      this.error = failed.reason instanceof Error ? failed.reason.message : String(failed.reason);
      this.loading = false;
    }
  }
}

/** Singleton for the app; tests construct their own `new AppState({...})`. */
export const app = new AppState();
