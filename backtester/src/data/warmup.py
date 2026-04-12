"""Warmup window sizing and deterministic feature trimming."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

import numpy as np
import pandas as pd
from strategies.base import StrategyDefinition

TIMEFRAME_TO_MINUTES: Final[dict[str, int]] = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "H12": 720,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}


def compute_required_warmup_bars(strategy: StrategyDefinition) -> int:
    """Compute required warmup bars from strategy indicator metadata."""

    configured = _coerce_warmup_bars(strategy.metadata.get("warmup_bars", 1))
    indicator_specs = strategy.metadata.get("indicator_specs", ())
    if not indicator_specs:
        return configured

    specs = _coerce_indicator_specs(indicator_specs)
    get_registry = _import_indicator_registry_loader()
    registry = get_registry()

    warmups = [configured]
    for spec in specs:
        indicator_id = str(spec["indicator_id"])
        params = dict(spec.get("params", {}))
        try:
            indicator = registry.get(indicator_id)
        except KeyError as exc:
            raise ValueError(f"Unknown indicator '{indicator_id}' in strategy metadata") from exc
        warmups.append(int(indicator.spec.warmup(params)))

    return max(1, max(warmups))


def compute_fetch_start_ms(*, start_ms: int, timeframe: str, warmup_bars: int) -> int:
    """Shift fetch start backward to cover warmup requirements."""

    if warmup_bars <= 1:
        return start_ms

    minutes = _timeframe_to_minutes(timeframe)
    offset_ms = (warmup_bars - 1) * minutes * 60_000
    return max(0, start_ms - offset_ms)


def trim_bars_for_execution(
    *,
    bars: pd.DataFrame,
    required_features: Sequence[str],
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """Trim rows to feature-complete data inside the requested time window."""

    trimmed = bars.copy()
    if required_features:
        missing = [column for column in required_features if column not in trimmed.columns]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"bars is missing required feature columns: {missing_text}")

        feature_frame = trimmed.loc[:, list(required_features)].replace([np.inf, -np.inf], np.nan)
        valid_rows = feature_frame.notna().all(axis=1)
        trimmed = trimmed.loc[valid_rows].copy()

    trimmed = trimmed.loc[
        (trimmed["timestamp_ms"] >= int(start_ms)) & (trimmed["timestamp_ms"] < int(end_ms))
    ].copy()
    trimmed.sort_values("timestamp_ms", kind="mergesort", inplace=True)
    trimmed.reset_index(drop=True, inplace=True)

    if trimmed.empty:
        raise ValueError(
            "No executable bars remain after warmup/feature trimming for the requested window"
        )

    return trimmed


def _coerce_warmup_bars(value: Any) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, coerced)


def _coerce_indicator_specs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Iterable):
        raise ValueError("strategy metadata 'indicator_specs' must be an iterable")
    specs: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("strategy metadata 'indicator_specs' entries must be dictionaries")
        if "indicator_id" not in entry:
            raise ValueError("strategy indicator spec is missing 'indicator_id'")
        specs.append(entry)
    return specs


def _import_indicator_registry_loader():
    try:
        from indicator_engine import get_registry
    except ModuleNotFoundError:
        _append_monorepo_lib_path("indicator_engine")
        try:
            from indicator_engine import get_registry
        except ModuleNotFoundError as exc:
            raise RuntimeError("indicator_engine is required for warmup inference") from exc
    return get_registry


def _append_monorepo_lib_path(lib_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    lib_path = repo_root / "libs" / lib_name
    as_text = str(lib_path)
    if lib_path.exists() and as_text not in sys.path:
        sys.path.append(as_text)


def _timeframe_to_minutes(timeframe: str) -> int:
    normalized = str(timeframe).upper()
    if normalized not in TIMEFRAME_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe code: {timeframe}")
    return TIMEFRAME_TO_MINUTES[normalized]
