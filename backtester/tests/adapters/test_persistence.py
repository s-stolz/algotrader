import json
import pickle
import unittest
from dataclasses import replace

from adapters.persistence import (
    BacktestRunLifecyclePersistenceAdapter,
    build_successful_completion_payload,
)
from app.backtest_child import CompactBacktestResult
from domain.enums import (
    BacktestEngine,
    ExitReason,
    GapPolicy,
    IntrabarExitPolicy,
    OrderSide,
    TradeDirection,
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
        self.execution_requests: list[tuple[str, dict | None]] = []

    def get_backtest_execution_slot(self) -> dict:
        self.execution_requests.append(("slot", None))
        return {"owner_token": None, "run_id": None, "fault_code": None, "fault_message": None}

    def claim_backtest_execution(self, claim: dict) -> bool:
        self.execution_requests.append(("claim", claim))
        return True

    def settle_backtest_execution(self, settlement: dict) -> bool:
        self.execution_requests.append(("settle", settlement))
        return True

    def reconcile_backtest_execution(self, reconciliation: dict) -> int:
        self.execution_requests.append(("reconcile", reconciliation))
        return 1

    def record_backtest_execution_fault(self, fault: dict) -> bool:
        self.execution_requests.append(("fault", fault))
        return True


class _FailingRunClient:
    def create_backtest_run(self, run: dict) -> dict:
        raise RuntimeError("database accessor unavailable")


class TestBacktestRunLifecyclePersistenceAdapter(unittest.TestCase):
    def test_profit_factor_survives_child_handoff_and_strict_json_payload(self):
        for value in (2.5, 0.0, "infinity", None):
            with self.subTest(value=value):
                result = _build_result()
                result = replace(result, metrics={**result.metrics, "profit_factor": value})
                compact = CompactBacktestResult.from_result(result, execution_duration_ms=5)
                restored = pickle.loads(pickle.dumps(compact)).to_result()
                payload = build_successful_completion_payload(
                    completed_at_ms=1714525500000, result=restored, execution_duration_ms=5
                )
                self.assertEqual(
                    json.loads(json.dumps(payload, allow_nan=False))["metrics"]["profit_factor"],
                    value,
                )

    def test_execution_operations_carry_owner_token_and_reconciliation_reason(self) -> None:
        client = _FakeLifecycleClient()
        adapter = BacktestRunLifecyclePersistenceAdapter(client=client)

        self.assertIsNone(adapter.execution_slot()["owner_token"])
        self.assertTrue(
            adapter.claim_execution(
                run_id="run-123",
                owner_token="owner-123",
                started_at_ms=1_780_921_860_000,
                worker_id="worker-123",
            )
        )
        self.assertTrue(
            adapter.settle_failure(
                run_id="run-123",
                owner_token="owner-123",
                completed_at_ms=1_780_922_100_000,
                error_code="backtest_failed",
                error_message="Backtest execution failed",
            )
        )
        self.assertEqual(adapter.reconcile_execution(completed_at_ms=1_780_922_100_000), 1)
        self.assertTrue(
            adapter.record_execution_fault(
                run_id="run-123",
                owner_token="owner-123",
                code="lost_ownership",
                message="Storage rejected settlement",
            )
        )

        names = [name for name, _ in client.execution_requests]
        self.assertEqual(names, ["slot", "claim", "settle", "reconcile", "fault"])
        claim_request = client.execution_requests[1][1]
        settle_request = client.execution_requests[2][1]
        reconcile_request = client.execution_requests[3][1]
        assert claim_request is not None
        assert settle_request is not None
        assert reconcile_request is not None
        self.assertEqual(claim_request["owner_token"], "owner-123")
        self.assertEqual(claim_request["worker_id"], "worker-123")
        self.assertEqual(settle_request["status"], "failed")
        self.assertEqual(reconcile_request["error_code"], "worker_interrupted")

    def test_settle_success_maps_result_without_equity_curve(self) -> None:
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
            trade_direction=TradeDirection.LONG,
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

        updated = adapter.settle_success(
            run_id="run-123",
            owner_token="owner-123",
            completed_at_ms=1_780_922_100_000,
            result=result,
            execution_duration_ms=275,
        )

        self.assertTrue(updated)
        _, payload = client.execution_requests[0]
        assert payload is not None
        run_id = payload["run_id"]
        self.assertEqual(run_id, "run-123")
        self.assertEqual(payload["owner_token"], "owner-123")
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["completed_at"], "2026-06-08T12:35:00+00:00")
        self.assertEqual(payload["result_schema_version"], 3)
        self.assertEqual(payload["metrics"], result.metrics)
        self.assertEqual(payload["metrics"]["ending_equity"], 25_002.5)
        self.assertEqual(payload["diagnostics"]["execution_duration_ms"], 275)
        self.assertEqual(payload["fills"][1]["exit_reason"], "take_profit")
        self.assertEqual(payload["trades"][0]["exit_reason"], "take_profit")
        self.assertEqual(payload["trades"][0]["trade_direction"], "long")
        self.assertEqual(payload["trades"][0]["exit_price"], 1.074)
        self.assertEqual(payload["trades"][0]["stop_loss_price"], 1.05)
        self.assertEqual(payload["trades"][0]["take_profit_price"], 1.08)
        self.assertNotIn("equity_curve", payload)

    def test_settle_success_preserves_empty_artifact_collections(self) -> None:
        client = _FakeLifecycleClient()
        adapter = BacktestRunLifecyclePersistenceAdapter(client=client)

        adapter.settle_success(
            run_id="run-empty",
            owner_token="owner-123",
            completed_at_ms=1_780_922_100_000,
            result=_build_result(fills=[], trades=[]),
            execution_duration_ms=0,
        )

        payload = client.execution_requests[0][1]
        assert payload is not None
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
        run_metadata={"label": "persistence-test"},
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
            trade_direction=TradeDirection.LONG,
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
            "profit_factor": None,
            "ending_equity": 25_002.5,
            "total_return_pct": 0.01,
            "max_drawdown_pct": -0.005,
            "trade_count": 1.0,
        },
        diagnostics={"engine": "event_driven", "bars": 25},
        replay_descriptor={
            "schema_version": 1,
            "fingerprint_algorithm": "sha256-ts-close-v1",
            "fingerprint_digest": "0" * 64,
            "source_point_count": 1,
            "first_timestamp_ms": 1_714_608_000_000,
            "last_timestamp_ms": 1_714_608_000_000,
        },
    )


if __name__ == "__main__":
    unittest.main()
