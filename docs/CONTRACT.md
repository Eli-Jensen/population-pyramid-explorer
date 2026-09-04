# Module contract (M0) — the interfaces every agent builds against

Read this before touching any file. `docs/PLAN.md` (with the DECISIONS block at the top) is the
specification; this file pins the *interfaces* so modules written in parallel fit together.
If you must deviate, change this file in the same commit and say so in your report.

## 0. Ground rules
- Python 3.12, `uv`. All deps are already declared in `pyproject.toml`; **do not edit pyproject.toml**
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
- `w1bal` = w1 + 50·Σ_k w_k|r_a,k − r_b,k| with r = male share of bin, w_k = bin share (s21).
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
