-- population-pyramid-explorer DuckDB store (CONTRACT AMENDMENTS §A). Applied by db.connect() on a
-- fresh file; the file is always rebuilt from scratch (no migrations). SCHEMA_VERSION lives in db.py
-- and is written to build_meta; a mismatch means "rebuild".

CREATE TABLE source (
  id TEXT PRIMARY KEY, family TEXT NOT NULL, name TEXT, url TEXT, vintage TEXT, licence TEXT,
  redistributable BOOLEAN NOT NULL, attribution TEXT, sha256 TEXT, bytes BIGINT, fetched_at DATE);
CREATE TABLE patch (
  id TEXT PRIMARY KEY, source_id TEXT REFERENCES source(id), applied BOOLEAN, locids INTEGER[],
  recomputed_aggregates INTEGER[], note TEXT);
CREATE TABLE build_meta (key TEXT PRIMARY KEY, value TEXT);

-- WPP2024_F01_LOCATIONS.xlsx sheet DB (pipeline/locations.parquet), original column names.
CREATE TABLE location (
  "Index" INTEGER, "Location" TEXT, "Notes" TEXT, "LocID" INTEGER PRIMARY KEY, "ISO3_Code" TEXT, "ISO2_Code" TEXT,
  "SDMX_Code" TEXT, "LocType" INTEGER, "LocTypeName" TEXT, "ParentID" INTEGER, "WorldID" INTEGER,
  "SubRegID" INTEGER, "SubRegName" TEXT, "SDGSubRegID" INTEGER, "SDGSubRegName" TEXT, "SDGRegID" INTEGER,
  "SDGRegName" TEXT, "GeoRegID" INTEGER, "GeoRegName" TEXT, "MoreDev" INTEGER, "LessDev" INTEGER,
  "LeastDev" INTEGER, "oLessDev" INTEGER, "LessDev_ExcludingChina" INTEGER, "LLDC" INTEGER, "SIDS" INTEGER,
  "WB_HUMIC" INTEGER, "WB_LLMIC" INTEGER, "WB_HIC" INTEGER, "WB_LMIC" INTEGER, "WB_MIC" INTEGER,
  "WB_MUIC" INTEGER, "WB_MLIC" INTEGER, "WB_LIC" INTEGER, "WB_NoIncomeGroup" INTEGER,
  "TotPop2024LessThan1k" TEXT, "TotPop2024LessThan90k" TEXT);

CREATE TABLE entity (
  id TEXT PRIMARY KEY, locid INTEGER UNIQUE NOT NULL, type TEXT NOT NULL CHECK (type IN ('country', 'aggregate')),
  iso2 TEXT, name TEXT NOT NULL, short_name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, agg_kind TEXT,
  parent_locid INTEGER, subregion_locid INTEGER, region_locid INTEGER, sdg_region_locid INTEGER,
  income_group TEXT, dev_group TEXT, pop_2026 DOUBLE, is_micro BOOLEAN, axis_pct SMALLINT,
  un_notes TEXT[], doc JSON NOT NULL);                       -- doc = the full CONTRACT §2 dict
CREATE TABLE entity_alias (alias TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id), kind TEXT);
CREATE TABLE entity_membership (
  agg_id TEXT REFERENCES entity(id), member_id TEXT REFERENCES entity(id), PRIMARY KEY (agg_id, member_id));
CREATE TABLE sovereignty (
  entity_id TEXT PRIMARY KEY REFERENCES entity(id), state_since SMALLINT, predecessor TEXT, event TEXT,
  note TEXT, ref TEXT);

-- Population by 5-year age group and sex, thousands, 1 July. pop_age5 is PATCHED and canonical;
-- pop_age5_vanilla holds the unpatched UN rows for the same entities.
CREATE TABLE pop_age5 (
  entity_id TEXT REFERENCES entity(id), year SMALLINT, age_start SMALLINT, pop_male DOUBLE, pop_female DOUBLE,
  source_id TEXT REFERENCES source(id), patch_id TEXT REFERENCES patch(id), PRIMARY KEY (entity_id, year, age_start));
CREATE TABLE pop_age5_vanilla (
  entity_id TEXT REFERENCES entity(id), year SMALLINT, age_start SMALLINT, pop_male DOUBLE, pop_female DOUBLE,
  source_id TEXT REFERENCES source(id), PRIMARY KEY (entity_id, year, age_start));

-- Materialised wide corpus (refresh_derived): row = corpus_row.row; cdf42 = per-sex cumsums of s42.
CREATE TABLE pyramid (
  row INTEGER PRIMARY KEY, entity_id TEXT NOT NULL, year SMALLINT NOT NULL, total DOUBLE NOT NULL,
  s42 DOUBLE[42] NOT NULL, cdf42 DOUBLE[42] NOT NULL, UNIQUE (entity_id, year));
CREATE TABLE corpus_u16 (row INTEGER PRIMARY KEY, u16 USMALLINT[42] NOT NULL);
CREATE TABLE sigma (metric TEXT, sex TEXT, value DOUBLE, PRIMARY KEY (metric, sex));

CREATE TABLE indicator (
  id TEXT PRIMARY KEY, family TEXT NOT NULL, code TEXT, name TEXT, unit TEXT, derived BOOLEAN DEFAULT FALSE, note TEXT);
CREATE TABLE indicator_value (
  entity_id TEXT REFERENCES entity(id), year SMALLINT, indicator_id TEXT REFERENCES indicator(id),
  source_id TEXT REFERENCES source(id), value DOUBLE, is_forecast BOOLEAN NOT NULL,
  PRIMARY KEY (entity_id, year, indicator_id, source_id));
CREATE TABLE source_entity_map (
  family TEXT, code TEXT, entity_id TEXT REFERENCES entity(id), note TEXT, PRIMARY KEY (family, code));
CREATE TABLE source_orphan (
  source_id TEXT, code TEXT, name TEXT, reason TEXT, n_rows INTEGER, first_year SMALLINT, last_year SMALLINT,
  PRIMARY KEY (source_id, code));
CREATE TABLE coverage (
  entity_id TEXT, series TEXT, source_id TEXT, first_year SMALLINT, last_year SMALLINT, n_obs INTEGER,
  n_gaps INTEGER, last_actual SMALLINT, PRIMARY KEY (entity_id, series, source_id));

CREATE TABLE embedding_model (
  model TEXT PRIMARY KEY, hf_id TEXT, checkpoint_sha TEXT, dim INTEGER, render_kind TEXT, render_size INTEGER,
  style_hash TEXT, processor_config JSON, asserted_shapes JSON, pca_mean FLOAT[768], pca_proj_sha TEXT,
  data_hash TEXT, created_at TIMESTAMP);
CREATE TABLE embedding (
  model TEXT REFERENCES embedding_model(model), entity_id TEXT, year SMALLINT, vec FLOAT[768],
  PRIMARY KEY (model, entity_id, year));
CREATE TABLE embedding_pca64 (
  model TEXT REFERENCES embedding_model(model), entity_id TEXT, year SMALLINT, vec FLOAT[64],
  PRIMARY KEY (model, entity_id, year));

-- Mirrors of evals/ files (loaded by ingest_evals; shapes intentionally loose).
CREATE TABLE eval_label_set (id TEXT PRIMARY KEY, name TEXT, source TEXT, vintage TEXT, note TEXT);
CREATE TABLE eval_label (set_id TEXT REFERENCES eval_label_set(id), entity_id TEXT, year SMALLINT, label TEXT,
  PRIMARY KEY (set_id, entity_id, year));
CREATE TABLE eval_triplet (id INTEGER PRIMARY KEY, anchor_id TEXT, anchor_year SMALLINT, a_id TEXT, a_year SMALLINT,
  b_id TEXT, b_year SMALLINT, choice TEXT, rater TEXT, stratum TEXT);
CREATE TABLE eval_verdict (metric TEXT, gate TEXT, value DOUBLE, verdict TEXT, data_hash TEXT, emb_meta_hash TEXT,
  PRIMARY KEY (metric, gate));

-- Views. corpus_row DERIVES the row index (entity_idx*151 + (year-1950)); nothing stores it by hand.
CREATE VIEW corpus_entity AS
  SELECT id AS entity_id, locid, type, row_number() OVER (ORDER BY (type = 'aggregate'), id) - 1 AS entity_idx
  FROM entity;
CREATE VIEW corpus_row AS
  SELECT (ce.entity_idx * 151 + (y.year - 1950))::INTEGER AS row, ce.entity_id, ce.entity_idx, ce.locid, ce.type,
         y.year::SMALLINT AS year
  FROM corpus_entity ce CROSS JOIN range(1950, 2101) y(year);
CREATE VIEW indicator_public AS
  SELECT iv.* FROM indicator_value iv JOIN source s ON s.id = iv.source_id WHERE s.redistributable;
CREATE VIEW entity_years AS
  SELECT e.id AS entity_id, e.type,
         p.first_year AS pyramid_first, p.last_year AS pyramid_last,
         g.first_year AS gdp_first, g.last_year AS gdp_last, g.last_actual AS gdp_last_actual,
         c.sources, s.state_since, s.predecessor
  FROM entity e
  LEFT JOIN (SELECT entity_id, min(first_year) AS first_year, max(last_year) AS last_year FROM coverage
             WHERE series = 'pyramid' GROUP BY 1) p ON p.entity_id = e.id
  LEFT JOIN (SELECT c.entity_id, min(c.first_year) AS first_year, max(c.last_year) AS last_year,
                    max(c.last_actual) AS last_actual FROM coverage c JOIN source s ON s.id = c.source_id
             WHERE c.series LIKE 'gdppc%' AND s.redistributable GROUP BY 1) g
         ON g.entity_id = e.id
  LEFT JOIN (SELECT c.entity_id, list(DISTINCT c.source_id ORDER BY c.source_id) AS sources
             FROM coverage c JOIN source s ON s.id = c.source_id WHERE s.redistributable GROUP BY 1) c
         ON c.entity_id = e.id                                 -- redistributable sources only: WEO stays in the DB
  LEFT JOIN sovereignty s ON s.entity_id = e.id;

-- Macros: cross-checks only; numpy (metrics.py) is the implementation.
CREATE MACRO l1(a, b) AS list_sum(list_transform(list_zip(a::DOUBLE[], b::DOUBLE[]), x -> abs(x[1] - x[2])));
CREATE MACRO w1s(ca, cb) AS 5 * l1(ca, cb);
CREATE MACRO blend_d(sa, ca, sb, cb, s_l2, s_w1) AS
  0.5 * array_distance(sa, sb) / s_l2 + 0.5 * w1s(ca, cb) / s_w1;
