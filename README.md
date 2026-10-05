# population-pyramid-explorer

**Find any country's demographic twins: the countries, and the years, whose population
pyramid has the same shape.**

A population pyramid shows how many people a country has at each age, men on one side
and women on the other. Its shape tells a story: births booming or collapsing, a
generation lost to war, migrants arriving to work, a society ageing. This explorer
covers every country and region in the UN's *World Population Prospects 2024*, from
1950 to projections out to 2100, and adds something other pyramid sites don't have:
**search by shape**.

**Live:** <https://eli-jensen.github.io/population-pyramid-explorer/>

## What you can do

- **Explore any country, any year.** Scrub from 1950 to 2100 and watch the pyramid
  change. Years after the last observation are UN projections and are marked as such.
- **Find its twins and opposites.** The countries whose pyramid looks most like it, or
  least like it, in the same year, nearby years, a range of years, or any year at all.
- **Time-shift.** Which past year of another country does today's pyramid match best?
  For example, South Korea in 2026 looks most like Japan in 2008, about 18 years behind.
- **Trajectory matching.** Instead of matching one snapshot, find the countries that
  moved the same way over 5, 10 or 20 years: who is on the path China was on in 1990?
- **Compare two pyramids** overlaid, as a difference, or side by side, with a "best year"
  shortcut that finds the year where they match most closely.
- **Economic context.** GDP per capita, recent growth, World Bank income group and
  demographic-dividend stage beside every pyramid, plus an optional market lens that
  shows what happened next to historical lookalikes (see below).
- **Export and share.** Download any pyramid or result list as PNG, SVG or CSV. Every
  view lives in the URL, so a link reproduces exactly what you see.

## How to use it

1. **Search for a country** on the home page (names, ISO codes and common short names
   all work), or start from the World or your own country.
2. **Drag the year scrubber** to move through time. The axes stay fixed so changes in
   shape are easy to see; switch between absolute numbers and percentages if you like.
3. **Look below the pyramid** for its closest twins and opposites. Change the search to
   *nearby years*, *a range* or *any year* to search across time, pick how many results
   you want, and filter out small countries.
4. **Open a result** to compare it with your country side by side, or jump to its own page.
5. **Turn on the market lens** (the toggle in the nav bar) to see what happened next to
   historical lookalikes. It's off by default.
6. **Share** with *Copy link*, or **export** an image or CSV from the export menu.

Some links to start with:

- Japan today: `/japan/2026`
- South Korea against its best-matching year of Japan: `/compare/south-korea/2026/japan/best`
- Niger, one of the youngest populations on Earth: `/niger/2026`
- The whole world in 2050: `/world/2050`

## How "similar" is measured

Each pyramid becomes 42 numbers: the share of the total population in each five-year
age group, for men and for women. Using shares rather than headcounts means a small
country can match a large one. The default **Shape** distance blends two views of
those numbers: how different the bars are, bin by bin, and how far the population is
*shifted in age* (an "earth-mover" distance, measured in years). Both are scaled so
that "typical" means the median gap between two random countries in the same year.

Each result shows *why* it matched: which age groups agree, which differ, and a
percentile band saying how unusual that closeness is. Other metrics are available
from the menu, including an experimental **Visual** option that compares what an AI
vision model *thinks* looks alike. The site's own evaluation found it less reliable
than the numeric metrics, and it's shipped for comparison. The [About page](https://eli-jensen.github.io/population-pyramid-explorer/about)
has the full method and the evaluation numbers.

## About the economic lens

It's tempting to think "this country looks like Japan did before its boom, so..." This
site tested that idea before showing anything. In a pre-registered backtest, the
countries whose pyramids most resembled past growth success stories grew no faster
than the typical country over the next decade: −0.19 percentage points a year against
the median, with a 95% confidence interval from −1.47 to +1.20. So **pyramid shape
alone is not a growth signal**.
The market lens therefore shows what happened as history, always next to a global
benchmark (VT) over the same window. It never ranks by return, makes forecasts, or
gives investment advice. The full evidence, including that null result, is on the
site's `/evidence` page and in [evals/econ/RESULTS.md](evals/econ/RESULTS.md).

## Data

- **Population:** United Nations, Department of Economic and Social Affairs, Population
  Division (2024). *World Population Prospects 2024* (medium variant): 237 countries
  and areas plus 43 regional, income and development groups, 1950–2100.
  [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/). The UN does not
  endorse this site.
- **Economy:** Maddison Project Database 2023, Penn World Table 11.0, and World Bank
  World Development Indicators and historical income classifications, all CC BY 4.0.
  Fund statistics are derived summaries (returns, drawdowns), never price series.

Full attributions are in [Credits & licences](#credits--licences) below and on the
site's About page.

## Run it locally

You need [uv](https://docs.astral.sh/uv/) (Python 3.12) and Node.js 20.19+ (CI uses 24).

```bash
git clone https://github.com/Eli-Jensen/population-pyramid-explorer.git
cd population-pyramid-explorer
make setup     # Python + web dependencies
make web       # http://localhost:5173/population-pyramid-explorer/
```

The built data snapshots are committed, so the site runs without downloading or
rebuilding anything. There's also a command-line query tool over the same data
(it needs a local build first, `make data build`):

```bash
make query Q="JPN 2026"                       # Japan's twins, opposites and time-shift table
make query Q="KOR 2026 --mode any"            # South Korea's best match in any year
```

Rebuilding the data, running the evaluations, the full URL reference, the data
format and deployment are all covered in the **[development guide](docs/DEVELOPMENT.md)**.
The original plan and the research behind it are in [docs/](docs/), and the evaluation
record is in [evals/RESULTS.md](evals/RESULTS.md).

## Credits & licences

- **Population data:** United Nations, Department of Economic and Social Affairs, Population Division (2024).
  *World Population Prospects 2024, Online Edition* (medium variant), including the 19 January 2026 interim
  update for Togo (aggregates containing Togo recomputed from members by this site; the UN did not revise
  aggregates). <https://population.un.org/wpp/> — © 2024 United Nations, licensed under
  [CC BY 3.0 IGO](https://creativecommons.org/licenses/by/3.0/igo/). Files under `web/public/data/` are
  reshaped, share-normalised and 16-bit-quantised derivatives, not the original UN files; the UN does not
  endorse this site. The full notice is `web/public/data/wpp2024/NOTICE` (also on `/about`).
- **Economic context (`econ.*.ecz`, the strip, the lens and `/evidence`):** Maddison Project Database 2023,
  Penn World Table 11.0, World Bank WDI + OGHIST — all CC BY 4.0; UN WPP 2024 TFR. Fund statistics are
  derived from daily adjusted closes / issuer NAV returns and named only as examples of what exists or existed;
  MSCI figures are hand-transcribed factsheet citations (`evals/econ/msci_citations.yaml`); IMF WEO is used at
  build time only and never exported. The site is not investment advice and makes no forecasts.
- **Evaluation labels:** transcribed from Korenjak-Černe et al., Hahn-Klimroth 2025, populationpyramids.org
  thresholds, RIETI, Yoshida et al. 2019 — `evals/labels/*.yaml` with page references and vintages.
- **Image encoders (offline experiment only):** SigLIP 2 (`google/siglip2-base-patch16-naflex`) and DINOv2
  (`facebook/dinov2-base`), Apache-2.0.
- **Design inspiration:** [populationpyramid.net](https://www.populationpyramid.net) — the fixed-axis,
  youngest-at-the-bottom pyramid and the year scrubber; no data or code is used from it.
- **Code:** MIT ([LICENSE](LICENSE)); data attributions in [NOTICE](NOTICE).
