"""Indicator-engine feature integration for vectorized backtests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition


def build_feature_frame(
    *,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
) -> pd.DataFrame:
    """Attach strategy-required indicator features to normalized bars."""

    indicator_requirements = _extract_indicator_requirements(strategy)
    if not indicator_requirements:
        return bars.copy()

    run_indicator = _import_indicator_runner()
    feature_input = _build_indicator_input_frame(bars)
    featured = bars.copy()

    for requirement in indicator_requirements:
        indicator_id = requirement.indicator_id
        params = dict(requirement.parameters)
        output_column = requirement.feature_name

        result_df = run_indicator(indicator_id, feature_input, params)
        if result_df.empty:
            raise ValueError(f"Indicator '{indicator_id}' returned no rows")

        resolved_key = _resolve_output_key(
            result_df.columns,
            output_key=requirement.output_key,
            indicator_id=indicator_id,
        )
        feature_values = np.asarray(
            pd.to_numeric(result_df[resolved_key], errors="coerce"),
            dtype=np.float64,
        )
        featured[output_column] = feature_values

    return featured


def _extract_indicator_requirements(
    strategy: StrategyDefinition,
) -> list[IndicatorFeatureRequirement]:
    return list(strategy.indicator_requirements)


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
