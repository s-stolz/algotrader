import unittest

import numpy as np
from domain.enums import ExitReason, GapPolicy, OrderSide
from execution.fills import (
    generate_fills_from_targets,
    generate_fills_from_targets_with_protective_exits,
)


class TestFillGeneration(unittest.TestCase):
    def test_next_bar_open_fill_timing_and_delta(self) -> None:
        result = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4, 5],
            open_prices=[100.0, 101.0, 102.0, 103.0, 104.0],
            target_quantity=[0.0, 1.0, 1.0, 0.0, 0.0],
            gap_policy=GapPolicy.SKIP,
        )

        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].timestamp_ms, 3)
        self.assertEqual(result.fills[0].side, OrderSide.BUY)
        self.assertEqual(result.fills[0].quantity, 1.0)
        self.assertEqual(result.fills[0].price, 102.0)

        self.assertEqual(result.fills[1].timestamp_ms, 5)
        self.assertEqual(result.fills[1].side, OrderSide.SELL)
        self.assertEqual(result.fills[1].quantity, 1.0)
        self.assertEqual(result.fills[1].price, 104.0)

        np.testing.assert_allclose(result.executed_delta, np.array([0.0, 0.0, 1.0, 0.0, -1.0]))
        np.testing.assert_allclose(
            result.executed_notional,
            np.array([0.0, 0.0, 102.0, 0.0, -104.0]),
        )
        np.testing.assert_allclose(result.executed_fees, np.array([0.0, 0.0, 0.0, 0.0, 0.0]))

    def test_invalid_open_for_gap_error_raises(self) -> None:
        with self.assertRaises(ValueError):
            generate_fills_from_targets(
                symbol="AAPL",
                timestamp_ms=[1, 2, 3],
                open_prices=[100.0, 0.0, 102.0],
                target_quantity=[1.0, 1.0, 1.0],
                gap_policy=GapPolicy.ERROR,
            )

    def test_gap_policy_skip_defers_and_aggregates_to_single_net_fill(self) -> None:
        result = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4, 5],
            open_prices=[100.0, 101.0, np.nan, 0.0, 105.0],
            target_quantity=[0.0, 1.0, 2.0, 1.0, 1.0],
            gap_policy=GapPolicy.SKIP,
        )

        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].timestamp_ms, 5)
        self.assertEqual(result.fills[0].side, OrderSide.BUY)
        self.assertEqual(result.fills[0].quantity, 1.0)
        self.assertEqual(result.fills[0].price, 105.0)
        np.testing.assert_allclose(result.executed_delta, np.array([0.0, 0.0, 0.0, 0.0, 1.0]))
        self.assertEqual(result.invalid_open_count, 2)
        self.assertEqual(result.deferred_delta_count, 2)
        self.assertEqual(result.expired_delta_count, 0)
        self.assertEqual(result.executed_deferred_count, 2)
        self.assertEqual(result.tail_expired_delta_count, 0)

    def test_gap_policy_expire_drops_pending_deltas(self) -> None:
        result = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3],
            open_prices=[100.0, 101.0, -1.0],
            target_quantity=[0.0, 1.0, 1.0],
            gap_policy=GapPolicy.EXPIRE,
        )

        self.assertEqual(len(result.fills), 0)
        np.testing.assert_allclose(result.executed_delta, np.array([0.0, 0.0, 0.0]))
        self.assertEqual(result.invalid_open_count, 1)
        self.assertEqual(result.expired_delta_count, 1)
        self.assertEqual(result.tail_expired_delta_count, 0)

    def test_expired_entry_then_flat_target_does_not_open_opposite_position(self) -> None:
        cases = (
            ("long", [1.0, 1.0, 0.0, 0.0]),
            ("short", [-1.0, -1.0, 0.0, 0.0]),
        )

        for direction, target_quantity in cases:
            with self.subTest(direction=direction):
                result = generate_fills_from_targets(
                    symbol="AAPL",
                    timestamp_ms=[1, 2, 3, 4],
                    open_prices=[100.0, 0.0, 99.0, 98.0],
                    target_quantity=target_quantity,
                    gap_policy=GapPolicy.EXPIRE,
                )

                self.assertEqual(result.fills, [])
                np.testing.assert_allclose(result.executed_delta, np.array([0.0] * 4))
                self.assertEqual(result.invalid_open_count, 1)
                self.assertEqual(result.expired_delta_count, 1)
                self.assertEqual(result.tail_expired_delta_count, 0)

    def test_expired_protective_entry_then_flat_signal_does_not_open_opposite_position(
        self,
    ) -> None:
        result = generate_fills_from_targets_with_protective_exits(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4],
            open_prices=[100.0, 0.0, 99.0, 98.0],
            low_prices=[99.0, 0.0, 98.0, 97.0],
            target_quantity=[-1.0, -1.0, 0.0, 0.0],
            signal_values=[-1, -1, 1, 0],
            stop_loss_pct=5.0,
            gap_policy=GapPolicy.EXPIRE,
        )

        self.assertEqual(result.fills, [])
        np.testing.assert_allclose(result.executed_delta, np.array([0.0] * 4))
        self.assertEqual(result.invalid_open_count, 1)
        self.assertEqual(result.expired_delta_count, 1)
        self.assertEqual(result.tail_expired_delta_count, 0)

    def test_costs_use_slippage_adjusted_execution_notional(self) -> None:
        result = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3, 4],
            open_prices=[100.0, 100.0, 100.0, 100.0],
            target_quantity=[0.0, 1.0, 0.0, 0.0],
            gap_policy=GapPolicy.SKIP,
            slippage_bps=10.0,
            commission_bps=20.0,
        )

        self.assertEqual(len(result.fills), 2)
        buy_fill = result.fills[0]
        sell_fill = result.fills[1]

        self.assertEqual(buy_fill.side, OrderSide.BUY)
        self.assertAlmostEqual(buy_fill.price, 100.1)
        self.assertAlmostEqual(buy_fill.fees, 0.2002)
        self.assertEqual(sell_fill.side, OrderSide.SELL)
        self.assertAlmostEqual(sell_fill.price, 99.9)
        self.assertAlmostEqual(sell_fill.fees, 0.1998)
        self.assertAlmostEqual(result.total_slippage_cost, 0.2)

    def test_last_bar_decision_expires_in_tail(self) -> None:
        result = generate_fills_from_targets(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3],
            open_prices=[100.0, 101.0, 102.0],
            target_quantity=[0.0, 0.0, 1.0],
            gap_policy=GapPolicy.SKIP,
        )

        self.assertEqual(len(result.fills), 0)
        self.assertEqual(result.tail_expired_delta_count, 1)

    def test_rejects_non_finite_cost_inputs(self) -> None:
        with self.assertRaises(ValueError):
            generate_fills_from_targets(
                symbol="AAPL",
                timestamp_ms=[1, 2, 3],
                open_prices=[100.0, 101.0, 102.0],
                target_quantity=[0.0, 1.0, 0.0],
                slippage_bps=float("nan"),
            )

        with self.assertRaises(ValueError):
            generate_fills_from_targets(
                symbol="AAPL",
                timestamp_ms=[1, 2, 3],
                open_prices=[100.0, 101.0, 102.0],
                target_quantity=[0.0, 1.0, 0.0],
                commission_bps=float("inf"),
            )

    def test_short_stop_loss_covers_with_planned_short_protective_prices(self) -> None:
        result = generate_fills_from_targets_with_protective_exits(
            symbol="AAPL",
            timestamp_ms=[1, 2, 3],
            open_prices=[99.0, 100.0, 101.0],
            high_prices=[101.0, 106.0, 102.0],
            low_prices=[98.0, 99.0, 100.0],
            target_quantity=[-1.0, -1.0, -1.0],
            signal_values=[-1, 0, 0],
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
            gap_policy=GapPolicy.SKIP,
        )

        self.assertEqual(
            [(fill.timestamp_ms, fill.side, fill.price, fill.exit_reason) for fill in result.fills],
            [
                (2, OrderSide.SELL, 100.0, None),
                (2, OrderSide.BUY, 105.0, ExitReason.STOP_LOSS),
            ],
        )
        self.assertEqual(result.fills[0].stop_loss_price, 105.0)
        self.assertEqual(result.fills[0].take_profit_price, 90.0)
        np.testing.assert_allclose(result.executed_delta, np.array([0.0, 0.0, 0.0]))


if __name__ == "__main__":
    unittest.main()
