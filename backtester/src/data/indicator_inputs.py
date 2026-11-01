"""Aligned indicator inputs and causal availability, separate from execution bars."""

from typing import Mapping

import numpy as np
import pandas as pd
from db_accessor_client.timeframes import timeframe_to_minutes
from indicator_engine import BarTensor, get_registry
from indicator_engine.adapters.history import IndicatorInput, prepare_daily_inputs
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition


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
        return prepare_daily_inputs(
            frames,
            assets,
            fields,
            bars["timestamp_ms"].to_numpy(dtype=np.int64),
            timeframe_to_minutes(timeframe) * 60_000,
            spec.input_history.predecessor_bars,
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
