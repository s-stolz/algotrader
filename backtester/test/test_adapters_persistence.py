import unittest

from adapters.persistence import BacktestRunSummaryPersistenceAdapter
from domain.enums import BacktestEngine
from domain.types import (
    BacktestRequest,
    BacktestResult,
    ExecutionConfig,
    PortfolioSnapshot,
    StrategyConfig,
)


class _FakeRunSummaryClient:
    def __init__(self) -> None:
        self.saved_summaries: list[dict] = []

    def store_backtest_run_summary(self, summary: dict) -> dict:
        self.saved_summaries.append(dict(summary))
        return {
            "run_id": "run-123",
            "persisted_at": "2026-05-15T12:30:05.123000+00:00",
        }


class _FailingRunSummaryClient:
    def store_backtest_run_summary(self, summary: dict) -> dict:
        raise RuntimeError("database accessor unavailable")


class TestBacktestRunSummaryPersistenceAdapter(unittest.TestCase):
    def test_save_run_summary_maps_completed_result_and_applies_metadata(self) -> None:
        client = _FakeRunSummaryClient()
        adapter = BacktestRunSummaryPersistenceAdapter(client=client)
        result = _build_result(
            final_snapshot=PortfolioSnapshot(
                timestamp_ms=1_714_608_000_000,
                cash=10_250.25,
                equity=10_750.25,
                positions={"EURUSD": 1_000.0},
            )
        )

        saved_result = adapter.save_run_summary(
            result=result,
            execution_duration_ms=275,
        )

        self.assertEqual(
            client.saved_summaries,
            [
                {
                    "execution_duration_ms": 275,
                    "symbol": "EURUSD",
                    "timeframe": "M15",
                    "engine": "vectorized",
                    "strategy_id": "sma_crossover",
                    "start_ms": 1_714_521_600_000,
                    "end_ms": 1_714_608_000_000,
                    "initial_capital": 10_000.0,
                    "final_equity": 10_750.25,
                    "final_cash": 10_250.25,
                    "final_position_symbol": "EURUSD",
                    "final_position_quantity": 1_000.0,
                    "total_return_pct": 7.5025,
                    "max_drawdown_pct": -2.25,
                    "trade_count": 1,
                }
            ],
        )
        self.assertEqual(saved_result.backtest_run_id, "run-123")
        self.assertEqual(saved_result.persisted_at, 1_778_848_205_123)
        self.assertIsNone(result.backtest_run_id)
        self.assertIsNone(result.persisted_at)

    def test_save_run_summary_persists_successful_no_trade_run_without_trades(self) -> None:
        client = _FakeRunSummaryClient()
        adapter = BacktestRunSummaryPersistenceAdapter(client=client)
        result = _build_result(
            final_snapshot=PortfolioSnapshot(
                timestamp_ms=1_714_608_000_000,
                cash=10_000.0,
                equity=10_000.0,
                positions={},
            ),
            metrics={
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": 0.0,
            },
        )

        saved_result = adapter.save_run_summary(result=result)

        self.assertEqual(saved_result.backtest_run_id, "run-123")
        self.assertEqual(client.saved_summaries[0]["execution_duration_ms"], 0)
        self.assertEqual(client.saved_summaries[0]["final_position_symbol"], None)
        self.assertEqual(client.saved_summaries[0]["final_position_quantity"], 0.0)
        self.assertEqual(client.saved_summaries[0]["trade_count"], 0)
        self.assertNotIn("trades", client.saved_summaries[0])

    def test_save_run_summary_surfaces_persistence_errors(self) -> None:
        adapter = BacktestRunSummaryPersistenceAdapter(client=_FailingRunSummaryClient())
        result = _build_result(
            final_snapshot=PortfolioSnapshot(
                timestamp_ms=1_714_608_000_000,
                cash=10_250.25,
                equity=10_750.25,
                positions={"EURUSD": 1_000.0},
            )
        )

        with self.assertRaisesRegex(RuntimeError, "database accessor unavailable"):
            adapter.save_run_summary(result=result, execution_duration_ms=275)


def _build_result(
    *,
    final_snapshot: PortfolioSnapshot,
    metrics: dict[str, float] | None = None,
) -> BacktestResult:
    request = BacktestRequest(
        symbols=["EURUSD"],
        timeframe="M15",
        start_ms=1_714_521_600_000,
        end_ms=1_714_608_000_000,
        strategy=StrategyConfig(strategy_id="sma_crossover"),
        execution=ExecutionConfig(),
        initial_capital=10_000.0,
        engine=BacktestEngine.VECTORIZED,
    )
    return BacktestResult(
        request=request,
        equity_curve=[
            PortfolioSnapshot(
                timestamp_ms=1_714_521_600_000,
                cash=10_000.0,
                equity=10_000.0,
                positions={},
            ),
            final_snapshot,
        ],
        metrics=metrics
        or {
            "total_return_pct": 7.5025,
            "max_drawdown_pct": -2.25,
            "trade_count": 1.0,
        },
    )


if __name__ == "__main__":
    unittest.main()
