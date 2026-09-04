"""TEMPORARY (M0 only): build a provisional corpus (237 countries, unpatched, locid=-1) from pyramid-econ's
parquet so the metrics / embedding / eval agents can work before scripts/build_data.py exists.
Run:  uv run --project ~/Projects/pyramid-econ python -c "import sys; sys.path.insert(0,'src'); exec(open('scripts/_provisional_corpus.py').read())"
Deleted once build_data.py produces the real corpus."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pyramid_explorer.paths import AGE_STARTS, DATA_PROCESSED, YEARS

src = Path.home() / "Projects/pyramid-econ/data/processed/wpp2024_population_age5.parquet"
df = pd.read_parquet(src)
ids = sorted(df.iso3.unique())
piv = df.pivot_table(index=["iso3", "year"], columns="age_start", values=["pop_male", "pop_female"]).reindex(
    pd.MultiIndex.from_product([ids, YEARS], names=["iso3", "year"]))
m = piv["pop_male"][AGE_STARTS].to_numpy()
f = piv["pop_female"][AGE_STARTS].to_numpy()
T = m.sum(1) + f.sum(1)
s42 = np.concatenate([m, f], 1) / T[:, None]
assert np.isfinite(s42).all() and np.allclose(s42.sum(1), 1)
keys = pd.DataFrame({"row": np.arange(len(T)), "id": np.repeat(ids, len(YEARS)), "locid": -1,
                     "year": np.tile(YEARS, len(ids)), "type": "country", "pop_total": T})
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
np.save(DATA_PROCESSED / "corpus_s42.npy", s42)
keys.to_parquet(DATA_PROCESSED / "corpus_keys.parquet", index=False)
pop26 = keys[keys.year == 2026].set_index("id").pop_total
ents = [{"id": i, "locid": -1, "iso2": None, "name": i, "short_name": i, "slug": i.lower(), "aliases": [i.lower()],
         "type": "country", "pop_2026": float(pop26[i]), "is_micro": bool(pop26[i] < 100), "axis_pct": 10,
         "notes": ["PROVISIONAL"]} for i in ids]
(DATA_PROCESSED / "entities.json").write_text(json.dumps(ents, indent=0))
print("provisional corpus:", s42.shape, "entities", len(ents), "micro", sum(e["is_micro"] for e in ents))
