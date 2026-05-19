import unittest
from typing import Any, cast
from unittest.mock import patch

import pandas as pd
from data.indicators import build_feature_frame
from domain.types import ExecutionArrayBundle, FeatureMatrix, SignalMatrix
from strategies.base import IndicatorFeatureRequirement, ProtectiveExitSpec, StrategyDefinition
from strategies.conditions import ConditionRule
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class TestStrategyDefinition(unittest.TestCase):
    def test_indicator_feature_requirement_captures_typed_indicator_mapping(self) -> None:
        requirement = IndicatorFeatureRequirement(
            feature_name="sma_fast",
            indicator_id="sma",
            output_key="sma",
            parameters={"window": 2, "source": "close"},
        )

        self.assertEqual(requirement.feature_name, "sma_fast")
        self.assertEqual(requirement.indicator_id, "sma")
        self.assertEqual(requirement.output_key, "sma")
        self.assertEqual(requirement.parameters, {"window": 2, "source": "close"})

    def test_indicator_feature_requirement_validates_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "feature_name"):
            IndicatorFeatureRequirement(
                feature_name="",
                indicator_id="sma",
                output_key="sma",
                parameters={"window": 2},
            )

        with self.assertRaisesRegex(ValueError, "indicator_id"):
            IndicatorFeatureRequirement(
                feature_name="sma_fast",
                indicator_id="",
                output_key="sma",
                parameters={"window": 2},
            )

        with self.assertRaisesRegex(ValueError, "parameters"):
            IndicatorFeatureRequirement(
                feature_name="sma_fast",
                indicator_id="sma",
                output_key="sma",
                parameters=cast(Any, (("window", 2),)),
            )

        with self.assertRaisesRegex(ValueError, "feature_name"):
            IndicatorFeatureRequirement(
                feature_name=cast(Any, None),
                indicator_id="sma",
                output_key="sma",
                parameters={"window": 2},
            )

        with self.assertRaisesRegex(ValueError, "indicator_id"):
            IndicatorFeatureRequirement(
                feature_name="sma_fast",
                indicator_id=cast(Any, None),
                output_key="sma",
                parameters={"window": 2},
            )

        with self.assertRaisesRegex(ValueError, "output_key"):
            IndicatorFeatureRequirement(
                feature_name="sma_fast",
                indicator_id="sma",
                output_key=cast(Any, 123),
                parameters={"window": 2},
            )

    def test_protective_exit_spec_accepts_optional_positive_stop_loss_pct(self) -> None:
        self.assertIsNone(ProtectiveExitSpec().stop_loss_pct)
        self.assertEqual(ProtectiveExitSpec(stop_loss_pct=2).stop_loss_pct, 2.0)

    def test_protective_exit_spec_rejects_invalid_stop_loss_pct(self) -> None:
        invalid_values = (0.0, -1.0, float("inf"), float("-inf"), float("nan"), 100.0)

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "stop_loss_pct"):
                    ProtectiveExitSpec(stop_loss_pct=value)

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

    def test_callback_only_strategy_is_not_v1_parity_compatible(self) -> None:
        def decision_model(features: FeatureMatrix) -> SignalMatrix:
            return SignalMatrix(timestamp_ms=features.timestamp_ms, signals_by_symbol={})

        def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
            return ExecutionArrayBundle(
                timestamp_ms=signals.timestamp_ms,
                target_quantity_by_symbol={},
            )

        strategy = StrategyDefinition(
            strategy_id="callback_only_fixture",
            feature_specs=(),
            decision_model=decision_model,
            position_builder=position_builder,
        )

        self.assertFalse(strategy.is_v1_parity_compatible)
        with self.assertRaisesRegex(ValueError, "callback-only"):
            strategy.require_v1_parity_model()

    def test_sma_crossover_uses_declarative_bar_model_and_preserves_targets(self) -> None:
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=2.5)

        self.assertTrue(strategy.is_v1_parity_compatible)
        self.assertEqual(strategy.feature_specs, ("sma_fast", "sma_slow"))
        self.assertEqual(
            strategy.indicator_requirements,
            (
                IndicatorFeatureRequirement(
                    feature_name="sma_fast",
                    indicator_id="sma",
                    output_key="sma",
                    parameters={"window": 2, "source": "close"},
                ),
                IndicatorFeatureRequirement(
                    feature_name="sma_slow",
                    indicator_id="sma",
                    output_key="sma",
                    parameters={"window": 3, "source": "close"},
                ),
            ),
        )

        bar_model = strategy.require_v1_parity_model()
        self.assertEqual(bar_model.protective_exit, ProtectiveExitSpec())
        self.assertEqual(
            bar_model.entry_conditions,
            (ConditionRule.crossover("sma_fast", "sma_slow"),),
        )
        self.assertEqual(
            bar_model.exit_conditions,
            (ConditionRule.crossunder("sma_fast", "sma_slow"),),
        )
        self.assertEqual(
            bar_model.evaluate_sequential_signal(
                previous={"sma_fast": 2.0, "sma_slow": 2.0},
                current={"sma_fast": 3.0, "sma_slow": 2.0},
            ),
            1,
        )

        features = FeatureMatrix(
            timestamp_ms=[1, 2, 3, 4, 5],
            features_by_symbol={
                "AAPL": {
                    "sma_fast": [1.0, 2.0, 3.0, 2.0, 1.0],
                    "sma_slow": [2.0, 2.0, 2.0, 2.0, 2.0],
                }
            },
        )

        targets = strategy.build_execution_targets(features)

        self.assertEqual(targets.timestamp_ms, [1, 2, 3, 4, 5])
        self.assertEqual(
            targets.target_quantity_by_symbol["AAPL"],
            [0.0, 0.0, 2.5, 2.5, 0.0],
        )

    def test_sma_crossover_accepts_optional_stop_loss_pct(self) -> None:
        strategy = build_sma_crossover_strategy(
            fast_window=2,
            slow_window=3,
            quantity=2.5,
            stop_loss_pct=4.0,
        )

        bar_model = strategy.require_v1_parity_model()
        self.assertEqual(bar_model.protective_exit, ProtectiveExitSpec(stop_loss_pct=4.0))

    def test_feature_frame_uses_typed_indicator_requirements(self) -> None:
        bars = pd.DataFrame(
            {
                "timestamp_ms": [1_700_000_000_000, 1_700_000_060_000],
                "symbol": ["AAPL", "AAPL"],
                "open": [10.0, 11.0],
                "high": [10.5, 11.5],
                "low": [9.5, 10.5],
                "close": [10.0, 11.0],
                "volume": [100.0, 110.0],
            }
        )

        def decision_model(features: FeatureMatrix) -> SignalMatrix:
            return SignalMatrix(timestamp_ms=features.timestamp_ms, signals_by_symbol={})

        def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
            return ExecutionArrayBundle(
                timestamp_ms=signals.timestamp_ms,
                target_quantity_by_symbol={},
            )

        strategy = StrategyDefinition(
            strategy_id="typed_indicator_fixture",
            feature_specs=("sma_fast",),
            indicator_requirements=(
                IndicatorFeatureRequirement(
                    feature_name="sma_fast",
                    indicator_id="sma",
                    output_key="sma",
                    parameters={"window": 2, "source": "close"},
                ),
            ),
            decision_model=decision_model,
            position_builder=position_builder,
        )
        calls: list[tuple[str, dict]] = []

        def fake_run_indicator(
            indicator_id: str,
            frame: pd.DataFrame,
            params: dict,
        ) -> pd.DataFrame:
            calls.append((indicator_id, params))
            self.assertEqual(frame["close"].tolist(), [10.0, 11.0])
            return pd.DataFrame({"sma": [float("nan"), 10.5]})

        with patch("data.indicators._import_indicator_runner", return_value=fake_run_indicator):
            featured = build_feature_frame(bars=bars, strategy=strategy)

        self.assertEqual(calls, [("sma", {"window": 2, "source": "close"})])
        self.assertIn("sma_fast", featured.columns)
        self.assertEqual(featured["sma_fast"].tolist()[1], 10.5)


if __name__ == "__main__":
    unittest.main()
