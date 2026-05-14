"""Local backtester CLI entrypoint."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Sequence

_SRC_PATH = Path(__file__).resolve().parent / "src"
_SRC_PATH_TEXT = str(_SRC_PATH)
if _SRC_PATH_TEXT not in sys.path:
    sys.path.insert(0, _SRC_PATH_TEXT)

_BACKTEST_RUNNER_MODULE = importlib.import_module("app.backtest_runner")
_APP_CONFIG_MODULE = importlib.import_module("app.config")
_DOMAIN_ENUMS_MODULE = importlib.import_module("domain.enums")
_DOMAIN_TYPES_MODULE = importlib.import_module("domain.types")

__all__ = ["build_parser", "main"]

_DEFAULT_LOCAL_DB_ACCESSOR_HOST = "localhost"
_DEFAULT_LOCAL_DB_ACCESSOR_PORT = "8000"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backtester",
        description="Run bar backtests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one backtest")
    run_parser.add_argument("--symbol", required=True, help="Instrument symbol (e.g. EURUSD)")
    run_parser.add_argument("--timeframe", required=True, help="Timeframe code (e.g. M15, H1)")
    run_parser.add_argument(
        "--start-ms",
        required=True,
        type=int,
        help="Start timestamp (UTC epoch ms)",
    )
    run_parser.add_argument(
        "--end-ms",
        required=True,
        type=int,
        help="End timestamp (UTC epoch ms)",
    )
    run_parser.add_argument("--strategy", default="sma_crossover", choices=("sma_crossover",))
    run_parser.add_argument(
        "--engine",
        default=_DOMAIN_ENUMS_MODULE.BacktestEngine.VECTORIZED.value,
        choices=tuple(engine.value for engine in _DOMAIN_ENUMS_MODULE.BacktestEngine),
        help="Backtest engine backend.",
    )
    run_parser.add_argument("--fast-window", default=5, type=int)
    run_parser.add_argument("--slow-window", default=20, type=int)
    run_parser.add_argument("--quantity", default=1.0, type=float)
    run_parser.add_argument("--initial-capital", default=10_000.0, type=float)
    run_parser.add_argument("--exchange", default=None)
    run_parser.add_argument(
        "--db-accessor-host",
        default=None,
        help=(
            "Override database accessor host. Defaults to DATABASE_ACCESSOR_HOST or "
            "the local published host from config/.env.shared."
        ),
    )
    run_parser.add_argument(
        "--db-accessor-port",
        default=None,
        type=int,
        help=(
            "Override database accessor port. Defaults to DATABASE_ACCESSOR_PORT or "
            "the local published port from config/.env.shared."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.error(f"Unsupported command: {args.command}")

    _configure_database_accessor_environment(
        host=args.db_accessor_host,
        port=args.db_accessor_port,
    )

    try:
        request = _build_request(args)
        result = _BACKTEST_RUNNER_MODULE.run_backtest_with_market_data(
            request=request,
            exchange=args.exchange,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_summary(result)
    return 0


def _build_request(args: argparse.Namespace) -> Any:
    strategy_parameters = {
        "fast_window": int(args.fast_window),
        "slow_window": int(args.slow_window),
        "quantity": float(args.quantity),
    }

    return _DOMAIN_TYPES_MODULE.BacktestRequest(
        symbols=[str(args.symbol)],
        timeframe=str(args.timeframe),
        start_ms=int(args.start_ms),
        end_ms=int(args.end_ms),
        strategy=_DOMAIN_TYPES_MODULE.StrategyConfig(
            strategy_id=str(args.strategy),
            parameters=strategy_parameters,
        ),
        execution=_APP_CONFIG_MODULE.build_default_execution_config(),
        initial_capital=float(args.initial_capital),
        engine=_DOMAIN_ENUMS_MODULE.BacktestEngine(str(args.engine)),
    )


def _print_summary(result: Any) -> None:
    final_equity = (
        float(result.equity_curve[-1].equity)
        if result.equity_curve
        else float(result.request.initial_capital)
    )
    total_return_pct = float(result.metrics.get("total_return_pct", 0.0))
    max_drawdown_pct = float(result.metrics.get("max_drawdown_pct", 0.0))
    trade_count = int(result.metrics.get("trade_count", float(len(result.trades))))

    print("Backtest completed")
    print(f"strategy={result.request.strategy.strategy_id}")
    print(f"engine={result.request.engine.value}")
    print(f"symbol={result.request.symbols[0]} timeframe={result.request.timeframe}")
    print(f"bars={int(result.diagnostics.get('bars', len(result.equity_curve)))}")
    print(f"fills={len(result.fills)} trades={trade_count}")
    print(f"total_return_pct={total_return_pct:.6f}")
    print(f"max_drawdown_pct={max_drawdown_pct:.6f}")
    print(f"final_equity={final_equity:.6f}")


def _configure_database_accessor_environment(*, host: str | None, port: int | None) -> None:
    local_defaults = _resolve_local_database_accessor_defaults()

    resolved_host = host or os.getenv("DATABASE_ACCESSOR_HOST") or local_defaults["host"]
    resolved_port = (
        str(port)
        if port is not None
        else os.getenv("DATABASE_ACCESSOR_PORT") or local_defaults["port"]
    )

    os.environ["DATABASE_ACCESSOR_HOST"] = resolved_host
    os.environ["DATABASE_ACCESSOR_PORT"] = resolved_port


def _resolve_local_database_accessor_defaults() -> dict[str, str]:
    env_values = _read_local_env_file()
    host = env_values.get("PUBLIC_HOST") or _DEFAULT_LOCAL_DB_ACCESSOR_HOST
    port = (
        env_values.get("DATABASE_ACCESSOR_PUBLISHED_PORT")
        or env_values.get("DATABASE_ACCESSOR_PORT")
        or _DEFAULT_LOCAL_DB_ACCESSOR_PORT
    )
    return {
        "host": host,
        "port": port,
    }


def _read_local_env_file() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env.shared"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


if __name__ == "__main__":
    raise SystemExit(main())
