"""Historical daily indicators with shared session alignment and availability."""

import asyncio

import numpy as np
import pandas as pd
from db_accessor_client import timeframe_to_minutes
from indicator_engine import ParamGrid
from indicator_engine.adapters.history import prepare_daily_inputs
from indicator_engine.core.spec import IndicatorSpec

from app import BATCH_ENGINE, ENGINE_REGISTRY
from app.candles import get_candles
from app.utils import tensor_to_dataframe_single


async def calculate_anchored_indicator(
    *,
    engine_id: str,
    parameters: dict,
    symbol: str,
    exchange: str | None,
    timeframe: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> pd.DataFrame:
    spec = ENGINE_REGISTRY.get(engine_id).spec
    history = spec.resolve_input_history(parameters)
    assets = spec.required_assets or [symbol]
    fields = list(spec.required_fields)
    source = parameters.get("source")
    if source is not None and source not in fields:
        fields.append(str(source))
    interval = timeframe_to_minutes(timeframe) * 60_000
    fetch_start = (
        None
        if start_ms is None
        else spec.plan_history(start_ms=start_ms, params=parameters).start_ms
    )
    frames = await _fetch_sources(
        assets=assets,
        fields=fields,
        timeframe=timeframe,
        exchange=exchange,
        start_ms=fetch_start,
        end_ms=end_ms,
        limit=limit if start_ms is None else None,
    )
    timestamps = _select_output_times(frames, start_ms=start_ms, end_ms=end_ms, limit=limit)
    if not len(timestamps):
        return pd.DataFrame(columns=pd.Index(spec.outputs))
    frames = await _load_calculation_history(
        frames=frames,
        assets=assets,
        spec=spec,
        fields=fields,
        parameters=parameters,
        timeframe=timeframe,
        exchange=exchange,
        timestamps=timestamps,
        reload_history=start_ms is None,
        interval=interval,
    )
    blocks = prepare_daily_inputs(
        frames,
        assets,
        fields,
        timestamps,
        interval,
        history.predecessor_bars,
        session=history.session,
    )
    results = []
    for block in blocks:
        result = BATCH_ENGINE.run(engine_id, block.bars, ParamGrid(parameters))
        frame = tensor_to_dataframe_single(result.tensor)
        valid = block.available & np.isfinite(frame.to_numpy(dtype=np.float64)).all(axis=1)
        results.append(frame.loc[valid])
    output = pd.concat(results).reindex(timestamps).dropna(how="any")
    output.index = pd.to_datetime(output.index, unit="ms", utc=True)
    output.index.name = "timestamp"
    return output


async def _load_calculation_history(
    *,
    frames: list[pd.DataFrame],
    assets: list[str],
    spec: IndicatorSpec,
    fields: list[str],
    parameters: dict,
    timeframe: str,
    exchange: str | None,
    timestamps: np.ndarray,
    reload_history: bool,
    interval: int,
) -> list[pd.DataFrame]:
    plan = spec.plan_history(start_ms=int(timestamps[0]), params=parameters)
    if reload_history:
        frames = await _fetch_sources(
            assets=assets,
            fields=fields,
            timeframe=timeframe,
            exchange=exchange,
            start_ms=plan.start_ms,
            end_ms=int(timestamps[-1]) + interval,
            limit=None,
        )
    if not plan.predecessor_bars:
        return frames
    predecessors = await _fetch_sources(
        assets=assets,
        fields=fields,
        timeframe=timeframe,
        exchange=exchange,
        start_ms=None,
        end_ms=plan.start_ms,
        limit=plan.predecessor_bars,
    )
    return [
        pd.concat([prior, frame.loc[frame.index >= plan.start_ms]]).sort_index()
        for prior, frame in zip(predecessors, frames, strict=True)
    ]


async def _fetch_sources(
    *,
    assets: list[str],
    fields: list[str],
    timeframe: str,
    exchange: str | None,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> list[pd.DataFrame]:
    frames = await asyncio.gather(
        *[
            get_candles(
                symbol=asset,
                timeframe=timeframe,
                exchange=exchange,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
            )
            for asset in assets
        ]
    )
    return [_normalize_source(frame, fields) for frame in frames]


def _normalize_source(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=pd.Index(fields), index=pd.Index([], dtype="int64"), dtype=np.float64
        )
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Historical indicator sources require a DatetimeIndex")
    if frame.index.hasnans:
        raise ValueError("Historical indicator source timestamps must be finite")
    missing = set(fields) - set(frame.columns)
    if missing:
        raise ValueError(f"Historical indicator source missing fields: {sorted(missing)}")
    normalized = frame.loc[:, fields].apply(pd.to_numeric, errors="coerce")
    normalized = normalized.replace([np.inf, -np.inf], np.nan).astype(np.float64)
    normalized.index = pd.Index(frame.index.as_unit("ms").asi8)
    return normalized.loc[~normalized.index.duplicated(keep="last")].sort_index()


def _select_output_times(
    frames: list[pd.DataFrame],
    *,
    start_ms: int | None,
    end_ms: int | None,
    limit: int | None,
) -> np.ndarray:
    timestamps = np.unique(
        np.concatenate([frame.index.to_numpy(dtype=np.int64) for frame in frames])
    )
    if start_ms is not None:
        timestamps = timestamps[timestamps >= start_ms]
    if end_ms is not None:
        timestamps = timestamps[timestamps < end_ms]
    if limit is not None:
        if limit <= 0:
            raise ValueError("Indicator history limit must be positive")
        timestamps = timestamps[-limit:]
    return timestamps
