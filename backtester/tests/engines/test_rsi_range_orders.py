"""Independent runtimes honor flat-only entry and fill-relative exits."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from data.order_bars import resolve_order_expiry
from domain.enums import BacktestEngine, OrderSide
from domain.orders import LimitOrder, OrderAction, OrderCommand, OrderProtection
from domain.progress import observe_progress
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from engines.order_event_driven import run_order_event_driven
from engines.order_events import EventOrderConfig, EventOrderState, execute_order_event
from engines.order_vectorized import run_order_vectorized
from execution.orders import OrderExecutionConfig, OrderExecutionState, execute_minute
from strategies.examples.rsi_range_limit import build_rsi_range_limit


class RsiRangeOrderTests(unittest.TestCase):
    def test_order_events_snapshot_prices_on_submit_and_update(self):
        for state_type in (OrderExecutionState, EventOrderState):
            with self.subTest(state=state_type.__name__):
                state = state_type()
                for timestamp, action, price in (
                    (60000, OrderAction.SUBMIT, 110.0),
                    (120000, OrderAction.UPDATE, 111.0),
                ):
                    order = LimitOrder("pending", OrderSide.SELL, price, 1.0)
                    state.command(OrderCommand(timestamp, action, "pending", order))
                state.command(OrderCommand(180000, OrderAction.CANCEL, "pending"))
                self.assertEqual(
                    [event.get("limit_price") for event in state.events], [110.0, 111.0, None]
                )
                self.assertEqual(
                    [event["outcome"] for event in state.events], ["submit", "update", "cancel"]
                )
                self.assertEqual(state.events[0]["side"], "sell")

    def test_delayed_fill_ignored_crossing_and_actual_fill_exits(self):
        strategy = build_rsi_range_limit()
        bars = pd.DataFrame(
            {
                "timestamp_ms": [0, 600000, 1200000, 1800000],
                "symbol": "TEST",
                "rsi": [50, 20, 80, 50],
                "lowest_low": 95.0,
                "highest_high": 110.0,
            }
        )
        minutes = pd.DataFrame(
            {
                "timestamp_ms": list(range(0, 2400000, 60000)),
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
            }
        )
        # Entry is eligible at minute 20, but waits until minute 22. The opening
        # gap improves its fill from 95 to 94; protection must be 93/96.
        minutes.loc[22:31, ["open", "high", "low", "close"]] = [94.0, 94.5, 93.5, 94.0]
        minutes.loc[32:, ["open", "high", "low", "close"]] = [94.0, 96.0, 93.5, 95.0]
        request = BacktestRequest(
            symbols=["TEST"],
            timeframe="M10",
            start_ms=0,
            end_ms=2400000,
            initial_capital=10000,
            market_min_move=0.01,
            strategy=StrategyConfig("rsi_range_limit", strategy_version=3),
            execution=ExecutionConfig(execution_mode="orders", candle_quote="bid"),
        )
        vector = run_order_vectorized(
            request=request, strategy_bars=bars, execution_bars=minutes, strategy=strategy
        )
        counts = []
        with observe_progress(lambda stage: None, lambda done, total: counts.append((done, total))):
            event = run_order_event_driven(
                request=replace(request, engine=BacktestEngine.EVENT_DRIVEN),
                strategy_bars=bars,
                execution_bars=minutes,
                strategy=strategy,
            )
        self.assertEqual(counts, [(0, len(minutes)), (len(minutes), len(minutes))])
        self.assertEqual(vector.fills, event.fills)
        self.assertEqual(vector.trades, event.trades)
        self.assertEqual(vector.equity_curve, event.equity_curve)
        self.assertEqual(vector.diagnostics["order_events"], event.diagnostics["order_events"])
        submitted = vector.diagnostics["order_events"][0]
        self.assertEqual(submitted["outcome"], "submit")
        self.assertEqual(submitted["limit_price"], 95.0)
        self.assertEqual(submitted["side"], "buy")
        self.assertEqual(len(vector.fills), 2)
        self.assertEqual(vector.fills[0].timestamp_ms, 22 * 60000)
        self.assertEqual(
            (
                vector.fills[0].price,
                vector.fills[0].stop_loss_price,
                vector.fills[0].take_profit_price,
            ),
            (94, 93, 96),
        )
        self.assertEqual(vector.fills[1].price, 96)
        self.assertIn(
            "position_open_ignored", [e["outcome"] for e in vector.diagnostics["order_events"]]
        )

        for runtime in (run_order_vectorized, run_order_event_driven):
            result = runtime(
                request=replace(request, market_min_move=0.02),
                strategy_bars=bars,
                execution_bars=minutes,
                strategy=strategy,
            )
            self.assertEqual(result.fills[0].stop_loss_price, 92)
            self.assertEqual(result.fills[0].take_profit_price, 98)

    def test_replacement_expiry_and_short_fill_protection_in_both_matchers(self):
        runtimes: list[tuple[Any, Any, Any]] = [
            (OrderExecutionState, OrderExecutionConfig, execute_minute),
            (EventOrderState, EventOrderConfig, execute_order_event),
        ]
        for state_type, config_type, execute in runtimes:
            with self.subTest(runtime=state_type.__name__):
                state = state_type()
                for i, side, price in ((1, OrderSide.BUY, 90), (2, OrderSide.SELL, 110)):
                    order = LimitOrder(
                        str(i),
                        side,
                        price,
                        1,
                        only_when_flat=True,
                        replace_group="entry",
                        lifetime_bars=2,
                        protection=OrderProtection(stop_loss_distance=2, take_profit_distance=4),
                    )
                    state.command(
                        resolve_order_expiry(
                            OrderCommand(i * 600000, OrderAction.SUBMIT, str(i), order), "M10"
                        )
                    )
                self.assertEqual(list(state.active), ["2"])
                missed = execute(
                    state,
                    symbol="TEST",
                    timestamp_ms=1200000,
                    prices=(100, 109, 99, 100),
                    config=config_type(),
                )
                self.assertFalse(missed.fills)
                expired = execute(
                    missed,
                    symbol="TEST",
                    timestamp_ms=2400000,
                    prices=(112, 113, 111, 112),
                    config=config_type(),
                )
                self.assertFalse(expired.fills)
                filled = execute(
                    missed,
                    symbol="TEST",
                    timestamp_ms=1260000,
                    prices=(112, 113, 111, 112),
                    config=config_type(),
                )
                self.assertEqual(filled.position, -1)
                self.assertEqual((filled.stop_price, filled.targets), (114, [(108, 1)]))
                exited = execute(
                    filled,
                    symbol="TEST",
                    timestamp_ms=1320000,
                    prices=(112, 114, 111, 112),
                    config=config_type(),
                )
                self.assertEqual(exited.position, 0)
                self.assertEqual(exited.fills[-1].price, 114)

    def test_offset_limits_wait_for_later_touch_in_both_directions_and_engines(self):
        for side, rsi in ((OrderSide.BUY, 20), (OrderSide.SELL, 80)):
            bars = pd.DataFrame(
                {
                    "timestamp_ms": [i * 60000 for i in range(7)],
                    "symbol": "TEST",
                    "rsi": [50, rsi, rsi, rsi, rsi, rsi, rsi],
                    "lowest_low": 100.0,
                    "highest_high": 100.0,
                }
            )
            minutes = pd.DataFrame(
                {
                    "timestamp_ms": [i * 60000 for i in range(7)],
                    "open": 100.0,
                    "high": 100.5,
                    "low": 99.5,
                    "close": 100.0,
                }
            )
            minutes.loc[5, "low" if side == OrderSide.BUY else "high"] = (
                99 if side == OrderSide.BUY else 101
            )
            request = BacktestRequest(
                symbols=["TEST"],
                timeframe="M1",
                start_ms=0,
                end_ms=420000,
                initial_capital=10000,
                market_min_move=0.01,
                strategy=StrategyConfig("rsi_range_limit", strategy_version=3),
                execution=ExecutionConfig(execution_mode="orders", candle_quote="bid"),
            )
            results = []
            for runtime in (run_order_vectorized, run_order_event_driven):
                with self.subTest(side=side, runtime=runtime.__name__):
                    baseline = runtime(
                        request=request,
                        strategy_bars=bars,
                        execution_bars=minutes,
                        strategy=build_rsi_range_limit(),
                    )
                    self.assertEqual(baseline.fills[0].timestamp_ms, 120000)
                    shifted = runtime(
                        request=request,
                        strategy_bars=bars,
                        execution_bars=minutes,
                        strategy=build_rsi_range_limit(limit_offset_ticks=100),
                    )
                    self.assertEqual(shifted.fills[0].timestamp_ms, 300000)
                    self.assertEqual(shifted.fills[0].price, 99 if side == OrderSide.BUY else 101)
                    self.assertEqual(shifted.fills[0].side, side)
                    results.append(shifted)
                    expired = runtime(
                        request=request,
                        strategy_bars=bars,
                        execution_bars=minutes,
                        strategy=build_rsi_range_limit(limit_offset_ticks=100, lifetime_bars=2),
                    )
                    self.assertFalse(expired.fills)
                    self.assertIn(
                        "expired",
                        [event["outcome"] for event in expired.diagnostics["order_events"]],
                    )
            self.assertEqual(results[0].fills, results[1].fills)
            self.assertEqual(
                results[0].diagnostics["order_events"], results[1].diagnostics["order_events"]
            )

    def test_expiry_uses_timeframe_and_calendar_months(self):
        boundary = int(datetime(2024, 2, 1, tzinfo=timezone.utc).timestamp() * 1000)
        order = LimitOrder("entry", OrderSide.BUY, 100, 1, lifetime_bars=1)
        command = resolve_order_expiry(
            OrderCommand(boundary, OrderAction.SUBMIT, "entry", order), "MN1"
        )
        assert command.order is not None
        self.assertEqual(
            command.order.expires_at_ms,
            int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp() * 1000),
        )
