import unittest
from dataclasses import replace

from app.backtest_runs import (
    BacktestRunNotFoundError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from domain.enums import BacktestRunStatus, DataGranularity, PriceSource
from domain.types import (
    BacktestRequest,
    BacktestRunQuery,
    BacktestRunRecord,
    ExecutionConfig,
    StrategyConfig,
)


class _FakeRunRepository:
    def __init__(self) -> None:
        self.created_runs: list[BacktestRunRecord] = []
        self.runs_by_id: dict[str, BacktestRunRecord] = {}

    def create(self, run: BacktestRunRecord) -> BacktestRunRecord:
        self.created_runs.append(run)
        self.runs_by_id[run.run_id] = run
        return run

    def get(self, run_id: str) -> BacktestRunRecord | None:
        return self.runs_by_id.get(run_id)

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        del query
        return list(self.runs_by_id.values())


class TestBacktestRunService(unittest.TestCase):
    def test_submit_persists_immutable_queued_run(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )
        request = _valid_request()

        submitted = service.submit(request)

        self.assertEqual(submitted.run_id, "run-123")
        self.assertEqual(submitted.status, BacktestRunStatus.QUEUED)
        self.assertEqual(submitted.submitted_at_ms, 1_780_921_805_123)
        self.assertEqual(submitted.request_snapshot.to_request(), request)
        self.assertEqual(repository.created_runs, [submitted])

    def test_submit_rejects_invalid_timestamp_range_before_persistence(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(repository=repository)
        request = _valid_request()
        request = replace(request, start_ms=request.end_ms)

        with self.assertRaisesRegex(InvalidBacktestRequestError, "start_ms must be less"):
            service.submit(request)

        self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_non_integer_timestamps_before_persistence(self) -> None:
        invalid_timestamps = (
            replace(_valid_request(), start_ms=True),
            replace(_valid_request(), end_ms=1_714_608_000_000.5),
        )

        for request in invalid_timestamps:
            with self.subTest(request=request):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(
                    InvalidBacktestRequestError,
                    "integer epoch milliseconds",
                ):
                    service.submit(request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_non_single_symbol_or_non_bar_requests(self) -> None:
        invalid_requests = (
            (replace(_valid_request(), symbols=["EURUSD", "GBPUSD"]), "exactly one symbol"),
            (
                replace(_valid_request(), data_granularity=DataGranularity.TICK),
                "bar data only",
            ),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(InvalidBacktestRequestError, message):
                    service.submit(request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_unknown_or_invalid_strategy_before_persistence(self) -> None:
        invalid_requests = (
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(strategy_id="unknown"),
                ),
                "Unknown strategy_id",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 20, "slow_window": 5},
                    ),
                ),
                "fast_window must be strictly smaller",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 1.5, "slow_window": 20},
                    ),
                ),
                "SMA windows must be integers",
            ),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(InvalidBacktestRequestError, message):
                    service.submit(request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_unsupported_execution_policies_before_persistence(self) -> None:
        invalid_execution_configs = (
            replace(ExecutionConfig(), allow_short=True),
            replace(ExecutionConfig(), allow_partial_fills=True),
            replace(ExecutionConfig(), price_source=PriceSource.CLOSE),
        )

        for execution in invalid_execution_configs:
            with self.subTest(execution=execution):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(
                    InvalidBacktestRequestError,
                    "Unsupported execution configuration",
                ):
                    service.submit(replace(_valid_request(), execution=execution))

                self.assertEqual(repository.created_runs, [])

    def test_get_returns_persisted_run_and_reports_missing_identity(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )
        submitted = service.submit(_valid_request())

        self.assertEqual(service.get("run-123"), submitted)
        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.get("run-missing")


def _valid_request() -> BacktestRequest:
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
    )


if __name__ == "__main__":
    unittest.main()
