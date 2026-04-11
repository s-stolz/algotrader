"""Strategy contracts shared by engine implementations."""

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple

from domain.types import ExecutionArrayBundle, FeatureMatrix, SignalMatrix

DecisionModel = Callable[[FeatureMatrix], SignalMatrix]
PositionBuilder = Callable[[SignalMatrix], ExecutionArrayBundle]
ExecutionTransformer = Callable[[ExecutionArrayBundle], ExecutionArrayBundle]


@dataclass
class StrategyDefinition:
    strategy_id: str
    feature_specs: Tuple[str, ...]
    decision_model: DecisionModel
    position_builder: PositionBuilder
    sizing_model: Optional[ExecutionTransformer] = None
    risk_rules: Sequence[ExecutionTransformer] = field(default_factory=tuple)

    def build_execution_targets(self, features: FeatureMatrix) -> ExecutionArrayBundle:
        """Evaluates vectorized strategy flow into execution target arrays."""
        signals = self.decision_model(features)
        targets = self.position_builder(signals)
        if self.sizing_model is not None:
            targets = self.sizing_model(targets)
        for risk_rule in self.risk_rules:
            targets = risk_rule(targets)
        return targets
