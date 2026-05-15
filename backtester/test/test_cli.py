import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import cli
import pandas as pd
from domain.enums import BacktestEngine, OrderSide
from domain.types import BacktestResult, Fill, PortfolioSnapshot, Trade


class TestCli(unittest.TestCase):
    def test_run_command_maps_args_and_prints_summary(self) -> None:
        captured_requests = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = data_adapter
            captured_requests.append((request, strategy, exchange))
            return BacktestResult(
                request=request,
                fills=[
                    Fill(
                        timestamp_ms=request.start_ms + 60_000,
                        symbol=request.symbols[0],
                        quantity=1.0,
                        price=101.0,
                        side=OrderSide.BUY,
                    )
                ],
                trades=[
                    Trade(
                        trade_id="trade-1",
                        symbol=request.symbols[0],
                        quantity=1.0,
                        entry_timestamp_ms=request.start_ms + 60_000,
                        entry_price=101.0,
                    )
                ],
                equity_curve=[
                    PortfolioSnapshot(
                        timestamp_ms=request.start_ms + 60_000,
                        cash=9_899.0,
                        equity=10_005.0,
                        positions={request.symbols[0]: 1.0},
                    )
                ],
                metrics={
                    "total_return_pct": 0.05,
                    "max_drawdown_pct": -0.01,
                    "trade_count": 1.0,
                },
                diagnostics={"bars": 100},
            )

        argv = [
            "run",
            "--symbol",
            "AAPL",
            "--timeframe",
            "M15",
            "--start-ms",
            "1700000000000",
            "--end-ms",
            "1700000900000",
            "--strategy",
            "sma_crossover",
            "--engine",
            "event_driven",
            "--fast-window",
            "7",
            "--slow-window",
            "20",
            "--quantity",
            "2.5",
            "--initial-capital",
            "50000",
            "--exchange",
            "NASDAQ",
        ]

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
            side_effect=_fake_run_backtest_with_market_data,
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.main(argv)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(captured_requests), 1)

        request, strategy, exchange = captured_requests[0]
        self.assertEqual(request.symbols, ["AAPL"])
        self.assertEqual(request.timeframe, "M15")
        self.assertEqual(request.start_ms, 1_700_000_000_000)
        self.assertEqual(request.end_ms, 1_700_000_900_000)
        self.assertEqual(request.initial_capital, 50_000.0)
        self.assertEqual(request.engine, BacktestEngine.EVENT_DRIVEN)
        self.assertFalse(request.persist_result)
        self.assertEqual(request.strategy.parameters["fast_window"], 7)
        self.assertEqual(request.strategy.parameters["slow_window"], 20)
        self.assertEqual(request.strategy.parameters["quantity"], 2.5)
        self.assertIsNone(strategy)
        self.assertEqual(exchange, "NASDAQ")

        output = stdout.getvalue()
        self.assertIn("Backtest completed", output)
        self.assertIn("engine=event_driven", output)
        self.assertIn("fills=1 trades=1", output)
        self.assertIn("total_return_pct=0.050000", output)
        self.assertIn("final_equity=10005.000000", output)

    def test_run_command_can_request_persistence_and_prints_saved_metadata(self) -> None:
        captured_requests = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = (strategy, exchange, data_adapter)
            captured_requests.append(request)
            return BacktestResult(
                request=request,
                fills=[],
                trades=[],
                equity_curve=[
                    PortfolioSnapshot(
                        timestamp_ms=request.end_ms,
                        cash=10_100.0,
                        equity=10_100.0,
                        positions={},
                    )
                ],
                metrics={
                    "total_return_pct": 1.0,
                    "max_drawdown_pct": 0.0,
                    "trade_count": 0.0,
                },
                diagnostics={"bars": 10},
                backtest_run_id="run-123",
                persisted_at=1_700_000_000_123,
            )

        stdout = io.StringIO()
        with patch(
            "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
            side_effect=_fake_run_backtest_with_market_data,
        ):
            with redirect_stdout(stdout):
                exit_code = cli.main(
                    [
                        "run",
                        "--symbol",
                        "AAPL",
                        "--timeframe",
                        "M1",
                        "--start-ms",
                        "1700000000000",
                        "--end-ms",
                        "1700000600000",
                        "--persist-result",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(captured_requests), 1)
        self.assertTrue(captured_requests[0].persist_result)
        output = stdout.getvalue()
        self.assertIn("backtest_run_id=run-123", output)
        self.assertIn("persisted_at_ms=1700000000123", output)

    def test_run_command_accepts_explicit_vectorized_and_defaults_to_vectorized(self) -> None:
        captured_requests = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = (strategy, exchange, data_adapter)
            captured_requests.append(request)
            return BacktestResult(
                request=request,
                fills=[],
                trades=[],
                equity_curve=[],
                metrics={},
                diagnostics={},
            )

        base_argv = [
            "run",
            "--symbol",
            "AAPL",
            "--timeframe",
            "M1",
            "--start-ms",
            "1700000000000",
            "--end-ms",
            "1700000600000",
        ]

        with patch(
            "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
            side_effect=_fake_run_backtest_with_market_data,
        ):
            for extra_args in ([], ["--engine", "vectorized"]):
                with self.subTest(extra_args=extra_args):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        exit_code = cli.main([*base_argv, *extra_args])

                    self.assertEqual(exit_code, 0)
                    self.assertEqual(captured_requests[-1].engine, BacktestEngine.VECTORIZED)
                    self.assertIn("engine=vectorized", stdout.getvalue())

    def test_run_command_uses_topology_db_accessor_defaults(self) -> None:
        observed_env: list[tuple[str | None, str | None]] = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = (request, strategy, exchange, data_adapter)
            observed_env.append(
                (
                    os.environ.get("DATABASE_ACCESSOR_HOST"),
                    os.environ.get("DATABASE_ACCESSOR_PORT"),
                )
            )
            return BacktestResult(
                request=request,
                fills=[],
                trades=[],
                equity_curve=[],
                metrics={},
                diagnostics={},
            )

        with patch.dict(
            os.environ,
            {
                "DATABASE_ACCESSOR_HOST": "database-accessor-api",
                "DATABASE_ACCESSOR_PORT": "8000",
            },
            clear=True,
        ):
            with patch(
                "cli._read_local_topology_file",
                return_value={
                    "public": {"host": "127.0.0.1"},
                    "services": {
                        "database_accessor_api": {
                            "host": "database-accessor-api",
                            "port": 8000,
                            "published_port": 18000,
                        },
                    },
                },
            ):
                with patch(
                    "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
                    side_effect=_fake_run_backtest_with_market_data,
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        exit_code = cli.main(
                            [
                                "run",
                                "--symbol",
                                "AAPL",
                                "--timeframe",
                                "M1",
                                "--start-ms",
                                "1700000000000",
                                "--end-ms",
                                "1700000600000",
                            ]
                        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed_env, [("127.0.0.1", "18000")])

    def test_run_command_falls_back_to_generated_env_when_topology_missing(self) -> None:
        observed_env: list[tuple[str | None, str | None]] = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = (request, strategy, exchange, data_adapter)
            observed_env.append(
                (
                    os.environ.get("DATABASE_ACCESSOR_HOST"),
                    os.environ.get("DATABASE_ACCESSOR_PORT"),
                )
            )
            return BacktestResult(
                request=request,
                fills=[],
                trades=[],
                equity_curve=[],
                metrics={},
                diagnostics={},
            )

        with patch.dict(os.environ, {}, clear=True):
            with patch("cli._read_local_topology_file", return_value={}):
                with patch(
                    "cli._read_local_env_file",
                    return_value={
                        "PUBLIC_HOST": "127.0.0.1",
                        "DATABASE_ACCESSOR_PUBLISHED_PORT": "18000",
                    },
                ):
                    with patch(
                        "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
                        side_effect=_fake_run_backtest_with_market_data,
                    ):
                        stdout = io.StringIO()
                        with redirect_stdout(stdout):
                            exit_code = cli.main(
                                [
                                    "run",
                                    "--symbol",
                                    "AAPL",
                                    "--timeframe",
                                    "M1",
                                    "--start-ms",
                                    "1700000000000",
                                    "--end-ms",
                                    "1700000600000",
                                ]
                            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed_env, [("127.0.0.1", "18000")])

    def test_run_command_prefers_cli_db_accessor_overrides(self) -> None:
        observed_env: list[tuple[str | None, str | None]] = []

        def _fake_run_backtest_with_market_data(
            *,
            request,
            strategy=None,
            exchange=None,
            data_adapter=None,
        ):
            _ = (request, strategy, exchange, data_adapter)
            observed_env.append(
                (
                    os.environ.get("DATABASE_ACCESSOR_HOST"),
                    os.environ.get("DATABASE_ACCESSOR_PORT"),
                )
            )
            return BacktestResult(
                request=request,
                fills=[],
                trades=[],
                equity_curve=[],
                metrics={},
                diagnostics={},
            )

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "cli._read_local_topology_file",
                return_value={
                    "public": {"host": "127.0.0.1"},
                    "services": {
                        "database_accessor_api": {
                            "published_port": 18000,
                        },
                    },
                },
            ):
                with patch(
                    "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
                    side_effect=_fake_run_backtest_with_market_data,
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        exit_code = cli.main(
                            [
                                "run",
                                "--symbol",
                                "AAPL",
                                "--timeframe",
                                "M1",
                                "--start-ms",
                                "1700000000000",
                                "--end-ms",
                                "1700000600000",
                                "--db-accessor-host",
                                "localhost",
                                "--db-accessor-port",
                                "9001",
                            ]
                        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed_env, [("localhost", "9001")])

    def test_run_command_executes_real_pipeline_deterministically(self) -> None:
        start_ms = 1_700_000_000_000
        minute = 60_000
        end_ms = start_ms + (9 * minute)
        raw_bars = pd.DataFrame(
            {
                "timestamp_ms": [start_ms - (2 * minute) + (minute * i) for i in range(11)],
                "symbol": ["AAPL"] * 11,
                "open": [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 10.0, 11.0, 12.0, 13.0],
                "high": [12.5, 11.5, 10.5, 9.5, 8.5, 9.5, 10.5, 10.5, 11.5, 12.5, 13.5],
                "low": [11.5, 10.5, 9.5, 8.5, 7.5, 8.5, 9.5, 9.5, 10.5, 11.5, 12.5],
                "close": [12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0],
                "volume": [1_000.0] * 11,
            }
        )

        fetch_calls: list[dict] = []

        def _fake_fetch_bars(_self, **kwargs) -> pd.DataFrame:
            fetch_calls.append(kwargs)
            return raw_bars.copy()

        argv = [
            "run",
            "--symbol",
            "AAPL",
            "--timeframe",
            "M1",
            "--start-ms",
            str(start_ms),
            "--end-ms",
            str(end_ms),
            "--fast-window",
            "2",
            "--slow-window",
            "3",
            "--quantity",
            "1.0",
        ]

        with patch(
            "adapters.db_accessor.DatabaseAccessorHistoricalDataAdapter.fetch_bars",
            autospec=True,
            side_effect=_fake_fetch_bars,
        ):
            stdout_one = io.StringIO()
            stderr_one = io.StringIO()
            with redirect_stdout(stdout_one), redirect_stderr(stderr_one):
                exit_code_one = cli.main(argv)

            stdout_two = io.StringIO()
            stderr_two = io.StringIO()
            with redirect_stdout(stdout_two), redirect_stderr(stderr_two):
                exit_code_two = cli.main(argv)

        self.assertEqual(exit_code_one, 0)
        self.assertEqual(exit_code_two, 0)
        self.assertEqual(stderr_one.getvalue(), "")
        self.assertEqual(stderr_two.getvalue(), "")
        self.assertEqual(len(fetch_calls), 2)

        expected_fetch_start = start_ms - (2 * minute)
        self.assertEqual(fetch_calls[0]["symbol"], "AAPL")
        self.assertEqual(fetch_calls[0]["timeframe"], "M1")
        self.assertEqual(fetch_calls[0]["start_ms"], expected_fetch_start)
        self.assertEqual(fetch_calls[0]["end_ms"], end_ms)

        output_one = stdout_one.getvalue()
        output_two = stdout_two.getvalue()
        self.assertEqual(output_one, output_two)
        self.assertIn("Backtest completed", output_one)
        self.assertIn("strategy=sma_crossover", output_one)
        self.assertIn("fills=", output_one)
        self.assertIn("trades=", output_one)

    def test_run_command_returns_non_zero_on_runner_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
            side_effect=RuntimeError("boom"),
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "run",
                        "--symbol",
                        "AAPL",
                        "--timeframe",
                        "M1",
                        "--start-ms",
                        "1700000000000",
                        "--end-ms",
                        "1700000600000",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: boom", stderr.getvalue())

    def test_run_command_prints_http_response_body_on_runner_error(self) -> None:
        class _HttpError(Exception):
            status_code = 404
            response_text = '{"detail":"Market not found"}'

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "cli._BACKTEST_RUNNER_MODULE.run_backtest_with_market_data",
            side_effect=_HttpError("database-accessor-api HTTP error: 404"),
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "run",
                        "--symbol",
                        "AAPL",
                        "--timeframe",
                        "M1",
                        "--start-ms",
                        "1700000000000",
                        "--end-ms",
                        "1700000600000",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            'Error: database-accessor-api HTTP error: 404: {"detail":"Market not found"}',
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
