import unittest

from domain.types import ExecutionArrayBundle, FeatureMatrix, SignalMatrix
from strategies.base import StrategyDefinition


class TestStrategyDefinition(unittest.TestCase):
    def test_build_execution_targets_applies_decision_sizing_and_risk(self) -> None:
        def decision_model(features: FeatureMatrix) -> SignalMatrix:
            return SignalMatrix(
                timestamp_ms=features.timestamp_ms,
                signals_by_symbol={"AAPL": [0, 1, 1]},
            )

        def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
            _ = signals
            return ExecutionArrayBundle(
                timestamp_ms=[1, 2, 3],
                target_quantity_by_symbol={"AAPL": [0.0, 1.0, -1.0]},
            )

        def sizing_model(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
            scaled = [qty * 2.0 for qty in bundle.target_quantity_by_symbol["AAPL"]]
            return ExecutionArrayBundle(
                timestamp_ms=bundle.timestamp_ms,
                target_quantity_by_symbol={"AAPL": scaled},
            )

        def long_only_rule(bundle: ExecutionArrayBundle) -> ExecutionArrayBundle:
            clamped = [max(0.0, qty) for qty in bundle.target_quantity_by_symbol["AAPL"]]
            return ExecutionArrayBundle(
                timestamp_ms=bundle.timestamp_ms,
                target_quantity_by_symbol={"AAPL": clamped},
            )

        strategy = StrategyDefinition(
            strategy_id="sma_crossover",
            feature_specs=("sma_fast", "sma_slow"),
            decision_model=decision_model,
            position_builder=position_builder,
            sizing_model=sizing_model,
            risk_rules=(long_only_rule,),
        )
        features = FeatureMatrix(
            timestamp_ms=[1, 2, 3],
            features_by_symbol={"AAPL": {"sma_fast": [1.0, 2.0, 3.0], "sma_slow": [1.5, 1.7, 2.1]}},
        )

        bundle = strategy.build_execution_targets(features)

        self.assertEqual(bundle.timestamp_ms, [1, 2, 3])
        self.assertEqual(bundle.target_quantity_by_symbol["AAPL"], [0.0, 2.0, 0.0])


if __name__ == "__main__":
    unittest.main()
