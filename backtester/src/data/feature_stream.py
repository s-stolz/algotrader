"""Sequential feature adapter for event-driven bar execution."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

from domain.types import BarView
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition

BAR_FIELD_ORDER = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class FeatureSnapshot:
    timestamp_ms: int
    symbol: str
    features: dict[str, float]


class _RegisteredFeature(NamedTuple):
    requirement: IndicatorFeatureRequirement
    engine: Any


class EventDrivenFeatureStream:
    """Feed completed bars through indicator-engine update registrations."""

    def __init__(
        self,
        *,
        strategy: StrategyDefinition,
        symbol: str,
        timeframe: str,
        history_rows: int = 5000,
    ) -> None:
        self._strategy = strategy
        self._symbol = str(symbol)
        self._timeframe = str(timeframe)
        self._registered_features = tuple(
            self._register_requirement(requirement, history_rows=history_rows)
            for requirement in strategy.indicator_requirements
        )

    def update(self, bar: BarView) -> FeatureSnapshot | None:
        """Update streaming indicators with one completed bar.

        Returns a finite feature snapshot when every strategy indicator
        requirement has emitted a usable value for the bar timestamp.
        """

        if bar.symbol != self._symbol:
            raise ValueError(
                f"Event-driven feature stream expected symbol {self._symbol!r} "
                f"but received {bar.symbol!r}"
            )

        row = _bar_to_update_row(bar)
        features = _base_feature_values(bar)

        snapshot_ready = True
        for registered in self._registered_features:
            requirement = registered.requirement
            updated = registered.engine.on_bar(
                timeframe=self._timeframe,
                timestamp_ms=int(bar.timestamp_ms),
                new_row=row,
            )
            tensor = updated.get(requirement.indicator_id)
            if tensor is None:
                snapshot_ready = False
                continue

            value = _extract_feature_value(
                tensor=tensor,
                requirement=requirement,
                symbol=self._symbol,
            )
            if not math.isfinite(value):
                snapshot_ready = False
                continue
            features[requirement.feature_name] = value

        if not snapshot_ready:
            return None

        return FeatureSnapshot(
            timestamp_ms=int(bar.timestamp_ms),
            symbol=self._symbol,
            features=features,
        )

    def _register_requirement(
        self,
        requirement: IndicatorFeatureRequirement,
        *,
        history_rows: int,
    ) -> _RegisteredFeature:
        get_update_engine, history_policy_cls, param_grid_cls = _import_update_engine_parts()
        engine = get_update_engine(
            history=history_policy_cls(mode="rolling", max_rows=history_rows)
        )
        engine.register_indicator(
            indicator_id=requirement.indicator_id,
            timeframe=self._timeframe,
            assets=[self._symbol],
            fields=BAR_FIELD_ORDER,
            param_grid=param_grid_cls(dict(requirement.parameters)),
        )
        return _RegisteredFeature(requirement=requirement, engine=engine)


def _bar_to_update_row(bar: BarView) -> np.ndarray:
    return np.asarray(
        [
            [
                float(bar.open),
                float(bar.high),
                float(bar.low),
                float(bar.close),
                float(bar.volume),
            ]
        ],
        dtype=np.float64,
    )


def _base_feature_values(bar: BarView) -> dict[str, float]:
    return {
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "volume": float(bar.volume),
    }


def _extract_feature_value(
    *,
    tensor: Any,
    requirement: IndicatorFeatureRequirement,
    symbol: str,
) -> float:
    return float(
        tensor.latest_value(
            asset=symbol,
            output=requirement.output_key,
        )
    )


def _import_update_engine_parts() -> tuple[Any, Any, Any]:
    try:
        from indicator_engine.core.history import HistoryPolicy
        from indicator_engine.core.params import ParamGrid
        from indicator_engine.defaults import get_update_engine
    except ModuleNotFoundError:
        _append_monorepo_lib_path("indicator_engine")
        try:
            from indicator_engine.core.history import HistoryPolicy
            from indicator_engine.core.params import ParamGrid
            from indicator_engine.defaults import get_update_engine
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "indicator_engine is required for event-driven feature computation"
            ) from exc

    return get_update_engine, HistoryPolicy, ParamGrid


def _append_monorepo_lib_path(lib_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    lib_path = repo_root / "libs" / lib_name
    as_text = str(lib_path)
    if lib_path.exists() and as_text not in sys.path:
        sys.path.append(as_text)
