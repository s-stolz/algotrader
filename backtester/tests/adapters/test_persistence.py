import unittest
from unittest.mock import patch

from adapters.persistence import (
    BacktestRunLifecyclePersistenceAdapter,
    BacktestRunPersistenceAdapter,
)
from domain.enums import (
    BacktestEngine,
    BacktestRunStatus,
    ExitReason,
    GapPolicy,
    IntrabarExitPolicy,
    OrderSide,
)
from domain.types import (
    BacktestRequest,
    BacktestResult,
    ExecutionConfig,
    Fill,
    PortfolioSnapshot,
    StrategyConfig,
    Trade,
)


class _FakeRunClient:
    def __init__(self) -> None:
        self.saved_runs: list[dict] = []

    def create_backtest_run(self, run: dict) -> dict:
        self.saved_runs.append(dict(run))
        return {key: value for key, value in run.items() if key not in {"fills", "trades"}}


class _FakeLifecycleClient:
    def __init__(self) -> None:
        self.conditional_updates: list[tuple[str, dict]] = []
        self.completions: list[tuple[str, dict]] = []

    def conditional_update_backtest_run(self, run_id: str, update: dict) -> bool:
        self.conditional_updates.append((run_id, update))
        return True

    def complete_backtest_run(self, run_id: str, completion: dict) -> bool:
        self.completions.append((run_id, completion))
        return True


class _FailingRunClient:
    def create_backtest_run(self, run: dict) -> dict:
        raise RuntimeError("database accessor unavailable")


class TestBacktestRunPersistenceAdapter(unittest.TestCase):
    @patch("adapters.persistence._new_run_id", return_value="run-123")
    @patch(
        "adapters.persistence._utc_now_text",
        return_value="2026-06-08T12:30:05.123000+00:00",
    )
    def test_save_run_maps_complete_succeeded_result(
        self,
        _utc_now_text,
        _new_run_id,
    ) -> None:
        client = _FakeRunClient()
        adapter = BacktestRunPersistenceAdapter(client=client)
        result = _build_result()

        saved_result = adapter.save_run(
            result=result,
            execution_duration_ms=275,
        )

        payload = client.saved_runs[0]
        self.assertEqual(payload["run_id"], "run-123")
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["submitted_at"], "2026-06-08T12:30:05.123000+00:00")
        self.assertEqual(payload["started_at"], "2026-06-08T12:30:05.123000+00:00")
        self.assertEqual(payload["completed_at"], "2026-06-08T12:30:05.123000+00:00")
        self.assertIsNone(payload["error_code"])
        self.assertIsNone(payload["error_message"])
        self.assertEqual(payload["request_schema_version"], 1)
        self.assertEqual(payload["request"]["symbols"], ["EURUSD"])
        self.assertEqual(payload["request"]["exchange"], "FX")
        self.assertEqual(payload["request"]["timeframe"], "M15")
        self.assertEqual(payload["request"]["engine"], "event_driven")
        self.assertEqual(
            payload["request"]["strategy"],
            {
                "strategy_id": "sma_crossover",
                "parameters": {
                    "fast_window": 5,
                    "slow_window": 20,
                    "quantity": 1_000.0,
                },
            },
        )
        self.assertEqual(payload["request"]["execution"]["gap_policy"], "error")
        self.assertEqual(
            payload["request"]["execution"]["intrabar_exit_policy"],
            "take_profit_first",
        )
        self.assertEqual(payload["request"]["run_metadata"], {"label": "cli-persist"})
        self.assertEqual(payload["result_schema_version"], 2)
        self.assertEqual(payload["metrics"], result.metrics)
        self.assertEqual(
            payload["diagnostics"],
            {
                "engine": "event_driven",
                "bars": 25,
                "execution_duration_ms": 275,
            },
        )
        self.assertEqual(
            payload["fills"],
            [
                {
                    "fill_sequence": 0,
                    "timestamp_ms": 1_714_522_500_000,
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 1_000.0,
                    "price": 1.0715,
                    "fees": 0.15,
                    "exit_reason": None,
                },
                {
                    "fill_sequence": 1,
                    "timestamp_ms": 1_714_526_100_000,
                    "symbol": "EURUSD",
                    "side": "sell",
                    "quantity": 1_000.0,
                    "price": 1.074,
                    "fees": 0.15,
                    "exit_reason": "signal",
                },
            ],
        )
        self.assertEqual(
            payload["trades"],
            [
                {
                    "trade_sequence": 0,
                    "trade_id": "trade-1",
                    "symbol": "EURUSD",
                    "quantity": 1_000.0,
                    "entry_timestamp_ms": 1_714_522_500_000,
                    "entry_price": 1.0715,
                    "exit_timestamp_ms": 1_714_526_100_000,
                    "exit_price": 1.074,
                    "realized_pnl": 2.5,
                    "fees": 0.3,
                    "exit_reason": "signal",
                    "stop_loss_price": None,
                    "take_profit_price": None,
                }
            ],
        )
        self.assertNotIn("equity_curve", payload)
        self.assertEqual(saved_result.backtest_run_id, "run-123")
        self.assertEqual(saved_result.persisted_at, 1_780_921_805_123)
        self.assertIsNone(result.backtest_run_id)

    @patch("adapters.persistence._new_run_id", return_value="run-empty")
    @patch(
        "adapters.persistence._utc_now_text",
        return_value="2026-06-08T12:30:05.123000+00:00",
    )
    def test_save_run_preserves_empty_artifact_collections(
        self,
        _utc_now_text,
        _new_run_id,
    ) -> None:
        client = _FakeRunClient()
        adapter = BacktestRunPersistenceAdapter(client=client)
        result = _build_result(fills=[], trades=[])

        adapter.save_run(result=result)

        self.assertEqual(client.saved_runs[0]["fills"], [])
        self.assertEqual(client.saved_runs[0]["trades"], [])
        self.assertEqual(
            client.saved_runs[0]["diagnostics"]["execution_duration_ms"],
            0,
        )

    def test_save_run_rejects_open_trade(self) -> None:
        adapter = BacktestRunPersistenceAdapter(client=_FakeRunClient())
        result = _build_result(
            trades=[
                Trade(
                    trade_id="open-1",
                    symbol="EURUSD",
                    quantity=1_000.0,
                    entry_timestamp_ms=1_714_522_500_000,
                    entry_price=1.0715,
                )
            ]
        )

        with self.assertRaisesRegex(ValueError, "exit_timestamp_ms"):
            adapter.save_run(result=result)

    def test_save_run_surfaces_persistence_errors(self) -> None:
        adapter = BacktestRunPersistenceAdapter(client=_FailingRunClient())

        with self.assertRaisesRegex(RuntimeError, "database accessor unavailable"):
            adapter.save_run(result=_build_result())


class TestBacktestRunLifecyclePersistenceAdapter(unittest.TestCase):
    def test_conditional_update_maps_status_enums_and_lifecycle_fields(self) -> None:
        client = _FakeLifecycleClient()
        adapter = BacktestRunLifecyclePersistenceAdapter(client=client)

        updated = adapter.conditional_update(
            run_id="run-123",
            expected_status=BacktestRunStatus.QUEUED,
            new_status=BacktestRunStatus.RUNNING,
            started_at_ms=1_780_921_860_000,
        )

        self.assertTrue(updated)
        self.assertEqual(
            client.conditional_updates,
            [
                (
                    "run-123",
                    {
                        "expected_status": "queued",
                        "new_status": "running",
                        "started_at": "2026-06-08T12:31:00+00:00",
                    },
                )
            ],
        )

    def test_complete_maps_result_without_equity_curve(self) -> None:
        client = _FakeLifecycleClient()
        adapter = BacktestRunLifecyclePersistenceAdapter(client=client)
        result = _build_result()
        result.fills[1] = Fill(
            timestamp_ms=1_714_526_100_000,
            symbol="EURUSD",
            quantity=1_000.0,
            price=1.074,
            side=OrderSide.SELL,
            fees=0.15,
            exit_reason=ExitReason.TAKE_PROFIT,
        )
        result.trades[0] = Trade(
            trade_id="trade-1",
            symbol="EURUSD",
            quantity=1_000.0,
            entry_timestamp_ms=1_714_522_500_000,
            entry_price=1.0715,
            exit_timestamp_ms=1_714_526_100_000,
            exit_price=1.074,
            realized_pnl=2.5,
            fees=0.3,
            exit_reason=ExitReason.TAKE_PROFIT,
            stop_loss_price=1.05,
            take_profit_price=1.08,
        )

        updated = adapter.complete(
            run_id="run-123",
            expected_status=BacktestRunStatus.RUNNING,
            completed_at_ms=1_780_922_100_000,
            result=result,
            execution_duration_ms=275,
        )

        self.assertTrue(updated)
        run_id, payload = client.completions[0]
        self.assertEqual(run_id, "run-123")
        self.assertEqual(payload["expected_status"], "running")
        self.assertEqual(payload["completed_at"], "2026-06-08T12:35:00+00:00")
        self.assertEqual(payload["result_schema_version"], 2)
        self.assertEqual(payload["metrics"], result.metrics)
        self.assertEqual(payload["diagnostics"]["execution_duration_ms"], 275)
        self.assertEqual(payload["fills"][1]["exit_reason"], "take_profit")
        self.assertEqual(payload["trades"][0]["exit_reason"], "take_profit")
        self.assertEqual(payload["trades"][0]["exit_price"], 1.074)
        self.assertEqual(payload["trades"][0]["stop_loss_price"], 1.05)
        self.assertEqual(payload["trades"][0]["take_profit_price"], 1.08)
        self.assertNotIn("equity_curve", payload)

    def test_complete_preserves_empty_artifact_collections(self) -> None:
        client = _FakeLifecycleClient()
        adapter = BacktestRunLifecyclePersistenceAdapter(client=client)

        adapter.complete(
            run_id="run-empty",
            expected_status=BacktestRunStatus.RUNNING,
            completed_at_ms=1_780_922_100_000,
            result=_build_result(fills=[], trades=[]),
        )

        payload = client.completions[0][1]
        self.assertEqual(payload["fills"], [])
        self.assertEqual(payload["trades"], [])


def _build_result(
    *,
    fills: list[Fill] | None = None,
    trades: list[Trade] | None = None,
) -> BacktestResult:
    request = BacktestRequest(
        symbols=["EURUSD"],
        exchange="FX",
        timeframe="M15",
        start_ms=1_714_521_600_000,
        end_ms=1_714_608_000_000,
        strategy=StrategyConfig(
            strategy_id="sma_crossover",
            parameters={
                "fast_window": 5,
                "slow_window": 20,
                "quantity": 1_000.0,
            },
        ),
        execution=ExecutionConfig(
            gap_policy=GapPolicy.ERROR,
            intrabar_exit_policy=IntrabarExitPolicy.TAKE_PROFIT_FIRST,
            commission_bps=1.5,
            slippage_bps=0.75,
        ),
        initial_capital=25_000.0,
        persist_result=True,
        run_metadata={"label": "cli-persist"},
        engine=BacktestEngine.EVENT_DRIVEN,
    )
    default_fills = [
        Fill(
            timestamp_ms=1_714_522_500_000,
            symbol="EURUSD",
            quantity=1_000.0,
            price=1.0715,
            side=OrderSide.BUY,
            fees=0.15,
        ),
        Fill(
            timestamp_ms=1_714_526_100_000,
            symbol="EURUSD",
            quantity=1_000.0,
            price=1.074,
            side=OrderSide.SELL,
            fees=0.15,
            exit_reason=ExitReason.SIGNAL,
        ),
    ]
    default_trades = [
        Trade(
            trade_id="trade-1",
            symbol="EURUSD",
            quantity=1_000.0,
            entry_timestamp_ms=1_714_522_500_000,
            entry_price=1.0715,
            exit_timestamp_ms=1_714_526_100_000,
            exit_price=1.074,
            realized_pnl=2.5,
            fees=0.3,
            exit_reason=ExitReason.SIGNAL,
        )
    ]
    return BacktestResult(
        request=request,
        fills=default_fills if fills is None else fills,
        trades=default_trades if trades is None else trades,
        equity_curve=[
            PortfolioSnapshot(
                timestamp_ms=1_714_608_000_000,
                cash=25_002.5,
                equity=25_002.5,
                positions={},
            )
        ],
        metrics={
            "total_return_pct": 0.01,
            "max_drawdown_pct": -0.005,
            "trade_count": 1.0,
        },
        diagnostics={"engine": "event_driven", "bars": 25},
    )


if __name__ == "__main__":
    unittest.main()
