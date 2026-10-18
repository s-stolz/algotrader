import unittest
from dataclasses import replace

import pandas as pd
from app.backtest_runs import (
    BacktestCandleUnavailableError,
    BacktestRunConflictError,
    BacktestRunNotFoundError,
    BacktestRunService,
)
from app.equity_replay import ReplayUnavailableError, descriptor, replay, sample
from domain.enums import BacktestRunStatus, OrderSide
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestRunRecord,
    ExecutionConfig,
    StrategyConfig,
)


class _Repository:
    def __init__(self, run, fills):
        self.run = run
        self.fills = fills

    def get(self, run_id):
        return self.run if run_id == "run-1" else None

    def rename(self, run_id, name):
        raise NotImplementedError

    def cancel(self, run_id):
        raise NotImplementedError

    def get_fills(self, run_id):
        return self.fills

    def create(self, run):
        self.run = run
        return run

    def list(self, query):
        return [self.run] if self.run is not None else []

    def get_trades(self, run_id):
        return []

    def delete(self, run_id):
        return False


class _Candles:
    def __init__(self, closes):
        self.closes = closes
        self.fails = False

    def fetch_bars(self, **kwargs):
        if self.fails:
            raise OSError("temporary failure")
        return pd.DataFrame(
            {
                "timestamp_ms": [ts for ts, _ in self.closes],
                "close": [close for _, close in self.closes],
            }
        )


def _request():
    return BacktestRequest(
        symbols=["EURUSD"],
        exchange="FX",
        timeframe="M1",
        start_ms=1_700_000_000_000,
        end_ms=1_700_010_000_000,
        strategy=StrategyConfig("sma_crossover", {}),
        execution=ExecutionConfig(),
        initial_capital=100.0,
    )


def _fill(sequence, timestamp, side, quantity, price, fees=0.0):
    return BacktestFillRecord("run-1", sequence, timestamp, "EURUSD", side, quantity, price, fees)


class EquityReplayTests(unittest.TestCase):
    def setUp(self):
        self.request = _request()
        self.start = self.request.start_ms
        self.closes = [(self.start + i * 60_000, float(10 + i)) for i in range(4)]

    def test_fingerprint_normalizes_negative_zero_and_identifies_market(self):
        zero = [(self.start, -0.0)]
        self.assertEqual(
            descriptor(self.request, zero), descriptor(self.request, [(self.start, 0.0)])
        )
        other_market = replace(self.request, exchange="OTHER")
        self.assertNotEqual(
            descriptor(self.request, zero)["fingerprint_digest"],
            descriptor(other_market, zero)["fingerprint_digest"],
        )

    def test_replays_long_short_flip_and_fees_after_candle_executions(self):
        fills = [
            _fill(0, self.closes[0][0], OrderSide.BUY, 1, 10, 1),
            _fill(1, self.closes[1][0], OrderSide.SELL, 2, 11, 2),
            _fill(2, self.closes[3][0], OrderSide.BUY, 1, 13, 1),
        ]
        points = replay(self.request, descriptor(self.request, self.closes), self.closes, fills)
        self.assertEqual([point["equity"] for point in points], [99, 98, 97, 95])
        self.assertEqual(points[0]["drawdown_pct"], 0)
        self.assertLess(points[-1]["drawdown_pct"], 0)
        self.assertEqual(
            [point["timestamp_ms"] for point in points], [timestamp for timestamp, _ in self.closes]
        )

    def test_fails_closed_for_mismatch_and_bad_fill_order(self):
        saved = descriptor(self.request, self.closes)
        with self.assertRaisesRegex(ReplayUnavailableError, "fingerprint_mismatch"):
            replay(self.request, saved, [(ts, close + 1) for ts, close in self.closes], [])
        fills = [
            _fill(0, self.closes[2][0], OrderSide.BUY, 1, 12),
            _fill(1, self.closes[1][0], OrderSide.SELL, 1, 11),
        ]
        with self.assertRaisesRegex(ReplayUnavailableError, "unsupported_replay_shape"):
            replay(self.request, saved, self.closes, fills)
        with self.assertRaisesRegex(ReplayUnavailableError, "unsupported_replay_shape"):
            replay(
                self.request,
                saved,
                self.closes,
                [_fill(0, self.closes[0][0], OrderSide.BUY, float("nan"), 10)],
            )

    def test_sampling_keeps_endpoints_and_peak_trough_within_bound(self):
        points = [
            {
                "timestamp_ms": index,
                "equity": float(100 + index % 11),
                "drawdown_pct": -float(index % 11),
            }
            for index in range(250)
        ]
        points[120] = {"timestamp_ms": 120, "equity": 200.0, "drawdown_pct": 0.0}
        points[121] = {"timestamp_ms": 121, "equity": 1.0, "drawdown_pct": -99.5}
        sampled = sample(points, 100)
        self.assertLessEqual(len(sampled), 100)
        self.assertEqual(sampled[0], points[0])
        self.assertEqual(sampled[-1], points[-1])
        self.assertIn(points[120], sampled)
        self.assertIn(points[121], sampled)
        self.assertEqual(sample(points, 100), sampled)

    def test_sampling_uses_earliest_timestamp_for_equal_bucket_extrema(self):
        points = [
            {"timestamp_ms": index, "equity": 100.0, "drawdown_pct": 0.0} for index in range(201)
        ]
        sampled = sample(points, 100)
        self.assertEqual(sampled[0]["timestamp_ms"], 0)
        self.assertEqual(sampled[1]["timestamp_ms"], 1)
        self.assertEqual(sampled[-1]["timestamp_ms"], 200)
        self.assertLessEqual(len(sampled), 100)

    def test_sampling_odd_budget_retains_last_bucket_maximum(self):
        points = [
            {"timestamp_ms": index, "equity": float(index), "drawdown_pct": 0.0}
            for index in range(301)
        ]

        sampled = sample(points, 101)
        timestamps = [point["timestamp_ms"] for point in sampled]

        self.assertLessEqual(len(sampled), 101)
        self.assertEqual(timestamps[0], 0)
        self.assertEqual(timestamps[-1], 300)
        self.assertIn(299, timestamps)

    def test_application_reports_exact_legacy_and_candle_failure(self):
        run = BacktestRunRecord(
            run_id="run-1",
            status=BacktestRunStatus.SUCCEEDED,
            submitted_at_ms=self.start,
            request_snapshot=BacktestRequestSnapshot.from_request(self.request),
            replay_descriptor=descriptor(self.request, self.closes),
        )
        repository = _Repository(run, [])
        candles = _Candles(self.closes)
        service = BacktestRunService(repository=repository, data_adapter=candles)
        exact = service.get_equity_curve("run-1", 100)
        self.assertEqual(exact["availability"], "exact")
        self.assertEqual(exact["source_point_count"], 4)
        self.assertFalse(exact["sampled"])
        repository.run = replace(run, replay_descriptor=None)
        self.assertEqual(service.get_equity_curve("run-1")["reason"], "replay_metadata_missing")
        repository.run = run
        candles.closes = [(ts, close + 1) for ts, close in self.closes]
        self.assertEqual(service.get_equity_curve("run-1")["reason"], "fingerprint_mismatch")
        candles.fails = True
        with self.assertRaises(BacktestCandleUnavailableError):
            service.get_equity_curve("run-1")
        with self.assertRaises(BacktestRunNotFoundError):
            service.get_equity_curve("missing")
        repository.run = replace(run, status=BacktestRunStatus.FAILED)
        with self.assertRaises(BacktestRunConflictError):
            service.get_equity_curve("run-1")
