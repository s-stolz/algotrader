"""Indicator-engine feature integration for vectorized backtests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd
from strategies.base import StrategyDefinition


def build_feature_frame(
    *,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> pd.DataFrame:
    """Attach strategy-required indicator features to normalized bars."""

    indicator_specs = _extract_indicator_specs(strategy)
    if not indicator_specs:
        return bars.copy()

    run_indicator = _import_indicator_runner()
    feature_input = _build_indicator_input_frame(bars)
    featured = bars.copy()

    for spec in indicator_specs:
        indicator_id = str(spec["indicator_id"])
        params = dict(spec.get("params", {}))
        output_column = str(spec.get("output_column", indicator_id))
        output_key = spec.get("output_key")

        result_df = run_indicator(indicator_id, feature_input, params)
        if result_df.empty:
            raise ValueError(f"Indicator '{indicator_id}' returned no rows")

        resolved_key = _resolve_output_key(
            result_df.columns,
            output_key=output_key,
            indicator_id=indicator_id,
        )
        feature_values = np.asarray(
            pd.to_numeric(result_df[resolved_key], errors="coerce"),
            dtype=np.float64,
        )
        featured[output_column] = feature_values

    return featured


def _extract_indicator_specs(strategy: StrategyDefinition) -> list[dict[str, Any]]:
    raw = strategy.metadata.get("indicator_specs", ())
    if not isinstance(raw, Iterable):
        raise ValueError("strategy metadata 'indicator_specs' must be an iterable")

    specs: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("strategy metadata 'indicator_specs' entries must be dictionaries")
        if "indicator_id" not in entry:
            raise ValueError("strategy indicator spec is missing 'indicator_id'")
        specs.append(entry)
    return specs


IndicatorRunner = Callable[[str, pd.DataFrame, dict[str, Any] | None], pd.DataFrame]


def _import_indicator_runner() -> IndicatorRunner:
    try:
        from indicator_engine import run
    except ModuleNotFoundError:
        _append_monorepo_lib_path("indicator_engine")
        try:
            from indicator_engine import run
        except ModuleNotFoundError as exc:
            raise RuntimeError("indicator_engine is required for feature computation") from exc
    return run


def _build_indicator_input_frame(bars: pd.DataFrame) -> pd.DataFrame:
    field_columns = ["open", "high", "low", "close", "volume"]
    frame = bars.loc[:, field_columns].copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(bars["timestamp_ms"], unit="ms", utc=True))
    return frame


def _resolve_output_key(
    columns: pd.Index,
    *,
    output_key: Any,
    indicator_id: str,
) -> str:
    if output_key is not None:
        key = str(output_key)
        if key not in columns:
            raise ValueError(
                "Indicator "
                f"'{indicator_id}' output key '{key}' was not found in columns {list(columns)}"
            )
        return key

    if len(columns) == 1:
        return str(columns[0])

    raise ValueError(
        "Indicator "
        f"'{indicator_id}' returned multiple outputs {list(columns)} but no output_key was provided"
    )


def _append_monorepo_lib_path(lib_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    lib_path = repo_root / "libs" / lib_name
    as_text = str(lib_path)
    if lib_path.exists() and as_text not in sys.path:
        sys.path.append(as_text)
