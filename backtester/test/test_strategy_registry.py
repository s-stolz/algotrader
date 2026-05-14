import unittest

from domain.types import StrategyConfig
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
            strategy.metadata["indicator_specs"][0]["params"],
            {"window": 2, "source": "close"},
        )
        self.assertEqual(
            strategy.metadata["indicator_specs"][1]["params"],
            {"window": 3, "source": "close"},
        )

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
