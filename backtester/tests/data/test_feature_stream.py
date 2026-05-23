import unittest

from data.feature_stream import EventDrivenFeatureStream
from domain.types import BarView, ExecutionArrayBundle, FeatureMatrix, SignalMatrix
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class TestEventDrivenFeatureStream(unittest.TestCase):
    def _bar(self, timestamp_ms: int, close: float, *, open_price: float | None = None) -> BarView:
        price = close if open_price is None else open_price
        return BarView(
            timestamp_ms=timestamp_ms,
            symbol="AAPL",
            open=price,
            high=max(price, close),
            low=min(price, close),
            close=close,
            volume=1_000.0,
        )

    def test_sma_features_are_hidden_until_all_requirements_complete_warmup(self) -> None:
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        stream = EventDrivenFeatureStream(strategy=strategy, symbol="AAPL", timeframe="1m")

        first = stream.update(self._bar(1_000, 1.0))
        second = stream.update(self._bar(2_000, 2.0))
        third = stream.update(self._bar(3_000, 3.0))

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertIsNotNone(third)
        assert third is not None
        self.assertEqual(third.timestamp_ms, 3_000)
        self.assertEqual(third.symbol, "AAPL")
        self.assertAlmostEqual(third.features["sma_fast"], 2.5)
        self.assertAlmostEqual(third.features["sma_slow"], 2.0)

    def test_sma_snapshots_are_sequential_and_do_not_include_future_bars(self) -> None:
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        stream = EventDrivenFeatureStream(strategy=strategy, symbol="AAPL", timeframe="1m")

        stream.update(self._bar(1_000, 1.0))
        stream.update(self._bar(2_000, 2.0))
        third = stream.update(self._bar(3_000, 3.0))
        fourth = stream.update(self._bar(4_000, 100.0))

        self.assertIsNotNone(third)
        self.assertIsNotNone(fourth)
        assert third is not None
        assert fourth is not None
        self.assertAlmostEqual(third.features["sma_fast"], 2.5)
        self.assertAlmostEqual(third.features["sma_slow"], 2.0)
        self.assertAlmostEqual(fourth.features["sma_fast"], 51.5)
        self.assertAlmostEqual(fourth.features["sma_slow"], 35.0)

    def test_indicator_requirements_receive_ohlcv_fields(self) -> None:
        strategy = _open_sma_strategy()
        stream = EventDrivenFeatureStream(strategy=strategy, symbol="AAPL", timeframe="1m")

        first = stream.update(self._bar(1_000, close=1.0, open_price=10.0))
        second = stream.update(self._bar(2_000, close=2.0, open_price=20.0))

        self.assertIsNone(first)
        self.assertIsNotNone(second)
        assert second is not None
        self.assertAlmostEqual(second.features["open"], 20.0)
        self.assertAlmostEqual(second.features["close"], 2.0)
        self.assertAlmostEqual(second.features["open_sma"], 15.0)

    def test_non_finite_indicator_values_prevent_feature_snapshot(self) -> None:
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        stream = EventDrivenFeatureStream(strategy=strategy, symbol="AAPL", timeframe="1m")

        snapshots = [
            stream.update(self._bar(1_000, 1.0)),
            stream.update(self._bar(2_000, 2.0)),
            stream.update(self._bar(3_000, float("nan"))),
            stream.update(self._bar(4_000, 4.0)),
        ]

        self.assertEqual(snapshots, [None, None, None, None])


def _open_sma_strategy() -> StrategyDefinition:
    def decision_model(features: FeatureMatrix) -> SignalMatrix:
        return SignalMatrix(
            timestamp_ms=features.timestamp_ms,
            signals_by_symbol={"AAPL": [0] * len(features.timestamp_ms)},
        )

    def position_builder(signals: SignalMatrix) -> ExecutionArrayBundle:
        return ExecutionArrayBundle(
            timestamp_ms=signals.timestamp_ms,
            target_quantity_by_symbol={"AAPL": [0.0] * len(signals.timestamp_ms)},
        )

    return StrategyDefinition(
        strategy_id="open_sma_fixture",
        feature_specs=("open_sma",),
        decision_model=decision_model,
        position_builder=position_builder,
        indicator_requirements=(
            IndicatorFeatureRequirement(
                feature_name="open_sma",
                indicator_id="sma",
                output_key="sma",
                parameters={"window": 2, "source": "open"},
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
