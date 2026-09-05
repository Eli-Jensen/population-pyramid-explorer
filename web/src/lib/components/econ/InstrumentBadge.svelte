<script lang="ts">
  // Investability badge (PLAN §7): `live INDA (iShares, since 2012)` / `liquidated NGE 2024-03-25` / `no US-listed
  // single-country fund` + the MSCI class + the capital-mobility flag + dated market events. The chips are compact
  // (ticker · issuer · year / ticker · last trading day from the shipped econ file, i.e. etf_manual's SEC-filing date);
  // each chip's title is the full L0.investability sentence rendered through lang.ts, and the fund-less case IS that
  // sentence. Links go ONLY to the issuer's own notice / filing / product page (never a broker, never a quote).
  import { events as econEvents, instruments, mobility as econMobility, msciClass, type EconData, type Mobility } from '../../econ.ts';
  import { investability } from '../../econ/lang.ts';
  import EvidenceLink from './EvidenceLink.svelte';

  interface Props {
    econ: EconData;
    iso3: string;
    /** Show the mobility flag + events (lens on). */
    detail?: boolean;
  }
  let { econ, iso3, detail = true }: Props = $props();

  const list = $derived(instruments(econ, iso3));
  const live = $derived(list.filter((i) => i.status === 'live'));
  const dead = $derived(list.filter((i) => i.status !== 'live'));
  const cls = $derived(msciClass(econ, iso3));
  const mob = $derived(econMobility(econ, iso3));
  const evs = $derived(econEvents(econ, iso3));
  const MOB_LABEL: Record<Mobility, string> = { open: 'capital mobility: open', restricted: 'capital mobility: restricted', closed: 'capital mobility: closed', not_assessed: 'capital mobility: not assessed' };
  const MOB_HINT: Record<Mobility, string> = {
    open: 'MSCI developed or emerging market and no repatriation or index-deletion event on record',
    restricted: 'MSCI frontier market with a repatriation event on record',
    closed: 'standalone market or an index deletion on record — foreign holders could not repatriate at the index price',
    not_assessed: 'no fund, no MSCI class and no event on record; nothing is asserted either way',
  };
  const CLASS_LABEL: Record<string, string> = { DM: 'MSCI developed', EM: 'MSCI emerging', FM: 'MSCI frontier', standalone: 'MSCI standalone', none: 'not in the MSCI universe' };
  const noneSentence = $derived(investability('none_ever', {}));
  const issuerShort = (issuer: string) => issuer.replace(/\s*\(.*\)$/, '');
  const liveTitle = (i: (typeof list)[number]) => investability('live', { ticker: i.ticker, issuer: issuerShort(i.issuer), inception: i.inception }) ?? i.name ?? i.ticker;
  const deadTitle = (i: (typeof list)[number]) => (i.status === 'liquidated' ? investability('liquidated', { ticker: i.ticker, delisted: i.delisted ?? i.liquidationDate ?? 'n/a' }) : null) ?? i.name ?? i.ticker;
</script>

<div class="flex flex-wrap items-center gap-1.5 text-xs">
  {#if live.length === 0 && dead.length === 0}
    <span class="chip">{noneSentence}</span>
  {/if}
  {#each live as i (i.ticker)}
    <span class="chip live" title={liveTitle(i)}>
      live
      {#if i.sourceUrl}<a class="ml-1 font-mono underline decoration-dotted" href={i.sourceUrl} rel="noopener" target="_blank">{i.ticker}</a>{:else}<span class="ml-1 font-mono">{i.ticker}</span>{/if}
      <span class="ml-1 text-muted">({issuerShort(i.issuer)}, since {i.inceptionYear})</span>
    </span>
  {/each}
  {#each dead as i (i.ticker)}
    <span class="chip dead" title={deadTitle(i)}>
      {i.status}
      <span class="ml-1 font-mono">{i.ticker}</span>
      {#if i.delisted}<span class="ml-1 text-muted tabular-nums">{i.delisted}</span>{/if}
      {#if i.statusUrl}<a class="ml-1 underline decoration-dotted" href={i.statusUrl} rel="noopener" target="_blank" title="issuer notice">notice</a>{/if}
    </span>
  {/each}
  {#if cls}<span class="chip" title="MSCI market classification as recorded on 2026-09-04 (informational; no test reads it)">{CLASS_LABEL[cls] ?? `MSCI ${cls}`}</span>{/if}
  {#if detail && mob}<span class="chip mob-{mob}" title={MOB_HINT[mob]}>{MOB_LABEL[mob]}</span>{/if}
  {#if detail}
    {#each evs as ev (ev.date + ev.kind)}
      <span class="chip" title={ev.detail ?? ev.note ?? ev.kind}>
        {ev.kind.replace(/_/g, ' ')} <span class="ml-1 tabular-nums text-muted">{ev.date}</span>
        {#if ev.url}<a class="ml-1 underline decoration-dotted" href={ev.url} rel="noopener" target="_blank">source</a>{/if}
      </span>
    {/each}
  {/if}
  <EvidenceLink anchor="investability" />
</div>

<style>
  .live {
    border-color: color-mix(in srgb, var(--wa) 60%, transparent);
  }
  .dead {
    border-color: color-mix(in srgb, var(--u15) 60%, transparent);
  }
  .mob-closed,
  .mob-restricted {
    border-color: color-mix(in srgb, var(--u15) 60%, transparent);
  }
</style>
