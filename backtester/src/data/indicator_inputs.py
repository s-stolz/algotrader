"""Aligned indicator inputs and causal availability, separate from execution bars."""

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd
from db_accessor_client.timeframes import timeframe_to_minutes
from indicator_engine import BarTensor, get_registry
from indicator_engine.core.history import UTC_DAY_MS
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition


@dataclass(frozen=True)
class IndicatorInput:
    bars: BarTensor
    available: np.ndarray


def needs_source_inputs(strategy: StrategyDefinition) -> bool:
    registry = get_registry()
    return any(
        registry.get(item.indicator_id).spec.required_assets
        or registry.get(item.indicator_id).spec.input_history.anchor != "rolling"
        for item in strategy.indicator_requirements
    )


def prepare_indicator_inputs(
    *,
    requirement: IndicatorFeatureRequirement,
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    feature_bars: Mapping[str, pd.DataFrame],
) -> list[IndicatorInput]:
    spec = get_registry().get(requirement.indicator_id).spec
    if spec.input_history.anchor != "rolling" and not spec.supports_update:
        raise ValueError("Anchored backtest indicators require incremental updates")
    assets = spec.required_assets or [symbol]
    sources = {**feature_bars, symbol: bars}
    missing = set(assets) - sources.keys()
    if missing:
        raise ValueError(f"Missing required indicator sources: {sorted(missing)}")
    fields = list(spec.required_fields)
    source_field = requirement.parameters.get("source")
    if source_field is not None and source_field not in fields:
        fields.append(str(source_field))
    frames = [_source_frame(sources[asset], fields, asset) for asset in assets]
    if spec.input_history.anchor == "utc_day":
        return _daily_inputs(
            frames, assets, fields, bars, timeframe, spec.input_history.predecessor_bars
        )
    timestamps = np.unique(np.concatenate([frame.index.to_numpy() for frame in frames]))
    data = np.stack([frame.reindex(timestamps).to_numpy() for frame in frames], axis=1)
    return [
        IndicatorInput(
            bars=BarTensor(data, timestamps, np.array(assets), np.array(fields)),
            available=np.asarray(np.isfinite(data).all(axis=(1, 2)), dtype=bool),
        )
    ]


def _source_frame(bars: pd.DataFrame, fields: list[str], asset: str) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=pd.Index(fields), index=pd.Index([], dtype="int64"))
    missing = {"timestamp_ms", *fields} - set(bars.columns)
    if missing:
        raise ValueError(f"Indicator source missing columns: {sorted(missing)}")
    if "symbol" in bars and not bool(bars["symbol"].eq(asset).to_numpy().all()):
        raise ValueError(f"Indicator source contains candles from a different symbol than {asset}")
    frame = bars.loc[:, ["timestamp_ms", *fields]].copy()
    frame = frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if frame["timestamp_ms"].isna().any():
        raise ValueError("Indicator source timestamps must be finite")
    frame["timestamp_ms"] = frame["timestamp_ms"].astype("int64")
    return frame.drop_duplicates("timestamp_ms", keep="last").set_index("timestamp_ms").sort_index()


def _daily_inputs(
    frames: list[pd.DataFrame],
    assets: list[str],
    fields: list[str],
    bars: pd.DataFrame,
    timeframe: str,
    predecessor_bars: int,
) -> list[IndicatorInput]:
    interval = timeframe_to_minutes(timeframe) * 60_000
    if interval > UTC_DAY_MS or UTC_DAY_MS % interval:
        raise ValueError("Daily anchored indicators require a timeframe dividing a UTC day")
    timestamps = bars["timestamp_ms"].to_numpy(dtype=np.int64)
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
