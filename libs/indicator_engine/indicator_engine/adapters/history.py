"""Shared daily input alignment for historical and sequential indicator adapters."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..core.bars import BarTensor
from ..core.history import UTC_DAY_MS


@dataclass(frozen=True)
class IndicatorInput:
    bars: BarTensor
    available: np.ndarray


def prepare_daily_inputs(
    frames: list[pd.DataFrame],
    assets: list[str],
    fields: list[str],
    timestamps: np.ndarray,
    interval: int,
    predecessor_bars: int,
) -> list[IndicatorInput]:
    if interval > UTC_DAY_MS or UTC_DAY_MS % interval:
        raise ValueError("Daily anchored indicators require a timeframe dividing a UTC day")
    if np.any(timestamps % interval):
        raise ValueError("Daily anchored indicators require timeframe-aligned candles")
    inputs = []
    for day in np.unique(timestamps // UTC_DAY_MS):
        start = int(day) * UTC_DAY_MS
        end = min(start + UTC_DAY_MS, int(timestamps[-1]) + interval)
        grid = np.arange(start, end, interval, dtype=np.int64)
        values = []
        for frame in frames:
            anchor_index = int(frame.index.searchsorted(start))
            prior = frame.iloc[max(0, anchor_index - predecessor_bars) : anchor_index].to_numpy(
                dtype=np.float64
            )
            seed = np.full((predecessor_bars, len(fields)), np.nan)
            if len(prior):
                seed[-len(prior) :] = prior
            values.append(np.vstack([seed, frame.reindex(grid).to_numpy(dtype=np.float64)]))
        data = np.stack(values, axis=1)
        # The seed is calculation-only: never invent an executable candle.
        times = np.concatenate(
            (np.arange(start - predecessor_bars * interval, start, interval), grid)
        )
        valid = np.logical_and.accumulate(np.isfinite(data).all(axis=(1, 2)))
        valid[:predecessor_bars] = False
        inputs.append(
            IndicatorInput(
                bars=BarTensor(data, times, np.array(assets), np.array(fields)),
                available=valid,
            )
        )
    return inputs
