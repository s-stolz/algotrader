import unittest

from domain.types import StrategyConfig
from strategies.base import IndicatorFeatureRequirement
from strategies.registry import resolve_strategy


class TestStrategyRegistry(unittest.TestCase):
    def test_resolves_sma_crossover_from_request_parameters(self) -> None:
        strategy = resolve_strategy(
            StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 2.5},
            )
        )

        self.assertEqual(strategy.strategy_id, "sma_crossover")
        self.assertEqual(strategy.feature_specs, ("sma_fast", "sma_slow"))
        self.assertEqual(strategy.metadata["warmup_bars"], 3)
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
        self.assertTrue(strategy.is_v1_parity_compatible)

    def test_unknown_strategy_id_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown strategy_id 'not_registered'"):
            resolve_strategy(StrategyConfig(strategy_id="not_registered"))

    def test_invalid_strategy_parameters_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid parameters for strategy 'sma_crossover'"):
            resolve_strategy(
                StrategyConfig(
                    strategy_id="sma_crossover",
                    parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0, "extra": 5},
                )
            )


if __name__ == "__main__":
    unittest.main()
