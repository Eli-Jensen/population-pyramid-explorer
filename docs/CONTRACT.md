# Module contract (M0) — the interfaces every agent builds against

> **AMENDED 2026-09-04 after plan approval (see the AMENDMENTS section at the end; it overrides anything above it that conflicts).** Repo/package renamed to `population-pyramid-explorer` / `pyramid_explorer`. DuckDB is the pipeline store; `trend`/`path` metrics exist; commands are `make` targets.

Read this before touching any file. `docs/PLAN.md` (with the DECISIONS block at the top) is the
specification; this file pins the *interfaces* so modules written in parallel fit together.
If you must deviate, change this file in the same commit and say so in your report.

## 0. Ground rules
- Python 3.12, `uv`. All deps are already declared in `pyproject.toml` (incl. `duckdb>=1.4`); **do not edit pyproject.toml**
  (the `embed` group has torch/transformers/scikit-learn; use `uv run --group embed …` for embedding code).
- Every module has a docstring, type hints, and pytest tests under `tests/`. Tests must run in `uv run pytest`
  without network (`@pytest.mark.network` for anything that fetches; `@pytest.mark.slow` for full-corpus runs;
  `@pytest.mark.embed` for anything importing torch).
- Never hardcode absolute paths; use `pyramid_explorer.paths`.
- Determinism: every random choice takes `seed=0` by default. No wall-clock in outputs except `meta.built`.
- Do not `git commit`; the orchestrator commits between waves.
- `docs/CONTRACT.md` is the truth for names. Ownership is listed in §7 — do not edit files you do not own;
  if you need a change in someone else's module, write a TODO in your report instead.

## 1. Corpus conventions
- **Entities**: countries first (all 237 WPP2024 `Country/Area` rows, `id` = ISO3, incl. `TWN`, `XKX`), sorted by `id`;
  then aggregates (`id = agg-{locid}`, e.g. `agg-900` World) sorted by `id`. This order is *the* corpus order.
- **Row index**: `row = entity_idx * 151 + (year - 1950)`, years 1950..2100 inclusive (151), entity-major.
- **Share vector** `s42 = [m_0, m_5, …, m_100, f_0, …, f_100] / T`, `T = Σm + Σf` (thousands). Rows sum to 1.
  Bin `k` (0..20) has `age_start = 5k`; bin 20 is 100+. Male = indices 0..20, female = 21..41.
- **s21** (total-only) `= s42[:21] + s42[21:]`.
- Files under `data/processed/` (gitignored, rebuilt by `scripts/build_data.py`):
  | file | shape / schema |
  |---|---|
  | `pyramids.parquet` | long: `id` str, `locid` int, `year` int, `age_start` int, `pop_male` f64, `pop_female` f64 (thousands, patched) |
  | `entities.json` | list of entity dicts in corpus order (schema §2) |
  | `corpus_keys.parquet` | `row` int, `id` str, `locid` int, `year` int, `type` `'country'|'aggregate'`, `pop_total` f64 (thousands) — one row per corpus row, in row order |
  | `corpus_s42.npy` | float64 `[n_rows, 42]` |
  | `corpus_u16.npy` | uint16 `[n_rows, 42]`, every row sums to exactly 65535 |
  | `sigma.json` | `{metric: {"2": σ, "1": σ}}` (see §4) |
- A **provisional corpus** (237 countries only, unpatched, from pyramid-econ) is already in `data/processed/`
  so metrics/embedding/eval agents can run on real data today. `scripts/build_data.py` overwrites it.

## 2. Entity dict (entities.json)
```
{ "id": "JPN", "locid": 392, "iso2": "JP", "name": "Japan", "short_name": "Japan", "slug": "japan",
  "aliases": ["jpn", "japan"], "type": "country", "subregion_locid": 906, "region_locid": 935,
  "sdg_region_locid": 1832, "income_group": "HIC", "dev_group": "more", "pop_2026": 122427.7,
  "is_micro": false, "axis_pct": 10, "notes": [] }
{ "id": "agg-900", "locid": 900, "iso2": null, "name": "World", "short_name": "World", "slug": "world",
  "aliases": ["world"], "type": "aggregate", "agg_kind": "world", "members": ["AFG", …], … }
```
`slugify` = NFKD → strip combining marks → lowercase → `[^a-z0-9]+` → `-` → trim. Both the UN-name slug and the
short-name slug are aliases; `pipeline/names.yaml` overrides short names and adds aliases (`usa`, `south-korea`, …).
`is_micro` = `pop_2026 < 100` (thousands). `axis_pct` ∈ {10, 12, 14, 17} = smallest covering the entity's max
single-sex bin share over all years.

## 3. Module APIs (Python, `src/pyramid_explorer/`)
```python
# data/wpp.py  (A1)
def load_locations() -> pd.DataFrame                       # pipeline/locations.parquet (from WPP2024_F01_LOCATIONS.xlsx sheet DB)
def load_raw_population(patched: bool = True) -> pd.DataFrame
    # columns: locid, name, iso3 (None for aggregates), loctype (LocTypeName), year, age_start, pop_male, pop_female
    # ALL locations (countries + aggregates), 1950..2100, 21 bins; Togo patch + aggregate recompute applied when patched=True

# patches.py  (A1)
def apply_togo_patch(raw: pd.DataFrame, update_csv: Path, locations: pd.DataFrame) -> tuple[pd.DataFrame, dict]
    # returns (patched frame, {"id": "togo-2026-01-19", "locids": [768], "recomputed_aggregates": [locids…]})

# entities.py  (A1)
def slugify(name: str) -> str
def build_entities(raw: pd.DataFrame, locations: pd.DataFrame) -> list[dict]   # corpus order; reads pipeline/names.yaml
def load_entities() -> list[dict]                                                # data/processed/entities.json
def save_entities(entities: list[dict]) -> Path

# shapes.py  (A1)
def build_pyramids(patched: bool = True) -> pd.DataFrame                      # writes data/processed/pyramids.parquet
def load_pyramids() -> pd.DataFrame
def build_corpus(pyr: pd.DataFrame, entities: list[dict]) -> tuple[np.ndarray, pd.DataFrame]
    # (s42 float64 [n,42], keys df per §1); ALSO writes corpus_s42.npy + corpus_keys.parquet
def load_corpus() -> tuple[np.ndarray, pd.DataFrame]                          # (s42, keys)
def row_index(keys: pd.DataFrame) -> dict[tuple[str, int], int]              # (id, year) -> row

# quantise.py  (A2)
def shares_to_u16(s42: np.ndarray) -> np.ndarray      # uint16 [n,42]; largest-remainder rounding; rows sum to exactly 65535
def u16_to_shares(u: np.ndarray) -> np.ndarray        # float32 u/65535

# delta.py  (A2)
def encode_blob(u16: np.ndarray, n_years: int = 151) -> bytes
    # rows entity-major (n_rows % n_years == 0). d[r] = (u[r] - u[r-1]) & 0xFFFF within an entity, prev = 0 for
    # each entity's first row. Then byte-transpose (all low bytes, then all high bytes) and gzip level 9. NO header.
def decode_blob(blob: bytes, n_rows: int, n_years: int = 151) -> np.ndarray   # exact round trip
def layout_sizes(u16: np.ndarray, n_years: int = 151) -> dict[str, int]      # {"raw_gz","delta_gz","zigzag_gz","delta_transposed_gz"} bytes, for the build report

# features.py  (B)
FEATURE_NAMES: list[str]   # median_age, mean_age, u15, wa, o65, o80, child_dep, old_dep, total_dep,
                           # base_slope_20 (s0/s20), base_slope_10 (s0/s10), modal_bin, wa_sex_ratio, stage, flag_male_skew, flag_urn
def features(s42: np.ndarray) -> pd.DataFrame        # one row per input row; stage ∈ {expansive, constrictive, stationary}
def zscores(feat: pd.DataFrame, reference_rows: np.ndarray) -> pd.DataFrame    # standardise against a reference set (focal-year countries)

# metrics.py  (B)
METRICS: list[str]   # 'blend' (default), 'l2', 'w1', 'l2s', 'hel', 'feat', 'w1sex', 'w1bal', 'clr'
def distances(metric: str, q: np.ndarray, X: np.ndarray, *, sex: str = "2", sigma: dict | None = None,
              feats: pd.DataFrame | None = None, emb: np.ndarray | None = None, q_row: int | None = None) -> np.ndarray
    # q [42], X [n,42] -> float32 [n]. sex "2" = two-sex (42-d), "1" = total only (s21).
    # metric 'visual:<model>' uses emb [n,64] float (cosine distance) and q_row to pick the query's embedding.
def fit_sigma(X: np.ndarray, keys: pd.DataFrame, entities: list[dict], seed: int = 0, n_pairs: int = 20000) -> dict
    # {metric: {"2": σ, "1": σ}}: median distance over random same-year COUNTRY pairs with pop ≥ 100k (thousands ≥ 100)
def decompose(metric: str, q: np.ndarray, x: np.ndarray, *, sex: str, sigma: dict) -> dict
    # {"d", "l2_part", "w1_part", "w1_years", "top_bins_l2": [(bin_idx, contribution)…], "top_bins_w1": […]}

# search.py  (B)
@dataclass
class Query: id: str; year: int; mode: str = "same"          # same|near|range|any
    n: int = 10; from_year: int | None = None; to_year: int | None = None
    era: str = "obs"; scope: str = "c"; minpop: float = 100.0  # minpop in thousands; era obs|all; scope c|all
    metric: str = "blend"; sex: str = "2"; k: int = 5; div: float = 2.0; current_year: int = 2026
@dataclass
class Result: id: str; year: int; row: int; d: float; rank_raw: int; dy: int
def candidate_mask(keys: pd.DataFrame, entities: list[dict], q: Query, last_observed_year: int = 2023) -> np.ndarray
    # bool [n_rows]; excludes own entity; applies year mode, era (obs = year ≤ max(last_observed_year, current_year)
    # unless q.year > current_year → all), scope, minpop (candidate's own-year pop)
def similar(X, keys, entities, q: Query, sigma: dict, *, feats=None, emb=None) -> list[Result]   # dedupe per entity (best year), sorted by d, len ≤ k
def different(X, keys, entities, q: Query, sigma: dict, *, feats=None, emb=None) -> list[Result]  # MMR: pool = min(ceil(0.25·|cand|), 2000) farthest; greedy argmax d(q,x)+div·min_s d(x,s); div=0 ⇒ plain farthest-k; dedupe per entity first
def best_year_per_entity(X, keys, entities, q: Query, sigma: dict, **kw) -> pd.DataFrame   # id, best_year, d, dy, boundary_hit(bool)
def isolation(X, keys, entities, year: int, metric: str, sigma: dict, *, sex="2", k=5, minpop=100.0) -> pd.DataFrame  # id, isolation (mean d to k nearest same-year countries)

# bands.py  (A2)
GRID: list[float]  # [0,1,2,5,10,15,20,25,30,40,50,60,70,75,80,85,90,95,97,98,99,99.5,99.9,100] (24 points)
def build_bands(X, keys, entities, sigma, metrics: list[str], *, seed=0, n_pairs=2000, current_year=2026, last_observed_year=2023) -> dict
    # {"same": {metric: {sex: {year: [24 floats]}}}, "cross": {metric: {sex: {era: {decade: [24]}}}}, "best": {…same shape as cross…}}
def serialize_bands(bands: dict) -> bytes          # uint32 LE json-index length + utf8 JSON {name: [offset, count]} + float32 LE values
def band_label(d: float, quantiles: list[float]) -> str   # 'very_close' ≤p5 · 'close' ≤p25 · 'typical' · 'far' ≥p75 · 'extreme' ≥p95

# export.py  (A2)
def write_web_data(*, entities, keys, s42, u16, bands: dict | None, sigma: dict, patches: list[dict],
                   emb: dict[str, np.ndarray] | None = None, out_root: Path | None = None) -> dict   # returns build report (also written to data/out/build-report.json)
    # Writes web/public/data/wpp2024/ (wiped first): years.{sha8}/{year}.u16, pyramids.{sha8}/{id}.u16, shares.{sha8}.d16z,
    # shares.{sha8}.u16, totals.{sha8}.f32, bands.{sha8}.bin, bands_default.{sha8}.bin, emb/{model}.{sha8}.f16, NOTICE;
    # and web/src/data/entities.json + meta.json. Asserts payload budgets (PLAN §3.4) and raises on violation.

# render.py  (C)
def render_canon2(s42: np.ndarray, size: int = 336) -> np.ndarray   # uint8 [size,size,3]; 21 rows of size/21 px, 100+ on top;
    # white bg; male bars grow LEFT from centre in steelblue (70,130,180), female grow RIGHT in (238,121,137); half-width = 17 % share; no gaps, no text
def render_canon1(s42: np.ndarray, size: int = 294) -> np.ndarray   # total-only: s21/2 mirrored both sides, grey (110,110,110)
def style_hash() -> str                                              # sha256 over the renderer source + constants
def render_corpus(s42: np.ndarray, kind: str, out: Path | None = None) -> np.ndarray   # uint8 [n,size,size,3]; saves data/renders/{kind}.npy

# embed.py  (C)
MODELS: dict[str, dict]   # 'siglip2-base-naflex': hf 'google/siglip2-base-patch16-naflex', patch 16, max_num_patches 441, render canon2@336
                          # 'dinov2-base': hf 'facebook/dinov2-base', patch 14, do_resize=False, do_center_crop=False, render canon2@294
def embed(model: str, images: np.ndarray, *, batch: int = 32, device: str = "mps") -> np.ndarray   # float32 [n,D], L2-normalised
def processor_check(model: str, images: np.ndarray) -> dict     # asserted shapes (naflex spatial_shapes==(21,21), pixel_attention_mask.sum()==441; dinov2 pixel_values (294,294)) + max abs pixel diff vs input ≤ 1/255
def pca64(E: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]   # (Z float16 [n,64], mean [D], proj [D,64]); NO whitening
# outputs: evals/embeddings/{model}.npy (float32 full-dim), {model}.pca64.npy (float16), {model}.meta.json (committed)
```

## 4. Metric definitions (B implements; A2/D consume)
- `l2` = ‖s42_a − s42_b‖₂ (sex="1": on s21).
- `w1s` (per-sex W1, years) = 5·Σ_k(|CM_a,k−CM_b,k| + |CF_a,k−CF_b,k|), CM/CF = cumsum of shares-of-total per sex.
- `w1` = 5·Σ_k|C21_a,k − C21_b,k| (total age distribution, years; sex-blind).
- `blend` (default) = 0.5·l2/σ_l2 + 0.5·w1s/σ_w1s (sex="2"); sex="1": 0.5·l2(s21)/σ'_l2 + 0.5·w1/σ'_w1.
- `l2s` = l2 after Gaussian smoothing along age with kernel [.054,.242,.399,.242,.054] (nearest padding), per sex.
- `hel` = Hellinger on s42. `feat` = L2 on z-scored FEATURE columns (numeric ones). `w1sex` = w1s alone.
- `w1bal` = w1 + 50·Σ_k w_k|r_a,k − r_b,k| with r = male share of bin and the SYMMETRIC weight `w_k = ½(s21_a,k + s21_b,k)`
  (mean of the two bin shares, so the metric is the same from either side; pinned by `tests/test_metrics.py::test_w1bal_formula_pinned_symmetric_weights`).
- `clr` = L2 on centred-log-ratio of s42 (ε = 1e-6). Evaluation-only.
- σ from `fit_sigma` (median random same-year country pairs ≥ 100k). Store in `data/processed/sigma.json`.

## 5. Web binary formats (little-endian; A2 writes, the M1 web agent reads)
- `years.{sha8}/{year}.u16`: n_entities × 42 uint16 (entity order) then n_entities float32 totals (thousands).
- `pyramids.{sha8}/{id}.u16`: 151 × 42 uint16 then 151 float32 totals.
- `shares.{sha8}.u16`: n_rows × 42 uint16 (corpus order). `totals.{sha8}.f32`: n_rows float32.
- `shares.{sha8}.d16z`: `encode_blob` bytes (gzip stream; deliberately NO .gz extension).
- `emb/{model}.{sha8}.f16`: n_rows × 64 float16. `bands*.bin`: `serialize_bands` bytes.
- `meta.json`: `{revision, patches, built, last_observed_year, n_entities, n_countries, n_rows, files: {logical→path}, sigma, kernel, budgets, sizes, attribution}`.
- `{sha8}` = first 8 hex of sha256 over the file's bytes (directories: over the concatenation in sorted order).

## 6. Scripts (`scripts/`)
| script | owner | does |
|---|---|---|
| `fetch_data.py --from DIR` | A1 | copy present raw files from DIR, download the rest per `pipeline/manifest.json` (sha256-verified), convert LOCATIONS.xlsx → `pipeline/locations.parquet` |
| `build_data.py [--no-patches] [--emb evals/embeddings/M.pca64.npy …]` | A2 | pyramids → corpus → u16 → σ → bands → export; prints the build report |
| `query.py ID YEAR [--mode …] [--metric …]` | B | prints twins, opposites (with raw ranks), time-shift table, decomposed reasons |
| `render_canonical.py [--kind canon2\|canon1] [--size N]` | C | → `data/renders/{kind}_{size}.npy` |
| `embed_images.py --model M […]` | C | → `evals/embeddings/` (+ processor assertions, throughput) |
| `fetch_labels.py` | D | external label sets → `evals/labels/*.yaml` |
| `eval_similarity.py [--full]` | D | protocol gates G1/G2/G4/opposites/method agreement over all metrics (+visual) → `evals/RESULTS.md`, `evals/verdicts.json` |
| `m0.py` | integration | runs the chain in order |

## 7. Ownership (M0, wave 1)
- **A1 ingest**: `data/wpp.py`, `entities.py`, `patches.py`, `shapes.py`, `pipeline/{manifest.json,names.yaml,locations.parquet}`, `scripts/fetch_data.py`, `tests/test_{entities,patches,shapes,wpp}.py`
- **A2 export**: `quantise.py`, `delta.py`, `bands.py`, `export.py`, `scripts/build_data.py`, `tests/test_{quantise,delta,bands,export}.py`
- **B metrics**: `features.py`, `metrics.py`, `search.py`, `scripts/query.py`, `tests/test_{features,metrics,search}.py`
- **C render/embed**: `render.py`, `embed.py`, `scripts/{render_canonical,embed_images}.py`, `tests/test_{render,processors}.py`, `evals/image_embeddings.md`, `evals/embeddings/*.meta.json`
- **D eval protocol**: `scripts/{fetch_labels,eval_similarity}.py`, `evals/{protocol.md,canonical_groups.yaml,time_shift.yaml,labels/*}`, `tests/test_protocol.py`


---

# AMENDMENTS (2026-09-04, approved plan `~/.claude/plans/moonlit-wandering-cocoa.md`) — these override the sections above

## A. Database (DuckDB) — owner A1
- `src/pyramid_explorer/schema.sql` (committed DDL + views + macros) and `src/pyramid_explorer/db.py` (the ONLY module importing duckdb). File `data/processed/explorer.duckdb` (gitignored) is **always rebuilt from scratch** by `scripts/build_data.py`; it is a pure function of manifest-pinned raw files + `pipeline/*.yaml` + code. No ORM, no migrations: `build_meta.schema_version` mismatch ⇒ rebuild.
- **Files under `data/processed/` (CONTRACT §1) are EXPORTS of the DB**, written by `db.export_processed(con)`; every other module keeps reading those files (B/C/D untouched). Extra exports: `indicators.parquet` (`entity_id, year, indicator_id, source_id, value, is_forecast` — redistributable sources only), `coverage.parquet`, `entity_years.parquet`.
- Rule: **numpy implements metrics; SQL asks questions** (coverage, joins, provenance, ad-hoc kNN, cross-checks in tests). Brute-force `array_cosine_distance` over `FLOAT[64]` (2 ms at 42k rows) — no vector index.
- Tables (see the plan §5 for the full DDL): `source` (id, family, name, url, vintage, licence, **redistributable**, attribution, sha256, bytes, fetched_at), `patch`, `build_meta`, `location` (all 326 UN rows), `entity`, `entity_alias`, `entity_membership`, `sovereignty` (curated `pipeline/sovereignty.yaml`, may be empty), `pop_age5` (PATCHED, long, canonical) + `pop_age5_vanilla`, `pyramid` (materialised wide: row, entity_id, year, total, `s42 DOUBLE[42]`, `cdf42 DOUBLE[42]`), `corpus_u16`, `sigma`, `indicator`, `indicator_value`, `source_entity_map` (WEO `UVK→XKX`, `WBG→PSE`…), `source_orphan` (codes with no entity, never silently dropped), `coverage` (derived: entity × series × source: first/last year, n_obs, n_gaps, last_actual), `embedding_model`, `embedding` (`FLOAT[768]`), `embedding_pca64` (`FLOAT[64]`), eval mirrors; views `corpus_entity`, `corpus_row` (**the row index is derived here: `entity_idx*151 + (year-1950)`, never stored by hand**), `indicator_public` (the ONLY relation export may read indicators from), `entity_years`; macros `l1`, `w1s`, `blend_d` (cross-check only).
- `db.py` API: `connect(path=None, *, read_only=False, rebuild=False)`, `ingest_sources`, `ingest_locations`, `insert_entities`, `ingest_sovereignty`, `ingest_pop_age5(con, vanilla, patched, patch)`, `ingest_wpp_indicators`, `ingest_indicators(con, family, source_id, long_df) -> {rows, orphans}`, `refresh_derived` (builds `pyramid` + `coverage`, runs SQL sanity checks: member sums 0.01 % on vanilla, patch identity), `write_u16`, `write_sigma`, `ingest_embeddings(con, model, full_npy, pca_npy, meta_json, keys)` (refuses on data_hash mismatch), `ingest_evals`; loaders `load_entities`, `load_corpus -> (s42, keys)`, `load_cdf`, `load_u16`, `load_embeddings(con, model, dim=64)`, `load_indicator`, `coverage`, `entity_years`, `knn(con, entity_id, year, *, model, k=10, where='TRUE')`; `export_processed`, `write_build_meta`, `diff_against(con, old_db)`. Arrow round-trip for ARRAY columns: `to_arrow_table().column(c).combine_chunks().flatten().to_numpy().reshape(-1, d)`.
- `scripts/build_data.py` order: connect(rebuild) → ingest_sources (sha256 vs `pipeline/manifest.json`) → ingest_locations → `wpp.load_raw_population(patched=False)` → `patches.apply_togo_patch` → `entities.build_entities(patched, …)` (**the PATCHED frame** — `pop_2026`, `is_micro`, `axis_pct` must describe the pyramids the site ships; amended after the fix wave, see §G) → `patches.restrict_to_entities` → insert_entities → ingest_sovereignty → ingest_pop_age5 → ingest_wpp_indicators → ingest_indicators for maddison/pwt/wdi/weo (each skipped with a WARNING if its raw file is absent) → refresh_derived → load_corpus → `quantise.shares_to_u16` → write_u16 → build_meta(data_hash = sha256(u16 bytes)) → `metrics.fit_sigma` → write_sigma → `--emb` ingest → export_processed → `bands.build_bands` → `export.write_web_data(...)` (signature unchanged) → build report (+ coverage summary, `--diff-against`). Flags: `[--no-patches] [--no-gdp] [--weo-vintage V] [--no-full-emb] [--emb NPY ...] [--diff-against DB]`.
- `shapes.build_pyramids/build_corpus/load_corpus` become thin wrappers over `db.*` (same files in/out); `entities.load_entities` reads the DB when present, else `entities.json`. New `scripts/sql.py "SELECT …"` (read-only). **Guard:** IMF WEO rows carry `source.redistributable = FALSE`; `tests/test_db.py::test_weo_never_exported` scans `data/processed/*.parquet`, `web/public/data/**`, `web/src/data/*.json` for WEO indicator ids / `NGDP`.
- Entity dict (§2) gains OPTIONAL keys (emitted from M3, not M0): `"coverage": {"gdppc_maddison": [1950, 2022], …}`, `"independent_since": 2011 | null`.

## B. Trend (trajectory) metrics — owner B
- `metrics.distances('trend', q, X, *, L=10, X_prev=None, q_prev=None, sigma)`: `Δ_q = s42(q,T) − s42(q,T−L)`, `Δ_c = s42(c,τ) − s42(c,τ−L)`, `d = ‖Δ_q − Δ_c‖₂ / σ_trend@L`. Implementation detail: callers pass the corpus and the row offset (`row − L` within the same entity; rows with `year − L < 1950` are masked out). `'path'`: mean of `d_blend` over aligned offsets `s ∈ {0, 5, …, L}`. `fit_sigma` gains `trend@5`, `trend@10`, `trend@20` (medians over random same-year country pairs ≥ 100k). `sigma.json` keys: `"trend@10": {"2": σ, "1": σ}` etc.
- `search.Query` gains `trend: str | None = None` (`'motion' | 'path'`), `L: int = 10`, and `mode` accepts `'today'` (sugar for `range [current_year, current_year]`). `candidate_mask` additionally requires `year − L ≥ 1950` when `trend` is set. `similar/different/best_year_per_entity` honour `trend`.
- `bands.build_bands` adds `same[trend@L]`, `cross[trend@L]`, `best[trend@L]` tables for L ∈ {5, 10, 20}.
- `scripts/query.py` flags: `--mode same|near|range|any|today`, `--trend motion|path`, `--L 5|10|20`, `--metric`, `--sex`, `--k`, `--div`, `--minpop`, `--era obs|all`, `--scope c|all`.
- Evaluation (D): temporal continuity for `trend@10` (adjacent windows of the same country must be nearest, self excluded), reported next to the snapshot metrics.

## C. Econ data loaders — owner F (new)
- `src/pyramid_explorer/data/{maddison,pwt,wdi,imf}.py` in the pyramid-econ style (`imf.fetch_vintage` copied from `~/Projects/pyramid-econ/src/pyramid_econ/data/imf.py`; `pwt.py` keeps `pop` and `rgdpe`). Each exposes `fetch() -> Path` (raw file under `data/raw/econ/`, sha256 recorded in `pipeline/econ_manifest.json`) and `load_long() -> DataFrame[code, year, indicator_id, value, is_forecast]` with upstream codes untouched (remapping happens in `db.ingest_indicators` via `pipeline/econ_iso3.yaml` / `source_entity_map`).
- Sources: Maddison 2023 (`https://dataverse.nl/api/access/datafile/421302`, sheet "Full data": countrycode, year, gdppc, pop; CC BY 4.0), PWT 11.0 (`~/Projects/pyramid-econ/data/raw/pwt/pwt110.xlsx` or dataverse 554105; sheet Data: countrycode, year, rgdpna, rgdpe, pop, hc, emp; CC BY 4.0), WDI (API v2 no key: `NY.GDP.PCAP.PP.KD`, `NY.GDP.MKTP.KD.ZG`, `SP.POP.TOTL`, `SP.POP.1564.TO.ZS`, `NY.GDP.TOTL.RT.ZS`; CC BY 4.0; verify licence page), WB OGHIST income classes (xlsx), IMF WEO 2025-04 (copy `~/Projects/pyramid-econ/data/processed/weo_202504.parquet`; **redistributable = FALSE**). Indicator ids: `gdppc_maddison`, `pop_maddison`, `rgdpna_pwt`, `rgdpe_pwt`, `pop_pwt`, `hc_pwt`, `gdppc_ppp_wdi`, `gdp_growth_wdi`, `pop_wdi`, `wa_share_wdi`, `rents_wdi`, `income_class_wb`, `gdppc_ppp_weo`, `real_gdp_growth_weo`, …
- `scripts/fetch_econ.py` (all sources, idempotent), `tests/test_econ_data.py` (remap fixtures; every mapped code ∈ entity ids; orphans recorded; windows on a toy series).
- ISO3 remaps (`pipeline/econ_iso3.yaml`): WEO `UVK→XKX`, `WBG→PSE`; WDI `XKX` ok, `PSE` ok, `CHI` (Channel Islands) → drop; Maddison drop `{CSK, SUN, YUG}` and any non-WPP code → `source_orphan` (assert against a fixed allowlist).

## D. Scripts / commands (replaces §6's command column with Makefile targets)
`make setup | setup-embed | data | build | build-nopatch | build-emb | test | test-slow | test-all | render | embed | eval | m0 | labels | backtest | query Q="…" | sql Q="…" | web | web-check | web-test | web-build | smoke | deploy | deploy-status | check-upstream | clean | distclean` — see `Makefile`. Docs and agent reports reference targets, not raw commands. Scripts added vs §6: `fetch_econ.py` (F), `sql.py` (A1), `m0.py` is replaced by `make m0`.

## E. Ownership (replaces §7)
- **A1 ingest + DB**: `data/wpp.py`, `entities.py`, `patches.py`, `shapes.py`, `db.py`, `schema.sql`, `pipeline/{manifest.json,names.yaml,locations.parquet,sources.yaml,sovereignty.yaml}`, `scripts/{fetch_data,sql}.py`, `tests/test_{entities,patches,shapes,wpp,db}.py`.
- **A2 export**: `quantise.py`, `delta.py`, `bands.py`, `export.py`, `scripts/build_data.py`, `tests/test_{quantise,delta,bands,export}.py`.
- **B metrics + search + trend**: `features.py`, `metrics.py`, `search.py`, `scripts/query.py`, `tests/test_{features,metrics,search}.py`.
- **C render + embed**: `render.py`, `embed.py`, `scripts/{render_canonical,embed_images}.py`, `tests/test_{render,processors}.py`, `evals/image_embeddings.md`, `evals/embeddings/*.meta.json`.
- **D eval protocol**: `scripts/{fetch_labels,eval_similarity}.py`, `evals/{protocol.md,canonical_groups.yaml,time_shift.yaml,labels/*}`, `tests/test_protocol.py`.
- **F econ data**: `data/{maddison,pwt,wdi,imf}.py`, `pipeline/{econ_manifest.json,econ_iso3.yaml}`, `scripts/fetch_econ.py`, `tests/test_econ_data.py`. (`db.ingest_indicators` is A1's; F calls it.)
- Shared read-only inputs for everyone: the provisional corpus in `data/processed/` (`corpus_s42.npy`, `corpus_keys.parquet`, `entities.json` — 237 countries, unpatched, `locid = -1`, entities marked `PROVISIONAL`), `docs/PLAN.md`, this file.

## F. Integration outcomes (2026-09-04, after the M0 wave-1 build) — recorded deviations that now ARE the contract
- **σ definition**: §4 stands (median over random SAME-year country pairs ≥ 100k, seed 0). Measured on the real corpus (280 entities, 42,280 rows): `σ_l2 = 0.0568 / 0.0781` (two-sex / total), `σ_w1sex = 7.62`, `σ_w1 = 6.17`, `trend@5/10/20 = 0.0182 / 0.0294 / 0.0396`, blend reference median ≈ 1.00. PLAN §3.5 / plan §9's ranges (`σ_L2 ∈ [.07, .10]`, `σ_W1 ∈ [9, 14]`) came from ANY-year pairs and are superseded; `tests/test_metrics.py` asserts same-year ranges (`σ_l2 ∈ [0.045, 0.10]`, `σ_w1sex ∈ [5, 14]`, blend median = 1 ± 0.05). `fit_sigma(..., *, write=False, path=None)` also returns `l2s/hel/clr/w1bal/feat/blend`.
- **`bands.*.bin` budget = 800 KB** (float32 values, full menu 8 snapshot + trend@5/10/20 × 2 sexes, 2,000 pairs/cell; measured 593 KB) and `bands_default` ≈ 19 KB; the first-paint budget (175 KB) is unchanged (measured 76 KB). `GRID` has 24 points (§3); `serialize_bands` index `[offset, count]` counts float32 ELEMENTS; names are `/`-joined (`same/blend/2/1990`, `cross/trend@10/1/obs/2020`); empty cells are omitted. `sizes.dir_total` (16 MB budget) excludes `emb/`; `dir_total_with_emb` is reported beside it and each `emb/*.f16` has its own 6 MB budget.
- **`meta.json` gains `verdicts`** (PLAN §3.6 one-writer rule): `build_data.py` reads `evals/verdicts.json` → `{data_hash, emb_meta_hash, stale, metrics: {metric: {verdict, provisional[, scope]}}}`. A verdicts file whose `data_hash` ≠ the build's is *stale*: every verdict is downgraded to `lab` with a WARNING (not a build failure — the chain is build → render → embed → eval → build-emb, so the first build after a data change necessarily precedes `make eval`); a `visual:<model>` verdict survives only when that model is passed via `--emb` and `emb_meta_hash[model] == sha256(<model>.meta.json)`. Absent file ⇒ key omitted. `meta.json` also carries `n_years`, `bands_grid`, `bands_format`.
- **`data_hash`** everywhere (`build_meta`, `verdicts.json`, `<model>.meta.json`) = sha256 over the little-endian uint16 corpus bytes (`quantise.shares_to_u16(s42)`), never over `corpus_s42.npy`; `db.ingest_embeddings` refuses a mismatch.
- **A1 signatures as built**: `db.ingest_wpp_indicators(con, indicators=None, update=None, patch=None)` (bare call loads the raw files itself); `db.write_build_meta(con, values=None, **kv)`; `db.load_pyramids(con, patched=True)`; `entities.build_entities(raw, locations, *, names=None, n_agg_range=(40, 44))`; `wpp.load_indicators*()` clip to 1950..2100; `export_processed` also writes `patches.json`, and `coverage.parquet` (like `indicators.parquet`) carries redistributable sources only — WEO coverage stays inside the DB (`test_weo_never_exported` scans every export). `entity_years` GDP spans count redistributable sources only.
- **Sources**: `pipeline/sources.yaml` has an `oghist` row + family (WB income classes, `income_class_wb`, ingested by `build_data.py` through `wdi.load_income_long` under source id `oghist`). `db.ingest_sources` de-duplicates `pipeline/econ_manifest.json` ids against `sources.yaml` rows by file name (`maddison2023 ≙ maddison-2023`, `pwt110 ≙ pwt-11.0`, `weo_2025-04 ≙ weo-2025-04`) and sums the WDI page files into the `wdi` row. A non-default `--weo-vintage V` goes through `imf.to_long(fetch_vintage(V), last_actual_year=int(V[:4]) − 1)`.
- **B additions**: `distances(..., L=10, X_prev=None, q_prev=None)`; `distances(sigma=None)` falls back to `DEFAULT_SIGMA`; `decompose(..., top=3)`; `zscores` returns the 13 numeric columns with `mu/sd` in `.attrs` + `zscore_vector`; `different()` pool floored at `k`; `best_year_per_entity.boundary_hit` is true on either era edge (the CLI prints `[at era edge]`, consumers may suppress it when `best_year == query year`). `scripts/query.py` extra flags: `--n`, `--from/--to`, `--current-year`, `--emb` (required for `visual:`).
- **C as built**: `render_corpus(s42, kind, size=None, out=None)` → `data/renders/{kind}_{size}.npy` + `.meta.json` (style hash + s42 sha; `embed_images.py --renders` refuses a mismatch); `processor_check` refuses non-canonical sizes; `embed(..., dtype='float16', progress=False)`, `pca64(E, k=64)`; `evals/embeddings/*.pca.npz` (200 KB/model) is written beside the meta and is not gitignored yet.
- **D as built**: `verdicts.json = {metric: {verdict, provisional, gates, numbers[, scope]}, data_hash, emb_meta_hash, _meta}`; G2(b) gated at the Hahn-Klimroth shape-family level, G2(e) Yoshida demoted to reported, `trend`/`path` verdicts from G1 only (`scope: trend-mode`); `visual:*` rows appear automatically for every aligned `evals/embeddings/*.pca64.npy`.
- The provisional corpus (§1, §E) is gone: `scripts/_provisional_corpus.py` was deleted once `make build` produced the real exports; `data/processed/` is now always the DB export.
- **Known, deliberately left**: `explorer.duckdb` ≈ 265 MB without / ≈ 900 MB with full-dim embeddings (ART index weight of composite TEXT keys); `feat` bands take ~30 s of `build_bands` (metrics recomputes `features(q)` per call; halved by the sex-blind aliasing in §G).

## G. Fix-wave outcomes (2026-09-04, after the three-lens adversarial review) — these also ARE the contract
- **Entities from the patched frame** (§A order above): `build_entities` runs AFTER `apply_togo_patch` on the patched frame, so `entities.pop_2026` equals the shipped 2026 pyramid total for TGO and the seven recomputed aggregates (previously vanilla, +1,150k). `tests/test_db.py` asserts `|pop_2026 − pop_total(2026)| < 1e-3` for every entity on the synthetic world (where the patch changes 2026) and on the real store.
- **Patch record names entities only**: `patches.restrict_to_entities(record, entities)` keeps entity locids in `recomputed_aggregates` (real: 900, 902, 903, 914, 941, 1500, 1834) and moves deny-listed unions (948, 1859, 5504 — recomputed in the frame, never shipped) to `recomputed_non_entities`; the DB `patch` table, `patches.json`, `meta.patches` and NOTICE all carry the filtered list. The patch note states that demographic indicators of recomputed aggregates remain UN-vanilla, and `db._sanity_checks` verifies `Σbins − pop_total_wpp == Σ_touched(patched − vanilla)` per year for them (tolerance 0.02k + 0.001k × 21 bins × members) instead of skipping the 1,057 rows.
- **`entity_years.sources`** lists redistributable sources only (WEO stays in the DB, like `coverage.parquet`); `test_weo_never_exported` scans text AND list columns case-insensitively for `weo|imf|ngdp` (binaries by exact token) and caught the pre-fix export.
- **`sdg_region_locid`** is aliased through `entities.SDG_ALIAS = {1830: 904, 1836: 927}` (deny-listed SDG duplicates → the shipped twin) and `build_entities` fails on any country group reference that is not an entity locid.
- **`make m0` = data build test render embed eval build-emb**; **`make test` = `pytest -m "not slow"`** (fast), `make test-slow` = `-m slow`, `make test-all` = everything incl. network.
- **DECISION 4 is machine-readable**: `verdicts.json` carries top-level `exposed_visual: {model, metric, C1_obs, alternates, rule}` (better observed-span C1); `build_data.load_verdicts` copies it into `meta.verdicts.exposed_visual` (`null` + WARNING when stale or the model is not shipped via `--emb`). A metric with a verdict above `lab` but no bands in this build (e.g. evaluation-only `clr`) is capped at `lab` with a WARNING, so every menu candidate in `meta.verdicts` has `same/<metric>` tables.
- **Opposites presets re-calibrated** (`search.DIV_PRESETS = {strict: 0, balanced: 0.5, spread: 2}`, `Query.div` default 0.5): on 199 anchors ≥ 100k at 2026 the MMR diversity term saturates early (β = 2 ≡ β = 4 on 85 % of anchors); mean top-5 Jaccard vs strict is 0.66 at β = 0.5 and 0.37 at β = 2. The formula (`argmax d(q,x) + β·min_s d(x,s)` over the farthest quartile) is unchanged. Diversity is over shape distance only: no β delivers Hahn-Klimroth-class or UN-region coverage (structural; recorded in RESULTS.md and PLAN §5). The pre-registered opposites test still runs at β = 2; a β sweep is reported beside it.
- **Bands**: sex-blind metrics (`w1`, `feat`, `visual:*`) are built once and their sex='1' tables alias the '2' tables; `serialize_bands` stores identical tables once and indexes them twice (a reader may ask for either name). `sizes.bands_tables` bytes are logical.
- **σ era tilt is documented, not changed**: `metrics.blend_balance` reports the median W1 share of `blend` per era (two-sex: observed 0.469 / nowcast 0.502 / projected 0.534; pooled 0.503) in the build report (`blend_w1_share`) and RESULTS.md; `DEFAULT_SIGMA` is the real-corpus set.
- **KC normalised P@10 dropped** from RESULTS/verdicts: every Korenjak-Černe cluster has ≥ 44 members so `min(10, |G|−1) = 10` and P@10 ≡ class agreement (protocol.md §2 note).
- **Paths**: `paths.PYRAMID_ECON_ROOT` (env `PYRAMID_ECON_ROOT`, default `~/Projects/pyramid-econ`) is the only place the sibling checkout is named; `pwt.py`/`imf.py` derive `LOCAL_COPY` from it and `scripts/fetch_econ.py --from DIR` (Makefile `ECON_FROM`) overrides it per run.
- **`scripts/query.py`**: ids resolve case-insensitively through ISO3 / slug / aliases; out-of-range years and `--metric trend|path` exit with a hint; the header prints the EFFECTIVE era (`all (query is a projection)`) and year window; the time-shift edge flag is suppressed when `best_year == query year`.
