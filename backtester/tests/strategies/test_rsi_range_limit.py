import unittest

from domain.enums import OrderSide
from domain.types import FeatureMatrix
from strategies.examples.rsi_range_limit import build_rsi_range_limit


class RsiRangeLimitTests(unittest.TestCase):
    def test_crossings_are_single_causal_orders_and_evaluators_agree(self):
        strategy = build_rsi_range_limit(tick_size=0.01)
        model = strategy.order_model
        assert model is not None
        rsi = [20, 30, 29, 15, 40, 70, 71, 80, 50, 29]
        snapshots = [
            {"rsi": value, "lowest_low": 90 + i, "highest_high": 110 + i}
            for i, value in enumerate(rsi)
        ]
        boundaries = [(i + 1) * 60000 for i in range(len(rsi))]
        features = FeatureMatrix(
            [i * 60000 for i in range(len(rsi))],
            {"TEST": {key: [row[key] for row in snapshots] for key in snapshots[0]}},
        )
        commands = model.build_commands(features, boundaries)
        previous = None
        sequential = []
        for boundary, snapshot in zip(boundaries, snapshots, strict=True):
            sequential.extend(model.evaluate_close(boundary, previous, snapshot))
            previous = snapshot
        self.assertEqual(commands, sequential)
        self.assertEqual([c.effective_at_ms for c in commands], [180000, 420000, 600000])
        orders = [c.order for c in commands if c.order is not None]
        self.assertEqual(len(orders), len(commands))
        self.assertEqual([o.side for o in orders], [OrderSide.BUY, OrderSide.SELL, OrderSide.BUY])
        self.assertEqual([o.price for o in orders], [92, 116, 99])
        self.assertTrue(all(o.only_when_flat and o.lifetime_bars == 10 for o in orders))
        assert orders[0].protection is not None
        self.assertEqual(orders[0].protection.stop_loss_distance, 1)
        self.assertEqual(orders[0].protection.take_profit_distance, 2)
        for end in range(1, len(rsi)):
            prefix = FeatureMatrix(
                features.timestamp_ms[:end],
                {"TEST": {k: v[:end] for k, v in features.features_by_symbol["TEST"].items()}},
            )
            self.assertEqual(
                list(model.build_commands(prefix, boundaries[:end])),
                [c for c in commands if c.effective_at_ms <= boundaries[end - 1]],
            )

    def test_parameter_validation(self):
        for overrides in (
            {"rsi_lower": 70},
            {"range_period": 0},
            {"tick_size": 0},
            {"quantity": float("nan")},
            {"stop_loss_ticks": 0},
            {"range_period": 5001},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                build_rsi_range_limit(**({"tick_size": 0.01} | overrides))
