import unittest

from data.warmup import compute_required_warmup_bars
from domain.enums import AllowedDirections
from domain.types import FeatureMatrix, StrategyConfig
from strategies.examples.macd_ema import build_macd_ema_strategy
from strategies.registry import (
    InvalidParameterCombinationError,
    resolve_strategy,
    strategy_catalog,
    validate_parameters,
)


class TestMacdEmaStrategy(unittest.TestCase):
    def test_crossovers_require_the_price_filter_in_both_runtimes(self) -> None:
        model = build_macd_ema_strategy().require_v1_parity_model()
        for previous_macd, current_macd, close, expected in (
            (-1.0, 1.0, 11.0, 1),
            (-1.0, 1.0, 9.0, 0),
            (-1.0, 1.0, 10.0, 0),
            (1.0, -1.0, 9.0, -1),
            (1.0, -1.0, 11.0, 0),
            (1.0, -1.0, 10.0, 0),
            (1.0, 2.0, 11.0, 0),
            (-1.0, -2.0, 9.0, 0),
            (0.0, 1.0, 11.0, 1),
            (0.0, -1.0, 9.0, -1),
            (-1.0, 1.0, float("nan"), 0),
        ):
            with self.subTest(previous=previous_macd, current=current_macd, close=close):
                previous = {"macd": previous_macd, "macd_signal": 0.0, "close": 10.0, "ema": 10.0}
                current = {"macd": current_macd, "macd_signal": 0.0, "close": close, "ema": 10.0}
                features = FeatureMatrix(
                    timestamp_ms=[0, 1],
                    features_by_symbol={
                        "TEST": {key: [previous[key], current[key]] for key in current}
                    },
                )
                self.assertEqual(
                    model.build_signals(features).signals_by_symbol["TEST"], [0, expected]
                )
                self.assertEqual(
                    model.evaluate_sequential_signal(previous=previous, current=current), expected
                )
                self.assertEqual(
                    model.evaluate_sequential_signal(previous=None, current=current), 0
                )

    def test_filtered_opposite_cross_holds_until_a_qualifying_cross(self) -> None:
        strategy = build_macd_ema_strategy(quantity=2.0)
        features = FeatureMatrix(
            timestamp_ms=list(range(5)),
            features_by_symbol={
                "TEST": {
                    "macd": [-1.0, 1.0, -1.0, 1.0, -1.0],
                    "macd_signal": [0.0] * 5,
                    "close": [10.0, 11.0, 11.0, 11.0, 9.0],
                    "ema": [10.0] * 5,
                }
            },
        )
        for direction, expected in (
            (AllowedDirections.LONG_AND_SHORT, [0.0, 2.0, 2.0, 2.0, -2.0]),
            (AllowedDirections.LONG_ONLY, [0.0, 2.0, 2.0, 2.0, 0.0]),
            (AllowedDirections.SHORT_ONLY, [0.0, 0.0, 0.0, 0.0, -2.0]),
        ):
            with self.subTest(direction=direction):
                targets = strategy.build_execution_targets(features, allowed_directions=direction)
                self.assertEqual(targets.target_quantity_by_symbol["TEST"], expected)

    def test_catalog_defaults_validation_and_warmup(self) -> None:
        entry = next(item for item in strategy_catalog() if item["strategy_id"] == "macd_ema")
        self.assertEqual(entry["strategy_version"], 1)
        resolved = validate_parameters(StrategyConfig("macd_ema"))
        self.assertEqual(resolved.parameters["ema_window"], 200)
        self.assertEqual(compute_required_warmup_bars(resolve_strategy(resolved)), 200)
        strategy = build_macd_ema_strategy(ema_window=3)
        self.assertEqual(compute_required_warmup_bars(strategy), 35)
        with self.assertRaises(InvalidParameterCombinationError) as caught:
            validate_parameters(StrategyConfig("macd_ema", {"fast_window": 26}))
        self.assertEqual(caught.exception.fields, ("fast_window", "slow_window"))
