"""Default registry/engine helpers for quick usage."""

from __future__ import annotations

from typing import Optional, cast

import pandas as pd

from .core.bars import BarTensor, DataBundle
from .core.history import HistoryPolicy
from .core.params import ParamGrid, ParamSet
from .core.registry import IndicatorRegistry
from .core.results import IndicatorResult
from .engines.batch import BatchEngine
from .engines.update import UpdateEngine
from .indicators import BBANDS, MACD, RSI, SMA, CurrencyStrength

_REGISTRY: Optional[IndicatorRegistry] = None
_BATCH_ENGINE: Optional[BatchEngine] = None


def _create_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    registry.register_many(
        [
            SMA(),
            RSI(),
            BBANDS(),
            MACD(),
            CurrencyStrength(),
        ]
    )
    try:
        registry.load_entry_points()
    except Exception:
        # Entry point loading is optional; ignore failures to keep defaults usable.
        pass
    return registry


def get_registry() -> IndicatorRegistry:
    """Return the shared registry instance with built-in indicators."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _create_registry()
    return _REGISTRY


def get_batch_engine(registry: IndicatorRegistry | None = None) -> BatchEngine:
    """Return a batch engine using the shared registry."""
    global _BATCH_ENGINE
    if registry is None:
        if _BATCH_ENGINE is None:
            _BATCH_ENGINE = BatchEngine(get_registry())
        return _BATCH_ENGINE
    return BatchEngine(registry)


def get_update_engine(
    *,
    history: HistoryPolicy | None = None,
    registry: IndicatorRegistry | None = None,
    max_delay_ms: int | None = None,
    max_delay_bars: int | None = None,
) -> UpdateEngine:
    """Return an update engine with a sensible default history policy."""
    registry = registry or get_registry()
    history = history or HistoryPolicy(mode="rolling", max_rows=5000)
    return UpdateEngine(
        registry=registry,
        history=history,
        max_delay_ms=max_delay_ms,
        max_delay_bars=max_delay_bars,
    )


def run_batch(
    indicator_id: str,
    data: BarTensor | DataBundle | pd.DataFrame | dict[str, pd.DataFrame],
    params: ParamSet | None = None,
    *,
    timeframe: str | None = None,
    registry: IndicatorRegistry | None = None,
) -> IndicatorResult:
    """Convenience wrapper to run a batch indicator with the shared engine.

    Accepts BarTensor/DataBundle or pandas DataFrame(s). DataFrames are
    converted to BarTensor automatically.
    """
    from .adapters.pandas import bars_from_dataframe

    normalized_data: BarTensor | DataBundle
    if isinstance(data, pd.DataFrame):
        normalized_data = bars_from_dataframe(data)
    elif isinstance(data, dict):
        if data and all(isinstance(value, BarTensor) for value in data.values()):
            normalized_data = cast(DataBundle, data)
        elif all(isinstance(value, pd.DataFrame) for value in data.values()):
            dataframe_bundle = cast(dict[str, pd.DataFrame], data)
            normalized_data = {
                key: bars_from_dataframe(value) for key, value in dataframe_bundle.items()
            }
        else:
            raise TypeError(
                "dict input must contain only BarTensor values or only pandas DataFrame values"
            )
    else:
        normalized_data = data

    grid = ParamGrid(params or {})
    engine = get_batch_engine(registry)
    return engine.run(indicator_id, normalized_data, param_grid=grid, timeframe=timeframe)


def _squeeze_result(df, tensor) -> pd.DataFrame:
    if df.empty:
        return df
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    assets = tensor.coords.get("asset")
    if assets is None:
        assets = []
    param_ids = tensor.coords.get("param")
    if param_ids is None:
        param_ids = []
    param_names = tensor.attrs.get("param_names")
    if param_names is None:
        param_names = []

    cols = df.columns
    if len(assets) == 1 and "asset" in cols.names:
        cols = cols.droplevel("asset")
    if len(param_ids) == 1 and param_names:
        for name in param_names:
            if name in cols.names:
                cols = cols.droplevel(name)
    df.columns = cols
    return df


def run(indicator_id: str, df, params: ParamSet | None = None):
    """Run an indicator on a pandas DataFrame and return a pandas DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    from .adapters.pandas import bars_from_dataframe, result_to_dataframe

    bar = bars_from_dataframe(df)
    result = run_batch(indicator_id, bar, params=params)
    out_df = result_to_dataframe(result.tensor)
    return _squeeze_result(out_df, result.tensor)


def list_indicators() -> list[dict[str, str]]:
    """Return a list of indicator id/name pairs from the registry."""
    registry = get_registry()
    return [{"id": spec.id, "name": spec.name} for spec in registry.list_specs().values()]
