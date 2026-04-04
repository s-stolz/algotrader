"""Numerical helper routines for indicator implementations."""

from __future__ import annotations

import numpy as np


def rolling_mean(series: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean with NaN propagation."""
    if window <= 0:
        raise ValueError("window must be > 0")
    t_len, a_len = series.shape
    out = np.full_like(series, np.nan, dtype=np.float64)
    valid = ~np.isnan(series)
    filled = np.where(valid, series, 0.0)
    csum = np.cumsum(filled, axis=0)
    ccount = np.cumsum(valid.astype(np.int64), axis=0)

    csum = np.vstack([np.zeros((1, a_len)), csum])
    ccount = np.vstack([np.zeros((1, a_len)), ccount])

    window_sum = csum[window:] - csum[:-window]
    window_count = ccount[window:] - ccount[:-window]
    mean = window_sum / float(window)
    mean[window_count < window] = np.nan
    out[window - 1 :] = mean
    return out


def rolling_std(series: np.ndarray, window: int) -> np.ndarray:
    """Rolling standard deviation with NaN propagation."""
    mean = rolling_mean(series, window)
    mean_sq = rolling_mean(series * series, window)
    var = mean_sq - mean * mean
    var = np.maximum(var, 0.0)
    return np.sqrt(var)


def ema(series: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average computed per asset."""
    if period <= 0:
        raise ValueError("period must be > 0")
    alpha = 2.0 / (period + 1.0)
    t_len, a_len = series.shape
    out = np.full_like(series, np.nan, dtype=np.float64)
    for a_idx in range(a_len):
        prev = np.nan
        for t in range(t_len):
            val = series[t, a_idx]
            if np.isnan(val):
                out[t, a_idx] = np.nan
                prev = np.nan
                continue
            if np.isnan(prev):
                prev = val
            else:
                prev = alpha * val + (1.0 - alpha) * prev
            out[t, a_idx] = prev
    return out
