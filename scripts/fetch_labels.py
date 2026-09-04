#!/usr/bin/env python
"""External label sets for the similarity evaluation → ``evals/labels/*.yaml`` (PLAN §4.6, CONTRACT §6 ``fetch_labels.py``).

    make labels                      # (re)write the five yaml files from the transcriptions embedded below
    uv run scripts/fetch_labels.py --refetch   # also re-download the sources (network) and re-derive the
                                               # Korenjak-Černe cluster lists from the PDF, asserting they equal
                                               # the embedded transcription (needs poppler: pdftotext + pdftoppm)

Retrieval was done once on 2026-09-04 with the ``arxiv``/``papers`` MCP servers and plain HTTP; what could be
obtained is transcribed here verbatim so the label files are reproducible offline and reviewable in one place.
Every yaml header records source, URL, data vintage and the pre-registered fallback status (PLAN §4.6):

  (a) Korenjak-Černe, Kejžar & Batagelj — *Population Studies* 2015 is paywalled (no OA copy via Unpaywall /
      Semantic Scholar / OpenAlex), so **fallback rung 1 applies: G2(a) uses the 2008 Informatica lists**.  The
      2008 paper prints the country-per-cluster membership only as dendrograms (Figs 9–11), so the four main
      clusters A–D were recovered from the figure geometry (leaf labels via ``pdftotext -bbox``, cluster
      membership = connected components of the rasterised tree left of the four-cluster cut) and verified
      against every count and named mover in the paper's prose (§3.1–3.2): |A₁₉₉₆| = 77, |D₁₉₉₆| = 60,
      |A₂₀₀₁| = 60, |D₂₀₀₁| = 54, |D₂₀₀₆| = 46, Vanuatu ∉ A₂₀₀₆, the six B₂₀₀₁ → C₂₀₀₆ movers and the five
      C₂₀₀₁ → B₂₀₀₆ movers all hold.  Data vintage: US Census Bureau International Data Base (2008 pull),
      17 five-year bins (80+ open), NOT WPP — the vintage-sensitivity row of PLAN §4.6 cannot be computed
      (no IDB-2008 totals on disk) and is recorded as such.
  (b) Hahn-Klimroth et al. 2025 (arXiv 2508.03788): Table S8 (appendix) transcribed in full; the human
      adaptation of the five buckets is fixed here and documented in the yaml.
  (c) populationpyramids.org "3 Types of Population Pyramids" guide (2024-11-12): thresholds + examples.
  (d) RIETI, Chi Hung Kwan, 2022-12-05: China 2020 ≈ Japan 1989–1991 → window [1985, 1995].
  (e) Yoshida, Er-Rbib & Tsutsumi (arXiv 1810.00210, WPP2015 data): Table 1 transcribed in full.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import textwrap
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyramid_explorer.paths import DATA_PROCESSED, DATA_RAW, EVALS  # noqa: E402

LABELS_DIR = EVALS / "labels"
RAW_DIR = DATA_RAW / "labels"
RETRIEVED = "2026-09-04"

SOURCES = {
    "korenjak_cerne_2008": {
        "citation": "Korenjak-Černe S., Kejžar N., Batagelj V. (2008). Clustering of Population Pyramids. Informatica 32, 157–167.",
        "url": "https://www.informatica.si/index.php/informatica/article/view/188",
        "pdf": "https://www.informatica.si/index.php/informatica/article/download/188/184",
        "licence": "open access (Informatica, Slovene Society Informatika)",
    },
    "korenjak_cerne_2015": {
        "citation": "Korenjak-Černe S., Kejžar N., Batagelj V. (2015). A weighted clustering of population pyramids for the world's countries, 1996, 2001, 2006. Population Studies 69(1), 105–120.",
        "url": "https://doi.org/10.1080/00324728.2014.954597",
        "status": "PAYWALLED — no open-access copy found (Unpaywall/Semantic Scholar/OpenAlex, 2026-09-04); memberships NOT transcribed",
    },
    "hahn_klimroth_2025": {
        "citation": "Hahn-Klimroth M., Meireles J.P., Lackey L.B., van Eeuwijk N., Bertelsen M.F., Dierkes P.W., Clauss M. (2025). A semi-automatic approach to study population dynamics based on population pyramids. arXiv:2508.03788 (q-bio.PE).",
        "url": "https://arxiv.org/abs/2508.03788", "pdf": "https://arxiv.org/pdf/2508.03788v1",
    },
    "populationpyramids_org": {
        "citation": "populationpyramids.org, '3 Types of Population Pyramids: Complete Guide to Understanding Population Structure', 2024-11-12.",
        "url": "https://www.populationpyramids.org/blog/population-pyramid-types-complete-guide",
    },
    "rieti": {
        "citation": "Kwan C.H. (2022-12-05). The Low Birthrate and Aging Population in China — A comparison with Japan. RIETI China in Transition.",
        "url": "https://www.rieti.go.jp/en/china/22102701.html",
    },
    "yoshida_2018": {
        "citation": "Yoshida T., Er-Rbib R., Tsutsumi M. (2018). Which country epitomizes the world? A study from the perspective of demographic composition. arXiv:1810.00210; Sustainability 11(22):6404 (2019).",
        "url": "https://arxiv.org/abs/1810.00210", "pdf": "https://arxiv.org/pdf/1810.00210v1",
    },
}

# --------------------------------------------------------------------------------------- (a) Korenjak-Černe 2008
# Four main clusters (Ward, Euclidean on 34 age-sex shares; IDB data) as printed in Figs 9/10/11, leaf order kept.
# A ≈ DTM stage 1 (expansive), B ≈ stages 2–3, C ≈ stages 3–4 (incl. the Gulf male-surplus states), D ≈ stage 4.
KC_CLUSTERS: dict[int, dict[str, list[str]]] = {
    1996: {
        "A": ["Afghanistan", "Ethiopia", "Gambia, The", "Guinea", "Eritrea", "Sudan", "Angola", "Nigeria", "Mozambique", "Sierra Leone", "Comoros", "Guinea-Bissau", "Cote d'Ivoire", "Djibouti", "Belize", "Ghana", "Pakistan", "Central African Republic", "Equatorial Guinea", "Gabon", "Cameroon", "Senegal", "Guatemala", "Laos", "Haiti", "Somalia", "Cambodia", "Tajikistan", "Cape Verde", "Bhutan", "Paraguay", "Bolivia", "Namibia", "Nepal", "Liberia", "El Salvador", "Lesotho", "Papua New Guinea", "Vanuatu", "East Timor", "Kiribati", "Nauru", "Botswana", "Zimbabwe", "Marshall Islands", "Micronesia, Federated States of", "Honduras", "Swaziland", "Nicaragua", "Kenya", "Rwanda", "Iraq", "Syria", "Jordan", "Samoa", "Tonga", "Benin", "Tanzania", "Zambia", "Togo", "Solomon Islands", "Burkina Faso", "Mali", "Sao Tome and Principe", "Yemen", "Uganda", "Burundi", "Western Sahara", "Congo (Kinshasa)", "Malawi", "Congo (Brazzaville)", "Madagascar", "Mauritania", "Niger", "Maldives", "Chad", "Mayotte"],
        "B": ["Algeria", "Libya", "Ecuador", "Morocco", "Philippines", "Jamaica", "Mongolia", "Vietnam", "Kyrgyzstan", "Turkmenistan", "Uzbekistan", "Bangladesh", "Iran", "Grenada", "Oman", "Saudi Arabia", "Azerbaijan", "Tuvalu", "Dominica", "Saint Kitts and Nevis", "Bahamas, The", "Colombia", "New Caledonia", "Costa Rica", "French Polynesia", "Panama", "Dominican Republic", "Peru", "India", "Venezuela", "Egypt", "Mexico", "Malaysia", "Fiji", "South Africa", "Brazil", "Turkey", "Indonesia", "Burma", "Tunisia", "Guyana", "Saint Lucia", "Saint Vincent and the Grenadines", "Seychelles", "Suriname", "Lebanon", "Montserrat"],
        "C": ["Albania", "Chile", "Trinidad and Tobago", "Argentina", "Israel", "Armenia", "Kazakhstan", "Anguilla", "China", "Mauritius", "Sri Lanka", "Thailand", "Barbados", "Korea, South", "Taiwan", "Cuba", "Saint Helena", "Korea, North", "Netherlands Antilles", "Saint Pierre and Miquelon", "Antigua and Barbuda", "Brunei", "Turks and Caicos Islands", "Greenland", "Palau", "Virgin Islands, British", "Macau S.A.R.", "Bahrain", "Kuwait", "Qatar", "United Arab Emirates"],
        "D": ["Andorra", "Hong Kong S.A.R.", "Singapore", "Aruba", "Cayman Islands", "Australia", "Canada", "United States", "Bermuda", "Liechtenstein", "Austria", "Guernsey", "Italy", "San Marino", "Germany", "Jersey", "Luxembourg", "Switzerland", "Netherlands", "Denmark", "Norway", "United Kingdom", "Isle of Man", "Sweden", "Monaco", "Belarus", "Russia", "Georgia", "Lithuania", "Estonia", "Latvia", "Ukraine", "Bosnia and Herzegovina", "Belgium", "France", "Finland", "Gibraltar", "Croatia", "Slovenia", "Bulgaria", "Japan", "Czech Republic", "Hungary", "Greece", "Portugal", "Spain", "Cyprus", "Iceland", "New Zealand", "Ireland", "Uruguay", "Faroe Islands", "Macedonia", "Montenegro", "Moldova", "Malta", "Poland", "Slovakia", "Romania", "Serbia"],
    },
    2001: {
        "A": ["Afghanistan", "Gambia, The", "Guinea", "Angola", "Ethiopia", "Madagascar", "Eritrea", "Sierra Leone", "Maldives", "West Bank", "Comoros", "Mozambique", "Djibouti", "Liberia", "Mayotte", "Somalia", "Oman", "Benin", "Tanzania", "Zambia", "Burkina Faso", "Congo (Kinshasa)", "Burundi", "Malawi", "Sao Tome and Principe", "Mali", "Yemen", "Chad", "Congo (Brazzaville)", "Mauritania", "Western Sahara", "Niger", "Gaza Strip", "Uganda", "Belize", "Honduras", "Ghana", "Namibia", "Nepal", "Pakistan", "Samoa", "Cote d'Ivoire", "Iraq", "Kenya", "Rwanda", "Marshall Islands", "Cameroon", "Senegal", "Laos", "Nigeria", "Guinea-Bissau", "Solomon Islands", "Sudan", "Central African Republic", "Equatorial Guinea", "Gabon", "Guatemala", "Haiti", "Togo", "Swaziland"],
        "B": ["Albania", "Saint Kitts and Nevis", "Azerbaijan", "Dominica", "Tuvalu", "Armenia", "Kazakhstan", "Trinidad and Tobago", "Bahamas, The", "Colombia", "Costa Rica", "Indonesia", "Panama", "New Caledonia", "Dominican Republic", "India", "Egypt", "Malaysia", "Mexico", "Peru", "Venezuela", "Fiji", "South Africa", "Brazil", "Turkey", "French Polynesia", "Burma", "Tunisia", "Guyana", "Saint Vincent and the Grenadines", "Saint Lucia", "Suriname", "Seychelles", "Lebanon", "Montserrat", "Kuwait", "Saudi Arabia", "Algeria", "Mongolia", "Vietnam", "Kyrgyzstan", "Uzbekistan", "Iran", "Bangladesh", "Grenada", "Jordan", "Libya", "American Samoa", "Bhutan", "Paraguay", "Kiribati", "Papua New Guinea", "Bolivia", "Lesotho", "El Salvador", "Philippines", "Turkmenistan", "Ecuador", "Morocco", "Vanuatu", "Jamaica", "Botswana", "Nicaragua", "Syria", "Tajikistan", "Zimbabwe", "Cambodia", "Tonga", "Cape Verde", "East Timor", "Nauru", "Micronesia, Federated States of"],
        "C": ["Anguilla", "China", "Chile", "Mauritius", "Sri Lanka", "Thailand", "Barbados", "Korea, South", "Taiwan", "Virgin Islands, British", "Cuba", "Saint Helena", "Argentina", "Israel", "Cyprus", "Iceland", "Ireland", "Puerto Rico", "Macedonia", "New Zealand", "Uruguay", "Faroe Islands", "Korea, North", "Netherlands Antilles", "Saint Pierre and Miquelon", "Virgin Islands", "Antigua and Barbuda", "Brunei", "Guam", "Turks and Caicos Islands", "Bahrain", "Palau", "Greenland", "Qatar", "Northern Mariana Islands", "United Arab Emirates"],
        "D": ["Andorra", "Hong Kong S.A.R.", "Singapore", "Macau S.A.R.", "Aruba", "Cayman Islands", "Bermuda", "Liechtenstein", "Australia", "United States", "Canada", "Belarus", "Russia", "Estonia", "Latvia", "Ukraine", "Bosnia and Herzegovina", "Georgia", "Lithuania", "Malta", "Serbia", "Poland", "Slovakia", "Romania", "Moldova", "Montenegro", "Austria", "Switzerland", "Belgium", "Luxembourg", "Netherlands", "Jersey", "Germany", "Italy", "San Marino", "Denmark", "Sweden", "Guernsey", "Isle of Man", "France", "United Kingdom", "Norway", "Finland", "Gibraltar", "Monaco", "Bulgaria", "Czech Republic", "Hungary", "Croatia", "Slovenia", "Greece", "Spain", "Portugal", "Japan"],
    },
    2006: {
        "A": ["Afghanistan", "Angola", "Gambia, The", "Madagascar", "Guinea", "Mauritania", "Western Sahara", "Sierra Leone", "Djibouti", "Liberia", "Comoros", "Mozambique", "Maldives", "West Bank", "Mayotte", "Somalia", "Oman", "Benin", "Tanzania", "Ethiopia", "Eritrea", "Central African Republic", "Haiti", "Togo", "Guatemala", "Cameroon", "Laos", "Equatorial Guinea", "Gabon", "Guinea-Bissau", "Nigeria", "Senegal", "Cote d'Ivoire", "Iraq", "Solomon Islands", "Sudan", "Kenya", "Rwanda", "Burkina Faso", "Burundi", "Congo (Brazzaville)", "Congo (Kinshasa)", "Gaza Strip", "Sao Tome and Principe", "Niger", "Chad", "Mali", "Uganda", "Malawi", "Yemen", "Zambia", "Bangladesh", "Marshall Islands", "Belize", "Honduras", "Ghana", "Nepal", "Pakistan", "Samoa", "Bhutan", "Paraguay", "Kiribati", "Papua New Guinea", "Bolivia", "Jamaica", "El Salvador", "Philippines", "Turkmenistan", "Botswana", "Lesotho", "Namibia", "Cambodia", "Tonga", "Nicaragua", "Tajikistan", "Syria", "Cape Verde", "East Timor", "Micronesia, Federated States of", "Nauru", "Swaziland", "Zimbabwe", "Grenada", "Jordan", "Libya", "Saudi Arabia"],
        "B": ["Algeria", "Mongolia", "Iran", "Azerbaijan", "Vietnam", "Brazil", "Turkey", "French Polynesia", "Burma", "Guyana", "Saint Vincent and the Grenadines", "Tunisia", "Brunei", "Saint Lucia", "Suriname", "Seychelles", "Lebanon", "Montserrat", "American Samoa", "Turks and Caicos Islands", "Bahamas, The", "Costa Rica", "New Caledonia", "Guam", "Colombia", "Indonesia", "Panama", "Mexico", "Peru", "Dominican Republic", "Malaysia", "Venezuela", "Egypt", "India", "Fiji", "Ecuador", "Morocco", "Vanuatu", "Kyrgyzstan", "Uzbekistan", "South Africa", "Tuvalu", "Northern Mariana Islands", "Kuwait", "United Arab Emirates"],
        "C": ["Albania", "Saint Kitts and Nevis", "Dominica", "Argentina", "Israel", "Anguilla", "Virgin Islands, British", "Chile", "Sri Lanka", "Mauritius", "Thailand", "Armenia", "Kazakhstan", "Trinidad and Tobago", "Antigua and Barbuda", "Palau", "Bahrain", "Greenland", "Qatar", "Aruba", "Bermuda", "Cayman Islands", "Virgin Islands", "Australia", "United States", "Cyprus", "Iceland", "Puerto Rico", "Macedonia", "Faroe Islands", "Ireland", "New Zealand", "Uruguay", "Barbados", "Korea, South", "Taiwan", "Saint Helena", "China", "Cuba", "Korea, North", "Netherlands Antilles", "Saint Pierre and Miquelon", "Hong Kong S.A.R.", "Singapore", "Macau S.A.R."],
        "D": ["Andorra", "Jersey", "Austria", "Switzerland", "Guernsey", "Germany", "Italy", "San Marino", "Japan", "Monaco", "Belgium", "United Kingdom", "France", "Isle of Man", "Denmark", "Norway", "Finland", "Gibraltar", "Sweden", "Bosnia and Herzegovina", "Canada", "Luxembourg", "Netherlands", "Liechtenstein", "Belarus", "Russia", "Ukraine", "Georgia", "Estonia", "Latvia", "Lithuania", "Moldova", "Montenegro", "Poland", "Slovakia", "Bulgaria", "Czech Republic", "Hungary", "Croatia", "Slovenia", "Malta", "Serbia", "Romania", "Greece", "Spain", "Portugal"],
    },
}
KC_DENDROGRAM_PAGES = {1996: 4, 2001: 5, 2006: 6}   # PDF pages of Figs 9/10/11; cut at 210 pt gives 4 clusters
# IDB names that do not resolve by name/alias lookup against entities.json.
KC_NAME_MAP = {
    "Gambia, The": "GMB", "Cote d'Ivoire": "CIV", "Guinea-Bissau": "GNB", "Congo (Brazzaville)": "COG",
    "Congo (Kinshasa)": "COD", "Gaza Strip": "PSE", "West Bank": "PSE", "Burma": "MMR", "East Timor": "TLS",
    "Micronesia, Federated States of": "FSM", "Swaziland": "SWZ", "Cape Verde": "CPV", "Bahamas, The": "BHS",
    "Korea, South": "KOR", "Korea, North": "PRK", "Macedonia": "MKD", "Hong Kong S.A.R.": "HKG",
    "Macau S.A.R.": "MAC", "Virgin Islands": "VIR", "Virgin Islands, British": "VGB", "Czech Republic": "CZE",
    "Russia": "RUS", "Syria": "SYR", "Iran": "IRN", "Laos": "LAO", "Vietnam": "VNM", "Tanzania": "TZA",
    "Moldova": "MDA", "Bolivia": "BOL", "Venezuela": "VEN", "Brunei": "BRN", "Turkey": "TUR", "Taiwan": "TWN",
    "United States": "USA", "Saint Helena": "SHN", "Sudan": "SDN",
    "Netherlands Antilles": None,   # dissolved 2010 → CUW/SXM/BES in WPP2024: no single entity
}

# --------------------------------------------------------------------------------------- (b) Hahn-Klimroth 2025
# Table S8: idealised transition sequence (bucket n → n+1, four steps, 1 = increase, 0 = same, −1 = decrease)
# → shape, with additional bucket comparisons where the sequence is ambiguous.  Conditions are evaluated in order;
# "else" catches the rest.  B1 = juvenile bucket … B5 = senior bucket.
HK_RULES: list[dict] = [
    {"seq": [-1, -1, 1, 1], "class": "hourglass"}, {"seq": [-1, -1, 1, 0], "class": "hourglass"}, {"seq": [-1, -1, 0, 1], "class": "hourglass"},
    {"seq": [1, 1, 0, 0], "class": "inverted_bell"}, {"seq": [1, 0, 0, 0], "class": "inverted_bell"}, {"seq": [0, 1, 0, 0], "class": "inverted_bell"},
    {"seq": [0, 0, -1, -1], "class": "bell"}, {"seq": [0, 0, -1, 0], "class": "bell"}, {"seq": [0, 0, 0, -1], "class": "bell"},
    {"seq": [0, 0, 1, 1], "class": "inverted_plunger"}, {"seq": [0, 0, 1, 0], "class": "inverted_plunger"}, {"seq": [0, 0, 0, 1], "class": "inverted_plunger"},
    *[{"seq": s, "class": "inverted_pyramid"} for s in ([1, 1, 1, 1], [1, 1, 1, 0], [1, 1, 0, 1], [1, 0, 1, 1], [0, 1, 1, 1], [0, 1, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0], [1, 0, 0, 1])],
    *[{"seq": s, "class": "lower_diamond"} for s in ([1, -1, -1, -1], [1, -1, -1, 0], [1, -1, 0, -1], [1, -1, 0, 0], [1, 0, -1, -1], [1, 0, -1, 0])],
    *[{"seq": s, "class": "diamond"} for s in ([1, 1, -1, -1], [1, 1, -1, 0], [1, 0, 0, -1], [0, 1, -1, -1], [0, 1, -1, 0])],
    {"seq": [-1, -1, 0, 0], "class": "plunger"}, {"seq": [-1, 0, 0, 0], "class": "plunger"}, {"seq": [0, -1, 0, 0], "class": "plunger"},
    *[{"seq": s, "class": "pyramid"} for s in ([-1, -1, -1, -1], [-1, -1, -1, 0], [-1, -1, 0, -1], [-1, 0, -1, -1], [-1, 0, -1, 0], [-1, 0, 0, -1], [0, -1, -1, -1], [0, -1, -1, 0], [0, -1, 0, -1])],
    *[{"seq": s, "class": "upper_diamond"} for s in ([1, 1, 1, -1], [1, 1, 0, -1], [1, 0, 1, -1], [0, 1, 1, -1], [0, 1, 0, -1], [0, 0, 1, -1])],
    {"seq": [0, 0, 0, 0], "class": "column"},
    {"seq": [-1, -1, -1, 1], "cases": [["B3 > B5", "pyramid"], ["else", "hourglass"]]},
    {"seq": [0, -1, -1, 1], "cases": [["B3 > B5", "pyramid"], ["else", "hourglass"]]},
    {"seq": [1, 1, -1, 1], "cases": [["B3 > B5", "diamond"], ["B3 = B5", "inverted_bell"], ["else", "inverted_pyramid"]]},
    {"seq": [0, 0, -1, 1], "cases": [["B3 > B5", "bell"], ["B3 = B5", "column"], ["else", "inverted_plunger"]]},
    {"seq": [0, 1, -1, 1], "cases": [["B3 > B5", "diamond"], ["B3 = B5", "inverted_bell"], ["else", "inverted_pyramid"]]},
    {"seq": [1, 0, -1, 1], "cases": [["B3 > B5", "lower_diamond"], ["B3 = B5", "inverted_bell"], ["else", "inverted_pyramid"]]},
    {"seq": [0, -1, 1, 0], "cases": [["B2 > B4", "plunger"], ["B2 = B4", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [0, -1, 0, 1], "cases": [["B2 > B5", "pyramid"], ["B2 = B5", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [1, -1, 1, 0], "cases": [["B2 > B4", "lower_diamond"], ["B2 = B4", "inverted_bell"], ["else", "inverted_pyramid"]]},
    {"seq": [0, -1, 1, 1], "cases": [["B2 > B4", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [-1, 0, 0, 1], "cases": [["B2 > B5", "plunger"], ["B2 = B5", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [-1, 0, 1, 1], "cases": [["B1 >= B4", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [-1, 0, 1, 0], "cases": [["B1 >= B4", "hourglass"], ["else", "inverted_plunger"]]},
    {"seq": [-1, 1, 1, 0], "cases": [["B1 >= B4", "hourglass"], ["B1 < B3", "inverted_pyramid"], ["else", "hourglass"]]},
    {"seq": [-1, 1, -1, -1], "cases": [["B1 > B3", "pyramid"], ["B1 = B3", "bell"], ["else", "diamond"]]},
    {"seq": [-1, 1, -1, 0], "cases": [["B1 > B3", "pyramid"], ["B1 = B3", "bell"], ["else", "diamond"]]},
    {"seq": [-1, 1, 0, -1], "cases": [["B1 > B3", "pyramid"], ["B1 = B3", "bell"], ["else", "upper_diamond"]]},
    {"seq": [-1, 1, 0, 1], "cases": [["B1 > B3", "hourglass"], ["B1 = B3", "inverted_plunger"], ["else", "inverted_pyramid"]]},
    {"seq": [-1, 1, 1, 1], "cases": [["B1 > B3", "hourglass"], ["B1 = B3", "inverted_plunger"], ["else", "inverted_pyramid"]]},
    {"seq": [-1, 0, -1, 1], "cases": [["B1 = B5 or B2 < B5", "hourglass"], ["B2 = B4", "plunger"], ["else", "pyramid"]]},
    {"seq": [-1, 1, 0, 0], "cases": [["B1 > B3", "plunger"], ["B1 = B3", "column"], ["else", "inverted_bell"]]},
    {"seq": [1, -1, -1, 1], "cases": [["B3 > B5", "lower_diamond"], ["B3 = B5 and B1 > B3", "plunger"], ["B3 = B5", "lower_diamond"],
                                      ["B1 >= B3", "hourglass"], ["else", "inverted_pyramid"]]},
    {"seq": [-1, 1, 1, -1], "cases": [["B1 < B4", "upper_diamond"], ["B1 > B3 and B3 > B5", "pyramid"], ["B3 < B5", "hourglass"], ["else", "bell"]]},
]
HK_HUMAN_BUCKETS = {
    "note": "Human adaptation of the paper's five buckets (juvenile / three equal adult blocks / senior) on 5-year WPP bins. "
            "Bucket value = mean population share per year of age inside the block (share / nominal width), as the paper "
            "uses the mean number of individuals per age class. 'Same size' = relative difference ≤ tolerance (the paper "
            "uses ±0.5 SEM overlap, undefined for a deterministic share vector).",
    "B1": {"ages": "0-14", "bins": [0, 1, 2], "width_years": 15},
    "B2": {"ages": "15-29", "bins": [3, 4, 5], "width_years": 15},
    "B3": {"ages": "30-44", "bins": [6, 7, 8], "width_years": 15},
    "B4": {"ages": "45-59", "bins": [9, 10, 11], "width_years": 15},
    "B5": {"ages": "60+", "bins": [12, 13, 14, 15, 16, 17, 18, 19, 20], "width_years": 25,
           "why_25": "open-ended tail folded into a 60-84 nominal width so the senior density is comparable to a 15-year "
                     "adult block; with the literal 45-year width (60-104) every human population steps down at B4→B5 and "
                     "the class set collapses to pyramid/diamond variants"},
    "tolerance_rel": 0.05,
}

# --------------------------------------------------------------------------------------- (c) thresholds
STAGE_THRESHOLDS = {
    "expansive": {"median_age": "< 25", "tfr": "> 2.5", "growth_pct_yr": "2-4",
                  "quotes": ["Birth rates: Usually above 2.5 children per woman", "Median age: Typically under 25 years", "Growth rate: Often 2-4% annually"],
                  "examples": {"NGA": "47% of population under 15, growing 2.6% annually", "UGA": "48% under 15, median age just 16.7 years",
                               "NER": "50% under 15, world's highest birth rate", "COD": "46% under 15"}},
    "stationary": {"median_age": "35-40", "tfr": "≈ 2.1", "growth_pct_yr": "0-0.5",
                   "quotes": ["Fertility rate: Around 2.1 children per woman", "Population growth near 0-0.5% annually", "Median age: Usually 35-40 years"],
                   "examples": {"USA": "1.7 fertility rate, gradual aging transition", "FRA": "1.8 fertility rate, balanced immigration",
                                "GBR": "1.6 fertility rate, stable population", "CAN": "1.5 fertility rate, immigration maintains growth"}},
    "constrictive": {"median_age": "40+", "tfr": "< 2.1", "growth_pct_yr": None,
                     "quotes": ["Fertility rate: Under 2.1 children per woman", "Median age: Often 40+ years"],
                     "examples": {"JPN": "1.3 fertility rate, 29% over 65, declining since 2010", "KOR": "0.8 fertility rate, world's lowest",
                                  "ITA": "1.2 fertility rate, 23% over 65", "DEU": "1.5 fertility rate, aging rapidly"}},
}

# --------------------------------------------------------------------------------------- (d) RIETI
RIETI = {
    "china_2020": {"child_0_14_pct": 18.0, "working_age_15_59_pct": 64.1, "elderly_60_plus_pct": 17.8, "median_age": 37.4},
    "quotes": [
        "In 2020, the proportion of the child population and that of elderly population in China were equivalent to their respective levels in Japan in 1990, and the proportion of the working-age population was equivalent to the 1989 level in Japan.",
        "China's median age in 2020 was 10.6 years lower than that of Japan's and resembled that of Japan in 1991.",
    ],
    "japan_years_named": {"child_and_elderly_share": 1990, "working_age_share": 1989, "median_age": 1991},
    "window": [1985, 1995],
}

# --------------------------------------------------------------------------------------- (e) Yoshida Table 1
# Countries in 2015 most similar (Aitchison distance on 21 total-population age shares, WPP2015) to the World in year Y;
# † = distance > 1 (listed by the authors only to characterise the distant future).
YOSHIDA_TABLE1 = {
    1990: [("IND", 0.579), ("EGY", 0.776), ("DZA", 0.785), ("BGD", 0.877)],
    2000: [("DZA", 0.605), ("IND", 0.775), ("BRA", 0.847)],
    2010: [("PER", 0.474), ("ECU", 0.581), ("COL", 0.581), ("BRA", 0.694), ("LKA", 0.706), ("MEX", 0.939), ("DZA", 0.989)],
    2015: [("COL", 0.532), ("PER", 0.567), ("ECU", 0.594), ("LKA", 0.639), ("MEX", 0.806), ("BRA", 0.900), ("ARG", 0.975)],
    2020: [("COL", 0.792), ("LKA", 0.801), ("ECU", 0.838), ("MEX", 0.872), ("PER", 0.900)],
    2030: [("ARG", 0.544), ("IRL", 0.776), ("ISR", 0.789)],
    2040: [("NZL", 0.494), ("USA", 0.635), ("AUS", 0.655), ("IRL", 0.677), ("URY", 0.703), ("CHL", 0.820), ("ARG", 0.824), ("NOR", 0.863),
           ("CAN", 0.956), ("GBR", 0.960), ("ISR", 0.965), ("CUB", 0.996)],
    2050: [("URY", 0.419), ("PRI", 0.622), ("GBR", 0.732), ("USA", 0.760), ("NOR", 0.882), ("NZL", 0.900), ("FRA", 0.916), ("CAN", 0.926)],
    2060: [("PRI", 0.839), ("URY", 1.027), ("FRA", 1.125), ("GBR", 1.149), ("ITA", 1.321)],
    2070: [("PRI", 1.293), ("JPN", 1.469), ("ITA", 1.501), ("FRA", 1.556), ("URY", 1.589)],
    2080: [("JPN", 1.576), ("PRI", 1.662), ("ITA", 1.697), ("FRA", 1.858), ("URY", 1.983)],
}
YOSHIDA_CLUSTERS_2015 = {   # §3.6, Ward on Aitchison distance; "representative areas" as named in the text
    1: "pyramid — Sub-Saharan Africa, Middle East, South-Eastern Asia, Afghanistan, Pakistan (world before 1990)",
    2: "pyramid, sub-cluster of 1 with relatively high population",
    3: "pyramid (as 1)",
    4: "bell — China, North Africa, Southern Asia, Brazil, India, Central Asia, South Africa (world ≈ 2000)",
    5: "spindle — Latin America, Israel (world 2015–2030)",
    6: "star — Russia, Western Europe (recessive; matches no period)",
    7: "coffin — Japan, Europe, North America, Oceania (world in the distant future)",
}


# --------------------------------------------------------------------------------------- helpers
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def map_names(names: list[str], entities: list[dict], manual: dict[str, str | None] = KC_NAME_MAP) -> tuple[dict[str, str], list[str]]:
    """IDB/paper country names → ISO3 via entities.json names/aliases, then the manual map; returns (mapped, unmapped)."""
    lookup: dict[str, str] = {}
    for e in entities:
        if e["type"] != "country":
            continue
        for key in [e["name"], e.get("short_name", ""), *e.get("aliases", [])]:
            lookup.setdefault(_norm(key), e["id"])
    mapped, unmapped = {}, []
    for n in names:
        iso = manual[n] if n in manual else lookup.get(_norm(n))
        (mapped.__setitem__(n, iso) if iso else unmapped.append(n))
    return mapped, unmapped


def kc_label_set(entities: list[dict]) -> dict:
    """Per year: cluster → ISO3 list (mapped), plus the raw names and what could not be mapped."""
    out = {}
    for year, clusters in KC_CLUSTERS.items():
        names = [n for ns in clusters.values() for n in ns]
        mapped, unmapped = map_names(names, entities)
        by_iso: dict[str, str] = {}
        for c, ns in clusters.items():
            for n in ns:
                if n in mapped:
                    by_iso.setdefault(mapped[n], c)
        dup = [n for n in mapped if list(mapped.values()).count(mapped[n]) > 1]
        out[year] = {"n_countries_paper": len(names), "n_mapped": len(by_iso), "unmapped": unmapped,
                     "merged_into_one_entity": sorted(set(mapped[n] for n in dup)),
                     "clusters": {c: sorted(iso for iso, cc in by_iso.items() if cc == c) for c in clusters},
                     "raw_names": clusters}
    return out


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_yaml(name: str, header: str, doc: dict) -> Path:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    p = LABELS_DIR / name
    text = "".join(f"# {line}\n" if line else "#\n" for line in textwrap.dedent(header).strip().splitlines())
    p.write_text(text + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return p


# --------------------------------------------------------------------------------------- refetch (network)
def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        subprocess.run(["curl", "-sSL", "-A", "Mozilla/5.0", "-o", str(dest), url], check=True)
    return dest


def parse_kc2008(pdf: Path, year: int, cut_pt: float = 210.0) -> dict[str, list[str]]:
    """Recover the four main clusters of one dendrogram page: leaf labels from ``pdftotext -bbox`` (uniform 2.8 pt
    pitch), membership = connected components of the rasterised tree left of the four-cluster cut (x = cut_pt)."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    page = KC_DENDROGRAM_PAGES[year]
    work = pdf.parent / f"kc2008_p{page}"
    subprocess.run(["pdftoppm", "-r", "400", "-f", str(page), "-l", str(page), "-png", str(pdf), str(work)], check=True)
    png = next(pdf.parent.glob(f"kc2008_p{page}*.png"))
    bbox = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    words = [(float(a), float(b), float(c), w.replace("&apos;", "'").replace("−", "-"))
             for a, b, c, _, w in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', bbox)]
    skip = re.compile(r"[\d. ]+|agnes|d2|\(\*,|&quot;ward&quot;\)|Male|Female|Height")
    lab = [w for w in words if w[0] < 250 and 80 < w[1] < 730 and not skip.fullmatch(w[3])]
    lines: dict[float, list] = {}
    for x0, y0, _, w in lab:
        lines.setdefault(round(y0, 1), []).append((x0, w))
    s = 400 / 72
    im = np.array(Image.open(png).convert("L")) < 128
    xl = int((float(np.median([w[2] for w in lab])) + 1.5) * s)
    sub = im[:, :int(cut_pt * s)].copy(); sub[:, :xl] = False
    comp, _ = ndimage.label(sub, structure=np.ones((3, 3)))
    groups: dict[int, list[str]] = {}
    for y in sorted(lines):
        yc = int((y + 1.4) * s)
        band = comp[yc - 4:yc + 5, xl:xl + 40]
        ids = band[band > 0]
        groups.setdefault(int(np.bincount(ids).argmax()) if len(ids) else -1, []).append(" ".join(w for _, w in sorted(lines[y])))
    comps = [g for k, g in groups.items() if k != -1]
    if len(comps) != 4:
        raise RuntimeError(f"{year}: expected 4 clusters at cut {cut_pt} pt, got {len(comps)}")
    return dict(zip("ABCD", comps))   # dendrogram top → bottom = expansive → aged


def refetch() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pdf = download(SOURCES["korenjak_cerne_2008"]["pdf"], RAW_DIR / "korenjak_cerne_2008.pdf")
    download(SOURCES["hahn_klimroth_2025"]["pdf"], RAW_DIR / "hahn_klimroth_2025.pdf")
    download(SOURCES["yoshida_2018"]["pdf"], RAW_DIR / "yoshida_2018.pdf")
    download(SOURCES["rieti"]["url"], RAW_DIR / "rieti_22102701.html")
    download(SOURCES["populationpyramids_org"]["url"], RAW_DIR / "populationpyramids_org_types.html")
    for year in KC_CLUSTERS:
        got = parse_kc2008(pdf, year)
        for c in "ABCD":
            assert got[c] == KC_CLUSTERS[year][c], f"{year} cluster {c}: PDF parse differs from the embedded transcription"
        print(f"KC2008 {year}: {[len(got[c]) for c in 'ABCD']} — parse matches the transcription")
    print("sha256:", {p.name: sha256_file(p)[:16] for p in sorted(RAW_DIR.iterdir())})


# --------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refetch", action="store_true", help="re-download the sources and re-derive the KC2008 lists (network, poppler)")
    a = ap.parse_args(argv)
    if a.refetch:
        refetch()
    entities = json.loads((DATA_PROCESSED / "entities.json").read_text())
    kc = kc_label_set(entities)
    common = {"retrieved": RETRIEVED, "written_by": "scripts/fetch_labels.py"}

    write_yaml("korenjak_cerne.yaml", f"""
    G2(a) — Korenjak-Černe, Kejžar & Batagelj: clusters of the world's countries by population-pyramid shape.
    FALLBACK STATUS: rung 1 of the PLAN §4.6 ladder — the 2015 Population Studies memberships are unobtainable
    (paywalled, no OA copy), so the 2008 Informatica lists are used; 2006 is the primary label year (closest to a
    year we can score), 1996 and 2001 are kept for reference/sensitivity.
    Method (paper): Ward hierarchical clustering, Euclidean distance on 34 normalised age-sex shares (17 five-year
    bins per sex, 80+ open), US Census Bureau International Data Base (2008 pull). Four main clusters A–D =
    the four-cluster cut of Figs 9/10/11 (A ≈ DTM stage 1 expansive … D ≈ stage 4 aged).
    Transcription: leaf order from the dendrogram text layer, membership from the rasterised tree (see
    scripts/fetch_labels.py::parse_kc2008); cross-checked against every count/mover in the paper's prose.
    Vintage caveat: IDB-2008 estimates, not WPP2024 — the vintage-sensitivity row (drop countries whose 2006 total
    differs > 10 % between vintages) is NOT computed because no IDB-2008 totals are on disk; recorded as omitted.
    """, {**common, "source": SOURCES["korenjak_cerne_2008"], "source_2015": SOURCES["korenjak_cerne_2015"],
          "fallback_status": "rung1_2008_lists", "primary_year": 2006, "vintage": "US Census IDB (2008), 17 bins/sex, 80+ open",
          "vintage_sensitivity_row": "omitted — IDB-2008 totals unavailable", "cluster_meaning": {
              "A": "expansive (DTM stage 1)", "B": "stage 2–3", "C": "stage 3–4 (incl. Gulf male-surplus states in 1996/2006)", "D": "stage 4 (aged)"},
          "years": kc})

    write_yaml("hahn_klimroth_2025.yaml", f"""
    G2(b) — Hahn-Klimroth et al. 2025 rule-based pyramid shapes, computed from the data (metric-independent).
    The paper (zoo mammal populations) reduces a pyramid to five buckets — juvenile / three equal adult blocks /
    senior — and classifies the four bucket-to-bucket transitions (+1 / 0 / −1) with Table S8 (transcribed in
    full below, 74 of the 81 sequences; the 7 unlisted sequences are classed 'other'). The human bucket
    boundaries and the equality tolerance are OUR choices, fixed here before any metric was scored against them.
    Vintage: rules only — classes are recomputed from WPP2024 rows at evaluation time.
    """, {**common, "source": SOURCES["hahn_klimroth_2025"], "vintage": "rule set (paper appendix Table S8, arXiv v1 2025-08-05)",
          "classes": ["pyramid", "plunger", "bell", "lower_diamond", "diamond", "upper_diamond", "column", "hourglass",
                      "inverted_pyramid", "inverted_plunger", "inverted_bell", "other"],
          "families": {"note": "gate level (G2b): the paper's lower/middle/upper diamond variants are one shape family",
                       "diamond": ["lower_diamond", "diamond", "upper_diamond"]},
          "buckets": HK_HUMAN_BUCKETS, "rules": HK_RULES})

    write_yaml("thresholds_stage.yaml", f"""
    G2(c) — textbook expansive / stationary / constrictive stage thresholds (populationpyramids.org guide, quoted).
    Operational rule used by pyramid_explorer.features.stage: expansive if median age < 25, constrictive if ≥ 40,
    stationary otherwise (the guide's 35–40 stationary band leaves 25–35 unnamed; we fill it as stationary).
    Vintage: thresholds are timeless; the guide's example figures refer to ~2024 data.
    """, {**common, "source": SOURCES["populationpyramids_org"], "vintage": "guide dated 2024-11-12; examples ≈ 2024 figures",
          "operational_rule": {"expansive": "median_age < 25", "stationary": "25 ≤ median_age < 40", "constrictive": "median_age ≥ 40"},
          "guide": STAGE_THRESHOLDS})

    write_yaml("rieti.yaml", f"""
    G2(d) — RIETI (Kwan 2022): China's 2020 age structure matched Japan's around 1989–1991 on child/elderly/working-age
    shares and median age → time-shift window [1985, 1995] for CHN 2020 → JPN best year.
    Vintage: China 2020 census / Japanese official statistics as cited by the author (not WPP).
    """, {**common, "source": SOURCES["rieti"], "vintage": "China 2020 census + Japan official statistics (author's tables)", **RIETI})

    write_yaml("yoshida_epitome.yaml", f"""
    G2(e) — Yoshida, Er-Rbib & Tsutsumi: which country in 2015 epitomises the World's age structure in year Y
    (Aitchison distance on 21 total-population five-year shares, WPP2015 medium variant, 201 countries ≥ 90k).
    Table 1 transcribed in full (countries block); † rows (distance > 1) kept with their values.
    Pre-registered targets (corrected from PLAN §4.6's summary after reading the paper): World 1990 → ≥ 3 of
    {{IND, EGY, DZA, BGD}} in top-5; World 2015 → ≥ 3 of {{COL, PER, ECU, LKA, MEX, BRA, ARG}} in top-5; World 2050 →
    both of {{URY, PRI}} in top-5. Query = agg-900 at year Y, candidates = countries in 2015 (≥ 100k), era all.
    Vintage caveat: WPP2015; WPP2024's World 2050 projection differs from WPP2015's.
    """, {**common, "source": SOURCES["yoshida_2018"], "vintage": "WPP2015 medium variant; candidates = countries in 2015",
          "distance": "Aitchison (clr-Euclidean) on 21 total age shares — our closest metric is 'clr' with sex='1'",
          "targets": {"1990": {"set": ["IND", "EGY", "DZA", "BGD"], "min_in_top5": 3},
                      "2015": {"set": ["COL", "PER", "ECU", "LKA", "MEX", "BRA", "ARG"], "min_in_top5": 3},
                      "2050": {"set": ["URY", "PRI"], "min_in_top5": 2}},
          "table1_countries": {y: [{"id": i, "d_ait": d} for i, d in rows] for y, rows in YOSHIDA_TABLE1.items()},
          "clusters_2015": YOSHIDA_CLUSTERS_2015})
    for p in sorted(LABELS_DIR.glob("*.yaml")):
        print(f"wrote {p.relative_to(EVALS.parent)}  sha256 {sha256_file(p)[:16]}")
    for year, d in kc.items():
        print(f"  KC {year}: mapped {d['n_mapped']}/{d['n_countries_paper']}, unmapped {d['unmapped']}, merged {d['merged_into_one_entity']}")


if __name__ == "__main__":
    main()
