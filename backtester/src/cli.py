"""Minimal CLI entrypoint for one-run bar backtests."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from app.backtest_runner import run_backtest_with_market_data
from app.config import build_default_execution_config
from domain.types import BacktestRequest, BacktestResult, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backtester",
        description="Run vectorized bar backtests.",
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
    run_parser.add_argument("--fast-window", default=5, type=int)
    run_parser.add_argument("--slow-window", default=20, type=int)
    run_parser.add_argument("--quantity", default=1.0, type=float)
    run_parser.add_argument("--initial-capital", default=10_000.0, type=float)
    run_parser.add_argument("--exchange", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.error(f"Unsupported command: {args.command}")

    try:
        strategy = _build_strategy(args)
        request = _build_request(args)
        result = run_backtest_with_market_data(
            request=request,
            strategy=strategy,
            exchange=args.exchange,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_summary(result)
    return 0


def _build_strategy(args: argparse.Namespace):
    if args.strategy != "sma_crossover":
        raise ValueError(f"Unsupported strategy: {args.strategy}")

    return build_sma_crossover_strategy(
        fast_window=int(args.fast_window),
        slow_window=int(args.slow_window),
        quantity=float(args.quantity),
    )


def _build_request(args: argparse.Namespace) -> BacktestRequest:
    strategy_parameters = {
        "fast_window": int(args.fast_window),
        "slow_window": int(args.slow_window),
        "quantity": float(args.quantity),
    }

    return BacktestRequest(
        symbols=[str(args.symbol)],
        timeframe=str(args.timeframe),
        start_ms=int(args.start_ms),
        end_ms=int(args.end_ms),
        strategy=StrategyConfig(
            strategy_id=str(args.strategy),
            parameters=strategy_parameters,
        ),
        execution=build_default_execution_config(),
        initial_capital=float(args.initial_capital),
    )


def _print_summary(result: BacktestResult) -> None:
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
    print(f"symbol={result.request.symbols[0]} timeframe={result.request.timeframe}")
    print(f"bars={int(result.diagnostics.get('bars', len(result.equity_curve)))}")
    print(f"fills={len(result.fills)} trades={trade_count}")
    print(f"total_return_pct={total_return_pct:.6f}")
    print(f"max_drawdown_pct={max_drawdown_pct:.6f}")
    print(f"final_equity={final_equity:.6f}")


if __name__ == "__main__":
    raise SystemExit(main())
