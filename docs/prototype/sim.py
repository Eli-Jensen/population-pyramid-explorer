import numpy as np, pandas as pd, time
df = pd.read_parquet('/Users/elijensen/Projects/pyramid-econ/data/processed/wpp2024_population_age5.parquet')
print('entities', df.iso3.nunique(), 'years', df.year.min(), df.year.max(), 'bins', df.age_start.nunique())
# pivot to (iso3, year) -> 21 male + 21 female
piv = df.pivot_table(index=['iso3','year'], columns='age_start', values=['pop_male','pop_female'])
male = piv['pop_male'].to_numpy(); female = piv['pop_female'].to_numpy()
tot = (male+female).sum(1, keepdims=True)
keys = piv.index.to_frame(index=False)
keys['popk'] = tot[:,0]
X = np.concatenate([male/tot, female/tot], 1).astype(np.float32)   # 42-dim shares
A = (male+female)/tot                                              # 21-dim age dist
CDF = np.cumsum(A, 1)
print('N pyramids', len(X), 'X bytes f32', X.nbytes/1e6, 'MB')
idx = {(r.iso3, r.year): i for i, r in enumerate(keys.itertuples())}
names = {r.iso3:r.iso3 for r in keys.itertuples()}
def w1(i, mask):            # Wasserstein-1 on age dist, in years of age (bin width 5)
    return 5*np.abs(CDF[mask]-CDF[i]).sum(1)
def cos(i, mask):
    a = X[i]; B = X[mask]
    return 1 - (B@a)/(np.linalg.norm(B,axis=1)*np.linalg.norm(a)+1e-12)
def l2(i, mask):
    return np.linalg.norm(X[mask]-X[i], axis=1)
def w1_sex(i, mask):        # W1 on male + W1 on female (each normalized to its own sex total)
    cm = np.cumsum(male/male.sum(1,keepdims=True),1); cf = np.cumsum(female/female.sum(1,keepdims=True),1)
    return 5*(np.abs(cm[mask]-cm[i]).sum(1)+np.abs(cf[mask]-cf[i]).sum(1))/2 + 100*np.abs((male/tot).sum(1)[mask]-(male/tot).sum(1)[i])
METRICS = {'W1_age': w1, 'cosine42': cos, 'L2_42': l2, 'W1_sex+ratio': w1_sex}
def query(iso, year, metric, mode='same', k=5, minpop=1000, years=None):
    i = idx[(iso, year)]
    if mode=='same': mask = (keys.year==year).to_numpy().copy()
    elif mode=='any': mask = np.ones(len(keys), bool)
    else: mask = keys.year.between(*years).to_numpy().copy()
    mask &= (keys.iso3!=iso).to_numpy() & (keys.popk>=minpop).to_numpy()
    d = METRICS[metric](i, mask); sub = keys[mask].copy(); sub['d']=d
    best = sub.sort_values('d').drop_duplicates('iso3')
    return best.head(k), best.tail(k).iloc[::-1]
for iso, year in [('JPN',2026),('NER',2026),('QAT',2026),('USA',2026),('KOR',2050)]:
    for m in ['W1_age','cosine42','W1_sex+ratio']:
        s, dfar = query(iso, year, m)
        fmt = lambda t: ', '.join(f"{r.iso3}({r.d:.3g})" for r in t.itertuples())
        print(f"{iso} {year} [{m}] SAME-YEAR  similar: {fmt(s)}\n{' '*len(iso)} {' '*4} {' '*(len(m)+2)}            different: {fmt(dfar)}")
    s, dfar = query(iso, year, 'W1_age', mode='any')
    print(f"{iso} {year} [W1_age] ANY-YEAR   similar: {', '.join(f'{r.iso3}-{r.year}({r.d:.3g})' for r in s.itertuples())}")
    print()
# temporal continuity: is (iso, year±1) the nearest among same-country rows?
ok=0; n=0
for iso in ['JPN','NER','USA','BRA','DEU','IND']:
    for year in range(1960, 2090, 10):
        i = idx[(iso,year)]; mask=(keys.iso3==iso).to_numpy().copy(); mask[i]=False
        d = w1(i, mask); sub = keys[mask]; nn = sub.iloc[np.argmin(d)]
        n+=1; ok += abs(nn.year-year)==1
print('temporal continuity (W1_age): nearest same-country row is an adjacent year in', ok, '/', n)
# timing: brute force one query over all 36k
t=time.time(); 
for _ in range(20): w1(idx[('JPN',2026)], np.ones(len(keys),bool))
print('W1 over all pyramids: %.2f ms/query' % ((time.time()-t)/20*1000))
