import unittest

from adapters.persistence import DatabaseAccessorBacktestRunRepository
from db_accessor_client import DatabaseAccessorClientError
from domain.enums import (
    BacktestEngine,
    BacktestRunStatus,
    ExitReason,
    OrderSide,
)
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
    ExecutionConfig,
    StrategyConfig,
)


class _FakeRunClient:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []
        self.runs_by_id: dict[str, dict] = {}
        self.listed_payloads: list[dict] = []
        self.list_queries: list[dict] = []
        self.fills_by_run_id: dict[str, list[dict]] = {}
        self.trades_by_run_id: dict[str, list[dict]] = {}
        self.deleted_run_ids: list[str] = []

    def create_backtest_run(self, run: dict) -> dict:
        self.created_payloads.append(run)
        self.runs_by_id[run["run_id"]] = dict(run)
        return dict(run)

    def get_backtest_run(self, run_id: str) -> dict:
        return dict(self.runs_by_id[run_id])

    def list_backtest_runs(self, **query) -> list[dict]:
        self.list_queries.append(query)
        return [dict(run) for run in self.listed_payloads]

    def get_backtest_fills(self, run_id: str) -> list[dict]:
        return [dict(fill) for fill in self.fills_by_run_id.get(run_id, [])]

    def get_backtest_trades(self, run_id: str) -> list[dict]:
        return [dict(trade) for trade in self.trades_by_run_id.get(run_id, [])]

    def delete_backtest_run(self, run_id: str) -> None:
        self.deleted_run_ids.append(run_id)


class _MissingRunClient(_FakeRunClient):
    def get_backtest_run(self, run_id: str) -> dict:
        raise DatabaseAccessorClientError("not found", status_code=404)


class _MissingDeleteRunClient(_FakeRunClient):
    def delete_backtest_run(self, run_id: str) -> None:
        raise DatabaseAccessorClientError("not found", status_code=404)


class TestDatabaseAccessorBacktestRunRepository(unittest.TestCase):
    def test_create_maps_queued_domain_record_and_round_trips_response(self) -> None:
        client = _FakeRunClient()
        repository = DatabaseAccessorBacktestRunRepository(client=client)
        run = BacktestRunRecord(
            run_id="run-123",
            status=BacktestRunStatus.QUEUED,
            submitted_at_ms=1_780_921_805_123,
            request_snapshot=BacktestRequestSnapshot.from_request(_request()),
        )

        created = repository.create(run)

        self.assertEqual(
            client.created_payloads,
            [
                {
                    "run_id": "run-123",
                    "status": "queued",
                    "submitted_at": "2026-06-08T12:30:05.123000+00:00",
                    "started_at": None,
                    "completed_at": None,
                    "error_code": None,
                    "error_message": None,
                    "request_schema_version": 1,
                    "request": dict(run.request_snapshot.payload),
                    "result_schema_version": None,
                    "metrics": None,
                    "diagnostics": None,
                    "fills": [],
                    "trades": [],
                }
            ],
        )
        self.assertEqual(created, run)

    def test_get_maps_lifecycle_and_terminal_fields(self) -> None:
        client = _FakeRunClient()
        client.runs_by_id["run-succeeded"] = {
            "run_id": "run-succeeded",
            "status": "succeeded",
            "submitted_at": "2026-06-08T12:30:05.123000+00:00",
            "started_at": "2026-06-08T12:31:00+00:00",
            "completed_at": "2026-06-08T12:35:00+00:00",
            "error_code": None,
            "error_message": None,
            "request_schema_version": 1,
            "request": dict(BacktestRequestSnapshot.from_request(_request()).payload),
            "result_schema_version": 1,
            "metrics": {"total_return_pct": 1.25},
            "diagnostics": {"execution_duration_ms": 240_000},
        }
        repository = DatabaseAccessorBacktestRunRepository(client=client)

        run = repository.get("run-succeeded")

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.status, BacktestRunStatus.SUCCEEDED)
        self.assertEqual(run.submitted_at_ms, 1_780_921_805_123)
        self.assertEqual(run.started_at_ms, 1_780_921_860_000)
        self.assertEqual(run.completed_at_ms, 1_780_922_100_000)
        self.assertEqual(run.request_snapshot.to_request(), _request())
        self.assertEqual(run.result_schema_version, 1)
        self.assertEqual(run.metrics, {"total_return_pct": 1.25})
        self.assertEqual(run.diagnostics, {"execution_duration_ms": 240_000})

    def test_get_maps_accessor_not_found_to_absent_record(self) -> None:
        repository = DatabaseAccessorBacktestRunRepository(client=_MissingRunClient())

        self.assertIsNone(repository.get("run-missing"))

    def test_list_maps_domain_filters_and_preserves_accessor_order(self) -> None:
        client = _FakeRunClient()
        client.listed_payloads = [
            _persisted_run("run-newer", "2026-06-08T12:35:00+00:00"),
            _persisted_run("run-older", "2026-06-08T12:30:00+00:00"),
        ]
        repository = DatabaseAccessorBacktestRunRepository(client=client)

        runs = repository.list(
            BacktestRunQuery(
                status=BacktestRunStatus.QUEUED,
                symbol="EURUSD",
                timeframe="M15",
                strategy_id="sma_crossover",
                engine=BacktestEngine.EVENT_DRIVEN,
                submitted_from_ms=1_780_921_800_000,
                submitted_to_ms=1_780_922_100_000,
            )
        )

        self.assertEqual([run.run_id for run in runs], ["run-newer", "run-older"])
        self.assertEqual(
            client.list_queries,
            [
                {
                    "status": "queued",
                    "symbol": "EURUSD",
                    "timeframe": "M15",
                    "strategy": "sma_crossover",
                    "engine": "event_driven",
                    "submitted_from": "2026-06-08T12:30:00+00:00",
                    "submitted_to": "2026-06-08T12:35:00+00:00",
                }
            ],
        )

    def test_get_execution_logs_maps_accessor_records_and_preserves_order(self) -> None:
        client = _FakeRunClient()
        client.fills_by_run_id["run-succeeded"] = [
            {
                "run_id": "run-succeeded",
                "fill_sequence": 0,
                "timestamp_ms": 1_714_525_200_000,
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 1_000.0,
                "price": 1.0715,
                "fees": 0.15,
                "exit_reason": None,
            },
            {
                "run_id": "run-succeeded",
                "fill_sequence": 1,
                "timestamp_ms": 1_714_532_400_000,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1_000.0,
                "price": 1.074,
                "fees": 0.15,
                "exit_reason": "take_profit",
            },
        ]
        client.trades_by_run_id["run-succeeded"] = [
            {
                "run_id": "run-succeeded",
                "trade_sequence": 0,
                "trade_id": "trade-1",
                "symbol": "EURUSD",
                "quantity": 1_000.0,
                "entry_timestamp_ms": 1_714_525_200_000,
                "entry_price": 1.0715,
                "exit_timestamp_ms": 1_714_532_400_000,
                "exit_price": 1.074,
                "realized_pnl": 2.5,
                "fees": 0.3,
                "exit_reason": "take_profit",
            }
        ]
        repository = DatabaseAccessorBacktestRunRepository(client=client)

        fills = repository.get_fills("run-succeeded")
        trades = repository.get_trades("run-succeeded")

        self.assertEqual(
            fills,
            [
                BacktestFillRecord(
                    run_id="run-succeeded",
                    sequence=0,
                    timestamp_ms=1_714_525_200_000,
                    symbol="EURUSD",
                    side=OrderSide.BUY,
                    quantity=1_000.0,
                    price=1.0715,
                    fees=0.15,
                ),
                BacktestFillRecord(
                    run_id="run-succeeded",
                    sequence=1,
                    timestamp_ms=1_714_532_400_000,
                    symbol="EURUSD",
                    side=OrderSide.SELL,
                    quantity=1_000.0,
                    price=1.074,
                    fees=0.15,
                    exit_reason=ExitReason.TAKE_PROFIT,
                ),
            ],
        )
        self.assertEqual(
            trades,
            [
                BacktestTradeRecord(
                    run_id="run-succeeded",
                    sequence=0,
                    trade_id="trade-1",
                    symbol="EURUSD",
                    quantity=1_000.0,
                    entry_timestamp_ms=1_714_525_200_000,
                    entry_price=1.0715,
                    exit_timestamp_ms=1_714_532_400_000,
                    exit_price=1.074,
                    realized_pnl=2.5,
                    fees=0.3,
                    exit_reason=ExitReason.TAKE_PROFIT,
                )
            ],
        )

    def test_delete_maps_success_and_accessor_not_found(self) -> None:
        client = _FakeRunClient()
        repository = DatabaseAccessorBacktestRunRepository(client=client)

        self.assertTrue(repository.delete("run-succeeded"))
        self.assertEqual(client.deleted_run_ids, ["run-succeeded"])
        self.assertFalse(
            DatabaseAccessorBacktestRunRepository(client=_MissingDeleteRunClient()).delete(
                "run-missing"
            )
        )


def _request() -> BacktestRequest:
    return BacktestRequest(
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
        execution=ExecutionConfig(),
        initial_capital=25_000.0,
        engine=BacktestEngine.EVENT_DRIVEN,
    )


def _persisted_run(run_id: str, submitted_at: str) -> dict:
    return {
        "run_id": run_id,
        "status": "queued",
        "submitted_at": submitted_at,
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "request_schema_version": 1,
        "request": dict(BacktestRequestSnapshot.from_request(_request()).payload),
        "result_schema_version": None,
        "metrics": None,
        "diagnostics": None,
    }


if __name__ == "__main__":
    unittest.main()
