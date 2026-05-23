"""Strategy contracts shared by engine implementations."""

import math
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from domain.types import ExecutionArrayBundle, FeatureMatrix, ProtectiveExitSpec, SignalMatrix

from strategies.conditions import ConditionRule

DecisionModel = Callable[[FeatureMatrix], SignalMatrix]
PositionBuilder = Callable[[SignalMatrix], ExecutionArrayBundle]
ExecutionTransformer = Callable[[ExecutionArrayBundle], ExecutionArrayBundle]


@dataclass(frozen=True)
class IndicatorFeatureRequirement:
    feature_name: str
    indicator_id: str
    output_key: str | None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.feature_name, str):
            raise ValueError(
                "indicator feature requirement feature_name must be a non-empty string"
            )
        feature_name = self.feature_name.strip()
        if not feature_name:
            raise ValueError("indicator feature requirement feature_name must be non-empty")

        if not isinstance(self.indicator_id, str):
            raise ValueError(
                "indicator feature requirement indicator_id must be a non-empty string"
            )
        indicator_id = self.indicator_id.strip()
        if not indicator_id:
            raise ValueError("indicator feature requirement indicator_id must be non-empty")

        if self.output_key is not None and not isinstance(self.output_key, str):
            raise ValueError("indicator feature requirement output_key must be a string or None")
        output_key = None if self.output_key is None else self.output_key.strip()
        if output_key == "":
            raise ValueError("indicator feature requirement output_key must be non-empty")

        if not isinstance(self.parameters, MappingABC):
            raise ValueError("indicator feature requirement parameters must be a mapping")

        object.__setattr__(self, "feature_name", feature_name)
        object.__setattr__(self, "indicator_id", indicator_id)
        object.__setattr__(self, "output_key", output_key)
        object.__setattr__(self, "parameters", dict(self.parameters))


@dataclass(frozen=True)
class BarStrategyModel:
    entry_conditions: Tuple[ConditionRule, ...]
    exit_conditions: Tuple[ConditionRule, ...]
    target_quantity: float
    long_only: bool = True
    protective_exit: ProtectiveExitSpec = field(default_factory=ProtectiveExitSpec)

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.target_quantity)) or float(self.target_quantity) <= 0.0:
            raise ValueError("bar strategy target_quantity must be positive and finite")
        if not self.long_only:
            raise ValueError("v1 bar strategy model supports long_only=True only")
        if not isinstance(self.protective_exit, ProtectiveExitSpec):
            raise ValueError("bar strategy protective_exit must be a ProtectiveExitSpec")

        object.__setattr__(self, "entry_conditions", tuple(self.entry_conditions))
        object.__setattr__(self, "exit_conditions", tuple(self.exit_conditions))
        object.__setattr__(self, "target_quantity", float(self.target_quantity))

    def build_signals(self, features: FeatureMatrix) -> SignalMatrix:
        signals_by_symbol: dict[str, list[int]] = {}

        for symbol, feature_map in features.features_by_symbol.items():
            entries = _combine_condition_masks(
                conditions=self.entry_conditions,
                feature_map=feature_map,
                expected_size=len(features.timestamp_ms),
            )
            exits = _combine_condition_masks(
                conditions=self.exit_conditions,
                feature_map=feature_map,
                expected_size=len(features.timestamp_ms),
            )

            signal = np.zeros(len(features.timestamp_ms), dtype=np.int64)
            signal[entries] = 1
            signal[exits] = -1
            signals_by_symbol[symbol] = signal.tolist()

        return SignalMatrix(
            timestamp_ms=features.timestamp_ms,
            signals_by_symbol=signals_by_symbol,
        )

    def build_positions(self, signals: SignalMatrix) -> ExecutionArrayBundle:
        target_by_symbol: dict[str, list[float]] = {}

        for symbol, raw_signals in signals.signals_by_symbol.items():
            signal_arr = np.asarray(raw_signals, dtype=np.int64)
            target = np.full(signal_arr.shape[0], np.nan, dtype=np.float64)
            target[signal_arr > 0] = self.target_quantity
            target[signal_arr < 0] = 0.0

            target_series = pd.Series(target, dtype=np.float64).ffill().fillna(0.0)
            target_by_symbol[symbol] = np.asarray(target_series, dtype=np.float64).tolist()

        return ExecutionArrayBundle(
            timestamp_ms=signals.timestamp_ms,
            target_quantity_by_symbol=target_by_symbol,
        )

    def build_execution_targets(self, features: FeatureMatrix) -> ExecutionArrayBundle:
        return self.build_positions(self.build_signals(features))

    def evaluate_sequential_signal(
        self,
        *,
        previous: Mapping[str, float] | None,
        current: Mapping[str, float],
    ) -> int:
        if any(
            condition.evaluate_sequential(previous=previous, current=current)
            for condition in self.exit_conditions
        ):
            return -1
        if any(
            condition.evaluate_sequential(previous=previous, current=current)
            for condition in self.entry_conditions
        ):
            return 1
        return 0


@dataclass
class StrategyDefinition:
    strategy_id: str
    feature_specs: Tuple[str, ...]
    decision_model: DecisionModel
    position_builder: PositionBuilder
    indicator_requirements: Tuple[IndicatorFeatureRequirement, ...] = field(default_factory=tuple)
    bar_model: Optional[BarStrategyModel] = None
    sizing_model: Optional[ExecutionTransformer] = None
    risk_rules: Sequence[ExecutionTransformer] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_v1_parity_compatible(self) -> bool:
        return self.bar_model is not None

    def require_v1_parity_model(self) -> BarStrategyModel:
        if self.bar_model is None:
            raise ValueError(
                f"Strategy '{self.strategy_id}' is callback-only and is not v1 parity-compatible"
            )
        return self.bar_model

    def build_execution_targets(self, features: FeatureMatrix) -> ExecutionArrayBundle:
        """Evaluates vectorized strategy flow into execution target arrays."""
        if self.bar_model is not None:
            targets = self.bar_model.build_execution_targets(features)
        else:
            signals = self.decision_model(features)
            targets = self.position_builder(signals)
        if self.sizing_model is not None:
            targets = self.sizing_model(targets)
        for risk_rule in self.risk_rules:
            targets = risk_rule(targets)
        return targets


def _combine_condition_masks(
    *,
    conditions: Sequence[ConditionRule],
    feature_map: Mapping[str, Sequence[float]],
    expected_size: int,
) -> np.ndarray:
    if not conditions:
        return np.zeros(expected_size, dtype=np.bool_)

    combined = np.zeros(expected_size, dtype=np.bool_)
    for condition in conditions:
        mask = np.asarray(condition.evaluate_vectorized(feature_map), dtype=np.bool_)
        if mask.size != expected_size:
            raise ValueError(
                "condition result length must match feature timestamp length "
                f"for features {condition.left_feature}, {condition.right_feature}"
            )
        combined |= mask
    return combined
