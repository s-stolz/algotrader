import unittest

from adapters.persistence import DatabaseAccessorBacktestRunRepository
from db_accessor_client import DatabaseAccessorClientError
from domain.enums import BacktestEngine, BacktestRunStatus
from domain.types import (
    BacktestRequest,
    BacktestRequestSnapshot,
    BacktestRunRecord,
    ExecutionConfig,
    StrategyConfig,
)


class _FakeRunClient:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []
        self.runs_by_id: dict[str, dict] = {}

    def create_backtest_run(self, run: dict) -> dict:
        self.created_payloads.append(run)
        self.runs_by_id[run["run_id"]] = dict(run)
        return dict(run)

    def get_backtest_run(self, run_id: str) -> dict:
        return dict(self.runs_by_id[run_id])


class _MissingRunClient(_FakeRunClient):
    def get_backtest_run(self, run_id: str) -> dict:
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


if __name__ == "__main__":
    unittest.main()
