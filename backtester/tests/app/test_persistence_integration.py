import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pandas as pd
from adapters.persistence import (
    BacktestRunPersistenceAdapter,
    DatabaseAccessorBacktestRunRepository,
)
from app.backtest_runner import run_backtest, run_backtest_with_market_data, save_backtest_result
from domain.enums import OrderSide, TradeDirection
from domain.types import BacktestRequest, BacktestResult, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class _RecordingPersistenceAdapter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def save_run(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        self.calls.append(
            {
                "result": result,
                "execution_duration_ms": execution_duration_ms,
            }
        )
        return replace(
            result,
            backtest_run_id="run-auto-1",
            persisted_at=1_778_848_205_123,
        )


class _ExplodingPersistenceAdapter:
    def save_run(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        _ = (result, execution_duration_ms)
        raise AssertionError("persistence adapter should not be called")


class _FailingPersistenceAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def save_run(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        _ = (result, execution_duration_ms)
        self.calls += 1
        raise RuntimeError("database accessor unavailable")


class _TimingAwareHistoricalAdapter:
    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars

    def fetch_bars(self, **kwargs) -> pd.DataFrame:
        _ = kwargs
        from app import backtest_runner

        backtest_runner.perf_counter()
        return self._bars.copy()


class _FakeDatabaseAccessorClient:
    instances: list["_FakeDatabaseAccessorClient"] = []

    def __init__(self) -> None:
        self.saved_runs: list[dict] = []
        self.closed = False
        self.__class__.instances.append(self)

    def __enter__(self) -> "_FakeDatabaseAccessorClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)
        self.closed = True

    def create_backtest_run(self, run: dict) -> dict:
        self.saved_runs.append(dict(run))
        return {key: value for key, value in run.items() if key not in {"fills", "trades"}}


class _InMemoryBacktestRunClient:
    def __init__(self) -> None:
        self.saved_runs: list[dict] = []
        self._runs: dict[str, dict] = {}
        self._fills: dict[str, list[dict]] = {}
        self._trades: dict[str, list[dict]] = {}

    def create_backtest_run(self, run: dict) -> dict:
        saved = deepcopy(run)
        run_id = str(saved["run_id"])
        self.saved_runs.append(saved)
        self._runs[run_id] = {
            key: value for key, value in deepcopy(saved).items() if key not in {"fills", "trades"}
        }
        self._fills[run_id] = [{"run_id": run_id, **fill} for fill in deepcopy(saved["fills"])]
        self._trades[run_id] = [{"run_id": run_id, **trade} for trade in deepcopy(saved["trades"])]
        return deepcopy(self._runs[run_id])

    def get_backtest_run(self, run_id: str) -> dict:
        return deepcopy(self._runs[run_id])

    def list_backtest_runs(self, **query) -> list[dict]:
        _ = query
        return [deepcopy(run) for run in self._runs.values()]

    def get_backtest_fills(self, run_id: str) -> list[dict]:
        return deepcopy(self._fills[run_id])

    def get_backtest_trades(self, run_id: str) -> list[dict]:
        return deepcopy(self._trades[run_id])

    def delete_backtest_run(self, run_id: str) -> None:
        del self._runs[run_id]
        del self._fills[run_id]
        del self._trades[run_id]


class TestBacktestPersistenceIntegration(unittest.TestCase):
    def test_default_long_and_short_run_persists_short_acceptance_artifacts(self) -> None:
        client = _InMemoryBacktestRunClient()
        request = _build_short_acceptance_request()
        strategy = build_sma_crossover_strategy(
            fast_window=2,
            slow_window=3,
            quantity=1.0,
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
        )

        with patch("adapters.persistence._new_run_id", return_value="run-short-acceptance"):
            result = run_backtest(
                request=request,
                bars=_build_short_acceptance_bars(),
                strategy=strategy,
                persistence_adapter=BacktestRunPersistenceAdapter(client=client),
            )

        saved_run = client.saved_runs[0]
        self.assertEqual(result.backtest_run_id, "run-short-acceptance")
        self.assertEqual(saved_run["request_schema_version"], 2)
        self.assertEqual(
            saved_run["request"]["execution"]["allowed_directions"],
            "long_and_short",
        )
        self.assertNotIn("allow_short", saved_run["request"]["execution"])
        self.assertEqual(saved_run["result_schema_version"], 3)

        self.assertEqual(
            [(fill["side"], fill["exit_reason"]) for fill in saved_run["fills"]],
            [("sell", None), ("buy", "stop_loss")],
        )
        self.assertTrue(all("trade_direction" not in fill for fill in saved_run["fills"]))
        self.assertGreater(saved_run["fills"][0]["fees"], 0.0)
        self.assertGreater(saved_run["fills"][1]["fees"], 0.0)

        self.assertEqual(len(saved_run["trades"]), 1)
        closed_short = saved_run["trades"][0]
        self.assertEqual(closed_short["trade_direction"], "short")
        self.assertEqual(closed_short["quantity"], 1.0)
        self.assertEqual(closed_short["exit_reason"], "stop_loss")
        self.assertAlmostEqual(closed_short["fees"], 0.01845)
        self.assertAlmostEqual(closed_short["realized_pnl"], -0.46845)
        self.assertAlmostEqual(closed_short["stop_loss_price"], 9.45)
        self.assertAlmostEqual(closed_short["take_profit_price"], 8.1)

        self.assertEqual(saved_run["metrics"]["trade_count"], 1.0)
        self.assertEqual(saved_run["metrics"]["long_trade_count"], 0.0)
        self.assertEqual(saved_run["metrics"]["short_trade_count"], 1.0)
        self.assertEqual(saved_run["metrics"]["long_win_rate_pct"], 0.0)
        self.assertEqual(saved_run["metrics"]["short_win_rate_pct"], 0.0)
        self.assertEqual(saved_run["metrics"]["long_realized_pnl"], 0.0)
        self.assertAlmostEqual(
            saved_run["metrics"]["short_realized_pnl"],
            closed_short["realized_pnl"],
        )

        repository = DatabaseAccessorBacktestRunRepository(client=client)
        run_record = repository.get("run-short-acceptance")
        fetched_fills = repository.get_fills("run-short-acceptance")
        fetched_trades = repository.get_trades("run-short-acceptance")

        self.assertIsNotNone(run_record)
        assert run_record is not None
        self.assertEqual(run_record.request_snapshot.schema_version, 2)
        self.assertEqual(
            run_record.request_snapshot.payload["execution"]["allowed_directions"],
            "long_and_short",
        )
        self.assertEqual(run_record.result_schema_version, 3)
        self.assertEqual(run_record.metrics, saved_run["metrics"])
        self.assertEqual(
            [(fill.side, fill.exit_reason) for fill in fetched_fills],
            [(OrderSide.SELL, None), (OrderSide.BUY, result.fills[1].exit_reason)],
        )
        self.assertEqual(fetched_trades[0].trade_direction, TradeDirection.SHORT)
        self.assertAlmostEqual(
            fetched_trades[0].realized_pnl,
            closed_short["realized_pnl"],
        )
        self.assertIsNotNone(fetched_trades[0].stop_loss_price)
        self.assertIsNotNone(fetched_trades[0].take_profit_price)
        assert fetched_trades[0].stop_loss_price is not None
        assert fetched_trades[0].take_profit_price is not None
        self.assertAlmostEqual(fetched_trades[0].stop_loss_price, 9.45)
        self.assertAlmostEqual(fetched_trades[0].take_profit_price, 8.1)

    def test_opt_in_request_persists_successful_run_and_attaches_metadata(self) -> None:
        adapter = _RecordingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
            persistence_adapter=adapter,
        )

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0]["result"].request, request)
        self.assertIsInstance(adapter.calls[0]["execution_duration_ms"], int)
        self.assertGreaterEqual(adapter.calls[0]["execution_duration_ms"], 0)
        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(result.persisted_at, 1_778_848_205_123)

    def test_default_request_does_not_call_persistence(self) -> None:
        request = _build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
            persistence_adapter=_ExplodingPersistenceAdapter(),
        )

        self.assertIsNone(result.backtest_run_id)
        self.assertIsNone(result.persisted_at)
        self.assertEqual(result.diagnostics["engine"], "vectorized")
        self.assertEqual(len(result.fills), 2)

    def test_failed_backtest_does_not_call_persistence(self) -> None:
        request = BacktestRequest(
            symbols=["MSFT"],
            timeframe="1m",
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_540_000,
            strategy=StrategyConfig(strategy_id="sma_crossover"),
            execution=ExecutionConfig(),
            initial_capital=10_000.0,
            persist_result=True,
        )
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaisesRegex(ValueError, "No bars found"):
            run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=_ExplodingPersistenceAdapter(),
            )

    def test_execution_duration_excludes_persistence_call_time(self) -> None:
        adapter = _RecordingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch("app.backtest_runner.perf_counter", side_effect=[10.0, 10.5]):
            result = run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=adapter,
            )

        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(adapter.calls[0]["execution_duration_ms"], 500)

    def test_market_data_loading_time_is_excluded_from_persisted_duration(self) -> None:
        persistence_adapter = _RecordingPersistenceAdapter()
        data_adapter = _TimingAwareHistoricalAdapter(_build_raw_bars_with_warmup())
        request = replace(_build_request(persist_result=True), timeframe="M1")
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with patch("app.backtest_runner.perf_counter", side_effect=[10.0, 100.0, 100.5]):
            result = run_backtest_with_market_data(
                request=request,
                strategy=strategy,
                data_adapter=data_adapter,
                persistence_adapter=persistence_adapter,
            )

        self.assertEqual(result.backtest_run_id, "run-auto-1")
        self.assertEqual(persistence_adapter.calls[0]["execution_duration_ms"], 500)

    def test_persistence_error_surfaces_for_opt_in_request(self) -> None:
        adapter = _FailingPersistenceAdapter()
        request = _build_request(persist_result=True)
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)

        with self.assertRaisesRegex(RuntimeError, "database accessor unavailable"):
            run_backtest(
                request=request,
                bars=_build_bars(),
                strategy=strategy,
                persistence_adapter=adapter,
            )

        self.assertEqual(adapter.calls, 1)

    def test_manual_save_uses_default_database_accessor_client_surface(self) -> None:
        _FakeDatabaseAccessorClient.instances.clear()
        request = _build_request()
        strategy = build_sma_crossover_strategy(fast_window=2, slow_window=3, quantity=1.0)
        completed_result = run_backtest(
            request=request,
            bars=_build_bars(),
            strategy=strategy,
        )

        with patch(
            "adapters.persistence._import_database_accessor_client",
            return_value=_FakeDatabaseAccessorClient,
            create=True,
        ):
            saved_result = save_backtest_result(
                result=completed_result,
                execution_duration_ms=321,
            )

        self.assertEqual(len(_FakeDatabaseAccessorClient.instances), 1)
        client = _FakeDatabaseAccessorClient.instances[0]
        self.assertTrue(client.closed)
        self.assertEqual(
            client.saved_runs[0]["diagnostics"]["execution_duration_ms"],
            321,
        )
        self.assertEqual(client.saved_runs[0]["request"]["symbols"], ["AAPL"])
        self.assertEqual(client.saved_runs[0]["metrics"]["trade_count"], 1.0)
        self.assertEqual(saved_result.backtest_run_id, client.saved_runs[0]["run_id"])
        self.assertIsInstance(saved_result.persisted_at, int)
        self.assertIsNone(completed_result.backtest_run_id)


def _build_request(*, persist_result: bool = False) -> BacktestRequest:
    return BacktestRequest(
        symbols=["AAPL"],
        timeframe="1m",
        start_ms=1_700_000_000_000,
        end_ms=1_700_000_540_000,
        strategy=StrategyConfig(strategy_id="sma_crossover"),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
        persist_result=persist_result,
    )


def _build_short_acceptance_request() -> BacktestRequest:
    start_ms = 1_700_000_000_000
    minute = 60_000
    return BacktestRequest(
        symbols=["AAPL"],
        timeframe="1m",
        start_ms=start_ms,
        end_ms=start_ms + (7 * minute),
        strategy=StrategyConfig(
            strategy_id="sma_crossover",
            parameters={
                "fast_window": 2,
                "slow_window": 3,
                "quantity": 1.0,
                "stop_loss_pct": 5.0,
                "take_profit_pct": 10.0,
            },
        ),
        execution=ExecutionConfig(commission_bps=10.0),
        initial_capital=10_000.0,
        persist_result=True,
    )


def _build_short_acceptance_bars() -> pd.DataFrame:
    start_ms = 1_700_000_000_000
    minute = 60_000
    closes = [10.0, 12.0, 14.0, 13.0, 11.0, 9.0, 8.0]

    return pd.DataFrame(
        {
            "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
            "symbol": ["AAPL"] * len(closes),
            "open": closes,
            "high": [price + 0.5 for price in closes],
            "low": [price - 0.5 for price in closes],
            "close": closes,
            "volume": [1_000.0] * len(closes),
        }
    )


def _build_bars() -> pd.DataFrame:
    start_ms = 1_700_000_000_000
    minute = 60_000
    closes = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]
    opens = [10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0]

    return pd.DataFrame(
        {
            "timestamp_ms": [start_ms + minute * i for i in range(len(closes))],
            "symbol": ["AAPL"] * len(closes),
            "open": opens,
            "high": [price + 0.5 for price in opens],
            "low": [price - 0.5 for price in opens],
            "close": closes,
            "volume": [1_000.0] * len(closes),
        }
    )


def _build_raw_bars_with_warmup() -> pd.DataFrame:
    start_ms = 1_700_000_000_000
    minute = 60_000
    timestamps = [start_ms - (2 * minute) + (minute * i) for i in range(11)]
    opens = [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0]
    closes = [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0]

    return pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "symbol": ["AAPL"] * len(timestamps),
            "open": opens,
            "high": [price + 0.5 for price in opens],
            "low": [price - 0.5 for price in opens],
            "close": closes,
            "volume": [1_000.0] * len(timestamps),
        }
    )


if __name__ == "__main__":
    unittest.main()
