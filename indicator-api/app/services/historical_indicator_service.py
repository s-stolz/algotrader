from __future__ import annotations

from typing import Optional

import pandas as pd
from app import (
    BATCH_ENGINE,
    ENGINE_REGISTRY,
    get_engine_id,
    get_indicator_metadata,
)
from app.candles import get_candles
from app.services.candle_cache import CandleCache
from app.utils import (
    adjust_fetch_bounds,
    format_indicator_response,
    prepare_parameters,
    tensor_to_dataframe_single,
    trim_indicator_output,
)
from db_accessor_client import normalize_timeframe_code, timeframe_to_minutes
from indicator_engine.adapters import bars_from_dataframe
from indicator_engine.core import ParamGrid


async def _fetch_multi_asset_candles(
    *,
    required_assets: list[str],
    timeframe_code: str,
    fetch_start: Optional[int],
    end_ms: Optional[int],
    fetch_limit: Optional[int],
    exchange: Optional[str],
) -> pd.DataFrame:
    candles = await get_candles(
        symbol=required_assets,
        timeframe=timeframe_code,
        start_ms=fetch_start,
        end_ms=end_ms,
        limit=fetch_limit,
        exchange=exchange,
    )

    if candles.empty or candles.columns.nlevels != 2:
        return candles

    try:
        close_df = candles.xs("close", level=0, axis=1)
    except KeyError:
        return candles

    if close_df.empty:
        return candles

    available_assets = [asset for asset in required_assets if asset in close_df.columns]
    if available_assets:
        close_df = close_df[available_assets]

    aligned_index = close_df.dropna(how="any").index
    return candles.loc[aligned_index]


async def _fetch_single_asset_candles(
    *,
    symbol: str,
    timeframe_code: str,
    fetch_start: Optional[int],
    end_ms: Optional[int],
    fetch_limit: Optional[int],
    exchange: Optional[str],
    candle_cache: CandleCache,
) -> pd.DataFrame:
    candles = await get_candles(
        symbol=symbol,
        timeframe=timeframe_code,
        start_ms=fetch_start,
        end_ms=end_ms,
        limit=fetch_limit,
        exchange=exchange,
    )
    candle_cache.put(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe_code,
        candles=candles,
    )
    return candles


async def run_historical_indicator(
    *,
    indicator_id: int,
    symbol: str,
    exchange: Optional[str],
    timeframe: str,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: Optional[int],
    custom_parameters: dict,
    candle_cache: CandleCache,
) -> dict:
    timeframe_code = normalize_timeframe_code(timeframe)
    timeframe_minutes = timeframe_to_minutes(timeframe_code)
    metadata = get_indicator_metadata(indicator_id)

    parameters = prepare_parameters(
        metadata,
        custom_parameters,
        timeframe=timeframe_code,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=limit,
    )
    indicator_params = {k: v for k, v in parameters.items() if k in metadata["parameters"]}

    engine_id = get_engine_id(indicator_id)
    indicator = ENGINE_REGISTRY.get(engine_id)
    warmup = indicator.spec.warmup(indicator_params)
    required_assets = metadata.get("inputs", [])

    fetch_start, fetch_limit, orig_start, orig_limit = adjust_fetch_bounds(
        start_ms=start_ms,
        limit=limit,
        timeframe=timeframe_minutes,
        warmup=warmup,
    )

    if required_assets:
        candles = await _fetch_multi_asset_candles(
            required_assets=required_assets,
            timeframe_code=timeframe_code,
            fetch_start=fetch_start,
            end_ms=end_ms,
            fetch_limit=fetch_limit,
            exchange=exchange,
        )
    else:
        candles = await _fetch_single_asset_candles(
            symbol=symbol,
            timeframe_code=timeframe_code,
            fetch_start=fetch_start,
            end_ms=end_ms,
            fetch_limit=fetch_limit,
            exchange=exchange,
            candle_cache=candle_cache,
        )

    bar_tensor = bars_from_dataframe(candles)
    param_grid = ParamGrid(indicator_params)
    indicator_result = BATCH_ENGINE.run(engine_id, bar_tensor, param_grid)
    indicator_raw = tensor_to_dataframe_single(indicator_result.tensor)

    dropna_how = "all" if required_assets else "any"
    indicator_data = trim_indicator_output(
        indicator_raw,
        original_start_ms=orig_start,
        original_limit=orig_limit,
        dropna_how=dropna_how,
    )

    return format_indicator_response(indicator_data, metadata)
