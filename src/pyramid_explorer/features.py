"""Engineered demographic features of a share vector (CONTRACT §3 `features.py`, PLAN §3.3).

Every feature is a pure function of the 42-vector ``s42`` (male shares 0..20, female shares 21..41, summing
to 1).  Ages are 5-year bins, ``age_start = 5k``; the last bin (100+) is treated as ``[100, 105)`` for the
median/mean interpolation.  The JS twin (`web/src/lib/math/features.ts`) must reproduce these numbers.

Stage rule (documented median-age thresholds, after populationpyramids.org / PLAN §4.6 G2(c)):
``expansive`` if median age < 25, ``constrictive`` if median age ≥ 40, ``stationary`` otherwise.
Flags: ``flag_male_skew`` = working-age sex ratio > 1.3 (Gulf-migrant pattern); ``flag_urn`` = modal bin
starts at age ≥ 45 (inverted / urn shape).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pyramid_explorer.paths import N_BINS, N_DIMS

FEATURE_NAMES: list[str] = [
    "median_age", "mean_age", "u15", "wa", "o65", "o80", "child_dep", "old_dep", "total_dep",
    "base_slope_20", "base_slope_10", "modal_bin", "wa_sex_ratio", "stage", "flag_male_skew", "flag_urn",
]
NUMERIC_FEATURES: list[str] = FEATURE_NAMES[:13]   # everything before `stage` and the flags
BIN_WIDTH = 5.0
MEDIAN_THRESHOLDS = (25.0, 40.0)   # expansive < 25 ≤ stationary < 40 ≤ constrictive
MALE_SKEW_RATIO = 1.3
URN_MODAL_AGE = 45


def s21(s42: np.ndarray) -> np.ndarray:
    """Total-only age distribution: male + female shares per bin, ``[n, 21]``."""
    s42 = np.asarray(s42, dtype=np.float64)
    return s42[..., :N_BINS] + s42[..., N_BINS:]


def median_age(a21: np.ndarray) -> np.ndarray:
    """Median age by linear interpolation inside the bin where the CDF crosses 0.5 (100+ as [100,105))."""
    cdf = np.cumsum(a21, axis=1)
    k = (cdf < 0.5).sum(axis=1)                      # first bin whose CDF reaches 0.5
    k = np.minimum(k, N_BINS - 1)
    idx = np.arange(len(a21))
    below = np.where(k > 0, cdf[idx, np.maximum(k - 1, 0)], 0.0)
    width = a21[idx, k]
    frac = np.divide(0.5 - below, width, out=np.zeros_like(width), where=width > 0)
    return BIN_WIDTH * k + BIN_WIDTH * np.clip(frac, 0.0, 1.0)


def features(s42: np.ndarray) -> pd.DataFrame:
    """One feature row per input row (``s42`` shaped ``[n, 42]`` or ``[42]``); columns = FEATURE_NAMES."""
    s42 = np.atleast_2d(np.asarray(s42, dtype=np.float64))
    if s42.shape[1] != N_DIMS:
        raise ValueError(f"expected [n, {N_DIMS}] shares, got {s42.shape}")
    a = s21(s42)
    m, f = s42[:, :N_BINS], s42[:, N_BINS:]
    mid = BIN_WIDTH * np.arange(N_BINS) + BIN_WIDTH / 2          # 2.5, 7.5, …, 102.5
    u15, wa, o65, o80 = a[:, :3].sum(1), a[:, 3:13].sum(1), a[:, 13:].sum(1), a[:, 16:].sum(1)
    safe_wa = np.where(wa > 0, wa, np.nan)
    ratio = lambda num, den: np.divide(num, den, out=np.full_like(num, np.nan), where=den > 0)
    med = median_age(a)
    modal_bin = BIN_WIDTH * a.argmax(1)                           # age_start of the modal bin
    wa_sr = ratio(m[:, 4:12].sum(1), f[:, 4:12].sum(1))          # ages 20–59
    stage = np.where(med < MEDIAN_THRESHOLDS[0], "expansive",
                     np.where(med >= MEDIAN_THRESHOLDS[1], "constrictive", "stationary"))
    return pd.DataFrame({
        "median_age": med, "mean_age": a @ mid, "u15": u15, "wa": wa, "o65": o65, "o80": o80,
        "child_dep": u15 / safe_wa, "old_dep": o65 / safe_wa, "total_dep": (u15 + o65) / safe_wa,
        "base_slope_20": ratio(a[:, 0], a[:, 4]), "base_slope_10": ratio(a[:, 0], a[:, 2]),
        "modal_bin": modal_bin, "wa_sex_ratio": wa_sr, "stage": stage,
        "flag_male_skew": wa_sr > MALE_SKEW_RATIO, "flag_urn": modal_bin >= URN_MODAL_AGE,
    })[FEATURE_NAMES]


def zscores(feat: pd.DataFrame, reference_rows: np.ndarray) -> pd.DataFrame:
    """Standardise the numeric feature columns of every row against ``feat.iloc[reference_rows]``.

    The reference is the focal-year country set (PLAN §3.3); the returned frame carries the reference
    mean/std in ``.attrs['mu'] / .attrs['sd']`` so a query vector can be standardised the same way.
    A zero-variance column gets ``sd = 1`` (its z-scores are then plain deviations, i.e. 0 on the reference).
    """
    ref = feat.iloc[np.asarray(reference_rows)][NUMERIC_FEATURES].to_numpy(dtype=np.float64)
    mu = np.nanmean(ref, axis=0)
    sd = np.nanstd(ref, axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)
    z = (feat[NUMERIC_FEATURES].to_numpy(dtype=np.float64) - mu) / sd
    out = pd.DataFrame(z, columns=NUMERIC_FEATURES, index=feat.index)
    out.attrs["mu"], out.attrs["sd"] = mu, sd
    return out


def zscore_vector(feat_row: pd.DataFrame | pd.Series, z: pd.DataFrame) -> np.ndarray:
    """Standardise one raw feature row with the reference statistics stored on a `zscores` frame."""
    raw = pd.DataFrame(feat_row).T if isinstance(feat_row, pd.Series) else feat_row
    v = raw[NUMERIC_FEATURES].to_numpy(dtype=np.float64).reshape(-1, len(NUMERIC_FEATURES))
    return (v - z.attrs["mu"]) / z.attrs["sd"]
