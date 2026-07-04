from __future__ import annotations

import unittest
from dataclasses import replace

from adapters.api.app import create_app
from adapters.api.schemas import BacktestSubmissionRequestSchema
from app.backtest_runs import BacktestRunService
from domain.enums import BacktestEngine, BacktestRunStatus, ExitReason, OrderSide
from domain.types import (
    BacktestFillRecord,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
)
from fastapi.testclient import TestClient


class _FakeRunRepository:
    def __init__(self) -> None:
        self.runs_by_id: dict[str, BacktestRunRecord] = {}
        self.listed_runs: list[BacktestRunRecord] = []
        self.queries: list[BacktestRunQuery] = []
        self.fills_by_run_id: dict[str, list[BacktestFillRecord]] = {}
        self.trades_by_run_id: dict[str, list[BacktestTradeRecord]] = {}
        self.deleted_run_ids: list[str] = []

    def create(self, run: BacktestRunRecord) -> BacktestRunRecord:
        self.runs_by_id[run.run_id] = run
        return run

    def get(self, run_id: str) -> BacktestRunRecord | None:
        return self.runs_by_id.get(run_id)

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        self.queries.append(query)
        return list(self.listed_runs)

    def get_fills(self, run_id: str) -> list[BacktestFillRecord]:
        return list(self.fills_by_run_id.get(run_id, []))

    def get_trades(self, run_id: str) -> list[BacktestTradeRecord]:
        return list(self.trades_by_run_id.get(run_id, []))

    def delete(self, run_id: str) -> bool:
        if run_id not in self.runs_by_id:
            return False
        self.deleted_run_ids.append(run_id)
        del self.runs_by_id[run_id]
        self.fills_by_run_id.pop(run_id, None)
        self.trades_by_run_id.pop(run_id, None)
        return True


class _FailingRunRepository(_FakeRunRepository):
    def get(self, run_id: str) -> BacktestRunRecord | None:
        raise RuntimeError("postgres password=do-not-expose")


class TestBacktestSubmissionRoute(unittest.TestCase):
    def test_submit_returns_accepted_queued_resource_location(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )

        with TestClient(create_app(service=service)) as client:
            response = client.post("/backtests", json=_valid_payload())

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"run_id": "run-123", "status": "queued"})
        self.assertEqual(response.headers["location"], "/backtests/run-123")
        self.assertIn("run-123", repository.runs_by_id)

    def test_submit_rejects_deterministically_invalid_requests_before_create(self) -> None:
        invalid_payloads = (
            {**_valid_payload(), "start_ms": 1_714_608_000_000},
            {**_valid_payload(), "symbols": ["EURUSD", "GBPUSD"]},
            {**_valid_payload(), "data_granularity": "tick"},
            {
                **_valid_payload(),
                "strategy": {"strategy_id": "unknown", "parameters": {}},
            },
            {
                **_valid_payload(),
                "strategy": {
                    "strategy_id": "sma_crossover",
                    "parameters": {"fast_window": 20, "slow_window": 5},
                },
            },
            {
                **_valid_payload(),
                "execution": {
                    **_valid_payload()["execution"],
                    "allow_short": True,
                },
            },
            {**_valid_payload(), "start_ms": True},
            {
                **_valid_payload(),
                "strategy": {
                    "strategy_id": "sma_crossover",
                    "parameters": {"fast_window": 1.5, "slow_window": 20},
                },
            },
            {
                **_valid_payload(),
                "strategy": {
                    "strategy_id": "sma_crossover",
                    "parameters": {"quantity": True},
                },
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with TestClient(create_app(service=service)) as client:
                    response = client.post("/backtests", json=payload)

                self.assertEqual(response.status_code, 422)
                self.assertEqual(repository.runs_by_id, {})


class TestBacktestStatusRoute(unittest.TestCase):
    def test_list_passes_all_filters_and_returns_every_matching_run(self) -> None:
        repository = _FakeRunRepository()
        request = BacktestSubmissionRequestSchema(**_valid_payload()).to_domain()
        base_run = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-base",
            now_ms=lambda: 1_780_921_805_123,
        ).submit(request)
        repository.listed_runs = [
            replace(base_run, run_id="run-newer", submitted_at_ms=1_780_922_000_000),
            replace(base_run, run_id="run-older", submitted_at_ms=1_780_921_900_000),
        ]
        service = BacktestRunService(repository=repository)

        with TestClient(create_app(service=service)) as client:
            response = client.get(
                "/backtests",
                params={
                    "status": "queued",
                    "symbol": "EURUSD",
                    "timeframe": "M15",
                    "strategy": "sma_crossover",
                    "engine": "event_driven",
                    "submitted_from_ms": 1_780_921_800_000,
                    "submitted_to_ms": 1_780_922_100_000,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [run["run_id"] for run in response.json()],
            ["run-newer", "run-older"],
        )
        self.assertEqual(
            repository.queries,
            [
                BacktestRunQuery(
                    status=BacktestRunStatus.QUEUED,
                    symbol="EURUSD",
                    timeframe="M15",
                    strategy_id="sma_crossover",
                    engine=BacktestEngine.EVENT_DRIVEN,
                    submitted_from_ms=1_780_921_800_000,
                    submitted_to_ms=1_780_922_100_000,
                )
            ],
        )

    def test_list_exposes_no_pagination_controls(self) -> None:
        app = create_app(service=BacktestRunService(repository=_FakeRunRepository()))

        parameters = app.openapi()["paths"]["/backtests"]["get"]["parameters"]

        self.assertEqual(
            {parameter["name"] for parameter in parameters},
            {
                "status",
                "symbol",
                "timeframe",
                "strategy",
                "engine",
                "submitted_from_ms",
                "submitted_to_ms",
            },
        )

    def test_list_rejects_inverted_submission_date_range(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(repository=repository)

        with TestClient(create_app(service=service)) as client:
            response = client.get(
                "/backtests",
                params={
                    "submitted_from_ms": 1_780_922_100_000,
                    "submitted_to_ms": 1_780_921_800_000,
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(repository.queries, [])

    def test_get_exposes_only_fields_valid_for_each_lifecycle_state(self) -> None:
        repository = _FakeRunRepository()
        request = BacktestSubmissionRequestSchema(**_valid_payload()).to_domain()
        queued = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-base",
            now_ms=lambda: 1_780_921_805_123,
        ).submit(request)
        repository.runs_by_id = {
            "run-queued": replace(queued, run_id="run-queued"),
            "run-running": replace(
                queued,
                run_id="run-running",
                status=BacktestRunStatus.RUNNING,
                started_at_ms=1_780_921_860_000,
            ),
            "run-succeeded": replace(
                queued,
                run_id="run-succeeded",
                status=BacktestRunStatus.SUCCEEDED,
                started_at_ms=1_780_921_860_000,
                completed_at_ms=1_780_922_100_000,
                result_schema_version=2,
                metrics={"total_return_pct": 1.25},
                diagnostics={"execution_duration_ms": 240_000},
            ),
            "run-failed": replace(
                queued,
                run_id="run-failed",
                status=BacktestRunStatus.FAILED,
                started_at_ms=1_780_921_860_000,
                completed_at_ms=1_780_922_100_000,
                error_code="market_data_unavailable",
                error_message="Historical market data is unavailable",
            ),
            "run-failed-internal": replace(
                queued,
                run_id="run-failed-internal",
                status=BacktestRunStatus.FAILED,
                started_at_ms=1_780_921_860_000,
                completed_at_ms=1_780_922_100_000,
                error_code="engine_failure",
                error_message=(
                    "Traceback (most recent call last):\n"
                    "RuntimeError: secret implementation detail"
                ),
            ),
            "run-failed-one-line-internal": replace(
                queued,
                run_id="run-failed-one-line-internal",
                status=BacktestRunStatus.FAILED,
                started_at_ms=1_780_921_860_000,
                completed_at_ms=1_780_922_100_000,
                error_code="RuntimeError: database password exposed",
                error_message="RuntimeError: database password exposed",
            ),
        }
        service = BacktestRunService(repository=repository)

        with TestClient(create_app(service=service)) as client:
            queued_response = client.get("/backtests/run-queued")
            running_response = client.get("/backtests/run-running")
            succeeded_response = client.get("/backtests/run-succeeded")
            failed_response = client.get("/backtests/run-failed")
            internal_failure_response = client.get("/backtests/run-failed-internal")
            one_line_internal_failure_response = client.get(
                "/backtests/run-failed-one-line-internal"
            )

        self.assertEqual(queued_response.status_code, 200)
        self.assertEqual(
            queued_response.json(),
            {
                "run_id": "run-queued",
                "status": "queued",
                "submitted_at_ms": 1_780_921_805_123,
                "request_schema_version": 1,
                "request": _valid_payload(),
            },
        )

        running_body = running_response.json()
        self.assertEqual(running_response.status_code, 200)
        self.assertEqual(running_body["started_at_ms"], 1_780_921_860_000)
        self.assertNotIn("metrics", running_body)
        self.assertNotIn("diagnostics", running_body)
        self.assertNotIn("error_code", running_body)
        self.assertNotIn("error_message", running_body)

        succeeded_body = succeeded_response.json()
        self.assertEqual(succeeded_response.status_code, 200)
        self.assertEqual(succeeded_body["completed_at_ms"], 1_780_922_100_000)
        self.assertEqual(succeeded_body["result_schema_version"], 2)
        self.assertEqual(succeeded_body["metrics"], {"total_return_pct": 1.25})
        self.assertEqual(
            succeeded_body["diagnostics"],
            {"execution_duration_ms": 240_000},
        )
        self.assertNotIn("error_code", succeeded_body)
        self.assertNotIn("error_message", succeeded_body)

        failed_body = failed_response.json()
        self.assertEqual(failed_response.status_code, 200)
        self.assertEqual(failed_body["error_code"], "market_data_unavailable")
        self.assertEqual(
            failed_body["error_message"],
            "Historical market data is unavailable",
        )
        self.assertNotIn("result_schema_version", failed_body)
        self.assertNotIn("metrics", failed_body)
        self.assertNotIn("diagnostics", failed_body)
        self.assertEqual(
            internal_failure_response.json()["error_message"],
            "Backtest execution failed",
        )
        self.assertNotIn("Traceback", internal_failure_response.text)
        self.assertEqual(
            one_line_internal_failure_response.json(),
            {
                **{
                    key: value
                    for key, value in failed_body.items()
                    if key not in {"run_id", "error_code", "error_message"}
                },
                "run_id": "run-failed-one-line-internal",
                "error_code": "backtest_failed",
                "error_message": "Backtest execution failed",
            },
        )
        self.assertNotIn("password", one_line_internal_failure_response.text)

    def test_get_missing_run_returns_not_found(self) -> None:
        service = BacktestRunService(repository=_FakeRunRepository())

        with TestClient(create_app(service=service)) as client:
            response = client.get("/backtests/run-missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Backtest run not found"})

    def test_get_does_not_expose_internal_persistence_exception_details(self) -> None:
        service = BacktestRunService(repository=_FailingRunRepository())

        with TestClient(
            create_app(service=service),
            raise_server_exceptions=False,
        ) as client:
            response = client.get("/backtests/run-123")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Backtest persistence unavailable"})
        self.assertNotIn("password", response.text)


class TestBacktestExecutionLogAndDeletionRoutes(unittest.TestCase):
    def test_get_fills_and_trades_returns_ordered_public_records(self) -> None:
        repository, service = _terminal_run_service("run-succeeded")
        repository.fills_by_run_id["run-succeeded"] = [
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
                exit_reason=ExitReason.STOP_LOSS,
            ),
        ]
        repository.trades_by_run_id["run-succeeded"] = [
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
                exit_reason=ExitReason.STOP_LOSS,
                stop_loss_price=1.05,
                take_profit_price=1.08,
            )
        ]

        with TestClient(create_app(service=service)) as client:
            fills_response = client.get("/backtests/run-succeeded/fills")
            trades_response = client.get("/backtests/run-succeeded/trades")

        self.assertEqual(fills_response.status_code, 200)
        self.assertEqual(
            fills_response.json(),
            [
                {
                    "sequence": 0,
                    "timestamp_ms": 1_714_525_200_000,
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 1_000.0,
                    "price": 1.0715,
                    "fees": 0.15,
                    "exit_reason": None,
                },
                {
                    "sequence": 1,
                    "timestamp_ms": 1_714_532_400_000,
                    "symbol": "EURUSD",
                    "side": "sell",
                    "quantity": 1_000.0,
                    "price": 1.074,
                    "fees": 0.15,
                    "exit_reason": "stop_loss",
                },
            ],
        )
        self.assertEqual(trades_response.status_code, 200)
        self.assertEqual(
            trades_response.json(),
            [
                {
                    "sequence": 0,
                    "trade_id": "trade-1",
                    "symbol": "EURUSD",
                    "quantity": 1_000.0,
                    "entry_timestamp_ms": 1_714_525_200_000,
                    "entry_price": 1.0715,
                    "exit_timestamp_ms": 1_714_532_400_000,
                    "exit_price": 1.074,
                    "realized_pnl": 2.5,
                    "fees": 0.3,
                    "exit_reason": "stop_loss",
                    "stop_loss_price": 1.05,
                    "take_profit_price": 1.08,
                }
            ],
        )

    def test_execution_logs_return_empty_collections_and_missing_is_not_found(self) -> None:
        _, service = _terminal_run_service("run-empty")

        with TestClient(create_app(service=service)) as client:
            self.assertEqual(client.get("/backtests/run-empty/fills").json(), [])
            self.assertEqual(client.get("/backtests/run-empty/trades").json(), [])
            for path in (
                "/backtests/run-missing/fills",
                "/backtests/run-missing/trades",
                "/backtests/run-missing",
            ):
                with self.subTest(path=path):
                    response = (
                        client.delete(path)
                        if path == "/backtests/run-missing"
                        else client.get(path)
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(
                        response.json(),
                        {"detail": "Backtest run not found"},
                    )

    def test_delete_terminal_runs_and_reject_active_runs(self) -> None:
        repository, service = _terminal_run_service("run-succeeded")
        failed = replace(
            repository.runs_by_id["run-succeeded"],
            run_id="run-failed",
            status=BacktestRunStatus.FAILED,
            result_schema_version=None,
            metrics=None,
            diagnostics=None,
            error_code="engine_failure",
            error_message="Backtest execution failed",
        )
        queued = replace(
            repository.runs_by_id["run-succeeded"],
            run_id="run-queued",
            status=BacktestRunStatus.QUEUED,
            started_at_ms=None,
            completed_at_ms=None,
            result_schema_version=None,
            metrics=None,
            diagnostics=None,
        )
        running = replace(
            queued,
            run_id="run-running",
            status=BacktestRunStatus.RUNNING,
            started_at_ms=1_780_921_860_000,
        )
        repository.runs_by_id.update(
            {
                "run-failed": failed,
                "run-queued": queued,
                "run-running": running,
            }
        )

        with TestClient(create_app(service=service)) as client:
            for run_id in ("run-succeeded", "run-failed"):
                with self.subTest(run_id=run_id):
                    response = client.delete(f"/backtests/{run_id}")
                    self.assertEqual(response.status_code, 204)
                    self.assertEqual(response.content, b"")

            for run_id in ("run-queued", "run-running"):
                with self.subTest(run_id=run_id):
                    response = client.delete(f"/backtests/{run_id}")
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(
                        response.json(),
                        {"detail": "Only terminal backtest runs can be deleted"},
                    )
                    self.assertIn(run_id, repository.runs_by_id)

        self.assertEqual(repository.deleted_run_ids, ["run-succeeded", "run-failed"])


def _terminal_run_service(run_id: str) -> tuple[_FakeRunRepository, BacktestRunService]:
    repository = _FakeRunRepository()
    request = BacktestSubmissionRequestSchema(**_valid_payload()).to_domain()
    queued = BacktestRunService(
        repository=repository,
        new_run_id=lambda: run_id,
        now_ms=lambda: 1_780_921_805_123,
    ).submit(request)
    repository.runs_by_id[run_id] = replace(
        queued,
        status=BacktestRunStatus.SUCCEEDED,
        started_at_ms=1_780_921_860_000,
        completed_at_ms=1_780_922_100_000,
        result_schema_version=2,
        metrics={"trade_count": 0},
        diagnostics={"bars": 10},
    )
    return repository, BacktestRunService(repository=repository)


def _valid_payload() -> dict:
    return {
        "symbols": ["EURUSD"],
        "exchange": "FX",
        "timeframe": "M15",
        "start_ms": 1_714_521_600_000,
        "end_ms": 1_714_608_000_000,
        "engine": "event_driven",
        "data_granularity": "bar",
        "initial_capital": 25_000.0,
        "strategy": {
            "strategy_id": "sma_crossover",
            "parameters": {
                "fast_window": 5,
                "slow_window": 20,
                "quantity": 1_000.0,
            },
        },
        "execution": {
            "signal_timing": "close",
            "fill_timing": "next_open",
            "price_source": "open",
            "allow_partial_fills": False,
            "allow_short": False,
            "trade_accounting_policy": "average_cost",
            "gap_policy": "skip",
            "intrabar_exit_policy": "conservative",
            "commission_bps": 0.0,
            "slippage_bps": 0.0,
        },
        "persist_result": False,
        "run_metadata": {"label": "api-smoke"},
    }


if __name__ == "__main__":
    unittest.main()
