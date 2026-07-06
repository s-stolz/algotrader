"""Local backtester CLI entrypoint."""

from __future__ import annotations

import argparse
import importlib
import math
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

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
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOPOLOGY_PATH = _REPO_ROOT / "config" / "topology.yaml"
_SHARED_ENV_PATH = _REPO_ROOT / "config" / ".env.shared"


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
    run_parser.add_argument(
        "--allowed-directions",
        default=_DOMAIN_ENUMS_MODULE.AllowedDirections.LONG_AND_SHORT.value,
        choices=tuple(direction.value for direction in _DOMAIN_ENUMS_MODULE.AllowedDirections),
        help="Allowed trade directions for strategy targets.",
    )
    run_parser.add_argument("--fast-window", default=5, type=int)
    run_parser.add_argument("--slow-window", default=20, type=int)
    run_parser.add_argument("--quantity", default=1.0, type=float)
    run_parser.add_argument("--stop-loss-pct", default=None, type=_stop_loss_pct_arg)
    run_parser.add_argument("--take-profit-pct", default=None, type=_take_profit_pct_arg)
    run_parser.add_argument(
        "--intrabar-exit-policy",
        "--intrabar-policy",
        dest="intrabar_exit_policy",
        default=_APP_CONFIG_MODULE.build_default_execution_config().intrabar_exit_policy.value,
        choices=tuple(policy.value for policy in _DOMAIN_ENUMS_MODULE.IntrabarExitPolicy),
        help="Policy for ambiguous bars where stop loss and take profit are both touched.",
    )
    run_parser.add_argument("--initial-capital", default=10_000.0, type=float)
    run_parser.add_argument("--exchange", default=None)
    run_parser.add_argument(
        "--persist-result",
        action="store_true",
        help="Persist the completed successful backtest through database-accessor-api.",
    )
    run_parser.add_argument(
        "--db-accessor-host",
        default=None,
        help=(
            "Override database accessor host. Defaults to public.host from " "config/topology.yaml."
        ),
    )
    run_parser.add_argument(
        "--db-accessor-port",
        default=None,
        type=int,
        help=(
            "Override database accessor port. Defaults to "
            "services.database_accessor_api.published_port from config/topology.yaml."
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
        )
    except Exception as exc:
        print(f"Error: {_format_cli_error(exc)}", file=sys.stderr)
        return 1

    _print_summary(result)
    return 0


def _build_request(args: argparse.Namespace) -> Any:
    strategy_parameters = {
        "fast_window": int(args.fast_window),
        "slow_window": int(args.slow_window),
        "quantity": float(args.quantity),
    }
    if args.stop_loss_pct is not None:
        strategy_parameters["stop_loss_pct"] = float(args.stop_loss_pct)
    if args.take_profit_pct is not None:
        strategy_parameters["take_profit_pct"] = float(args.take_profit_pct)

    execution = replace(
        _APP_CONFIG_MODULE.build_default_execution_config(),
        allowed_directions=_DOMAIN_ENUMS_MODULE.AllowedDirections(str(args.allowed_directions)),
        intrabar_exit_policy=_DOMAIN_ENUMS_MODULE.IntrabarExitPolicy(
            str(args.intrabar_exit_policy)
        ),
    )

    return _DOMAIN_TYPES_MODULE.BacktestRequest(
        symbols=[str(args.symbol)],
        timeframe=str(args.timeframe),
        start_ms=int(args.start_ms),
        end_ms=int(args.end_ms),
        strategy=_DOMAIN_TYPES_MODULE.StrategyConfig(
            strategy_id=str(args.strategy),
            parameters=strategy_parameters,
        ),
        execution=execution,
        initial_capital=float(args.initial_capital),
        exchange=str(args.exchange) if args.exchange is not None else None,
        persist_result=bool(args.persist_result),
        engine=_DOMAIN_ENUMS_MODULE.BacktestEngine(str(args.engine)),
    )


def _stop_loss_pct_arg(value: str) -> float:
    parsed = _finite_float_arg(value)
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    if parsed >= 100.0:
        raise argparse.ArgumentTypeError("must be less than 100")
    return parsed


def _take_profit_pct_arg(value: str) -> float:
    parsed = _finite_float_arg(value)
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _finite_float_arg(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


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
    if result.backtest_run_id is not None:
        print(f"backtest_run_id={result.backtest_run_id}")
    if result.persisted_at is not None:
        print(f"persisted_at_ms={result.persisted_at}")


def _format_cli_error(exc: Exception) -> str:
    message = str(exc)
    response_text = getattr(exc, "response_text", None)
    if response_text:
        return f"{message}: {response_text}"
    return message


def _configure_database_accessor_environment(*, host: str | None, port: int | None) -> None:
    local_defaults = _resolve_local_database_accessor_defaults()

    resolved_host = host or local_defaults["host"]
    resolved_port = str(port) if port is not None else local_defaults["port"]

    os.environ["DATABASE_ACCESSOR_HOST"] = resolved_host
    os.environ["DATABASE_ACCESSOR_PORT"] = resolved_port


def _resolve_local_database_accessor_defaults() -> dict[str, str]:
    topology_defaults = _resolve_topology_database_accessor_defaults()
    if topology_defaults is not None:
        return topology_defaults

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


def _resolve_topology_database_accessor_defaults() -> dict[str, str] | None:
    topology = _read_local_topology_file()
    if not topology:
        return None

    host = _lookup_topology_value(topology, ("public", "host")) or _DEFAULT_LOCAL_DB_ACCESSOR_HOST
    port = (
        _lookup_topology_value(
            topology,
            ("services", "database_accessor_api", "published_port"),
        )
        or _lookup_topology_value(topology, ("services", "database_accessor_api", "port"))
        or _DEFAULT_LOCAL_DB_ACCESSOR_PORT
    )
    return {
        "host": host,
        "port": port,
    }


def _read_local_topology_file() -> Mapping[str, Any]:
    if not _TOPOLOGY_PATH.exists():
        return {}

    try:
        import yaml
    except ModuleNotFoundError:
        return {}

    data = yaml.safe_load(_TOPOLOGY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        return {}
    return data


def _lookup_topology_value(topology: Mapping[str, Any], path: Sequence[str]) -> str | None:
    current: Any = topology
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]

    if current is None:
        return None
    return str(current)


def _read_local_env_file() -> dict[str, str]:
    if not _SHARED_ENV_PATH.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in _SHARED_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


if __name__ == "__main__":
    raise SystemExit(main())
