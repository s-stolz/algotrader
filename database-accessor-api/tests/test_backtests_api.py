import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("TIMESCALEDB_USER", "test")
os.environ.setdefault("TIMESCALEDB_PASSWORD", "test")
os.environ.setdefault("TIMESCALEDB_HOST", "localhost")
os.environ.setdefault("TIMESCALEDB_PORT", "5432")
os.environ.setdefault("TIMESCALEDB_DB", "test")

import main  # noqa: E402
from app.models import (  # noqa: E402
    backtest_closed_trades,
    backtest_fills,
    backtest_runs,
    metadata,
)
from app.schemas import (  # noqa: E402
    BacktestClosedTradeIn,
    BacktestFillIn,
    BacktestRequestPayload,
    BacktestRunCompleteIn,
    BacktestRunConditionalUpdateIn,
    BacktestRunCreateIn,
)


class InMemoryAsyncSession:
    def __init__(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()
        self.connection.execute(text("PRAGMA foreign_keys=ON"))

    async def execute(self, statement, params=None):
        return self.connection.execute(statement, params or {})

    async def commit(self):
        self.connection.commit()

    async def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()
        self.engine.dispose()


def _request_payload(**overrides):
    payload = {
        "symbols": ["EURUSD"],
        "exchange": "FX",
        "timeframe": "M15",
        "start_ms": 1714521600000,
        "end_ms": 1714608000000,
        "engine": "event_driven",
        "data_granularity": "bar",
        "initial_capital": 25000.0,
        "strategy": {
            "strategy_id": "sma_crossover",
            "parameters": {
                "fast_window": 5,
                "slow_window": 20,
                "quantity": 1000.0,
            },
        },
        "execution": {
            "signal_timing": "close",
            "fill_timing": "next_open",
            "price_source": "open",
            "allow_partial_fills": False,
            "allow_short": False,
            "trade_accounting_policy": "average_cost",
            "gap_policy": "error",
            "intrabar_exit_policy": "take_profit_first",
            "commission_bps": 1.5,
            "slippage_bps": 0.75,
        },
        "persist_result": False,
        "run_metadata": {
            "label": "queued-smoke",
            "tags": ["durable", "api"],
        },
    }
    payload.update(overrides)
    return payload


def _run_payload(**overrides):
    payload = {
        "run_id": "run-queued-1",
        "status": "queued",
        "submitted_at": datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "request_schema_version": 1,
        "request": _request_payload(),
        "result_schema_version": None,
        "metrics": None,
        "diagnostics": None,
        "fills": [],
        "trades": [],
    }
    payload.update(overrides)
    return payload


class BacktestRunApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = InMemoryAsyncSession()

    def tearDown(self):
        self.session.close()

    @property
    def db(self) -> AsyncSession:
        return cast(AsyncSession, self.session)

    async def test_create_queued_run_and_get_preserves_complete_request(self):
        created = await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        fetched = await main.get_backtest_run(created["run_id"], db=self.db)

        self.assertEqual(fetched["run_id"], "run-queued-1")
        self.assertEqual(fetched["status"], "queued")
        self.assertEqual(fetched["request_schema_version"], 1)
        self.assertEqual(fetched["request"], _request_payload())
        self.assertEqual(fetched["request"]["exchange"], "FX")
        self.assertEqual(
            fetched["request"]["strategy"]["parameters"],
            _request_payload()["strategy"]["parameters"],
        )
        self.assertEqual(
            fetched["request"]["execution"],
            _request_payload()["execution"],
        )
        self.assertEqual(
            fetched["request"]["run_metadata"],
            _request_payload()["run_metadata"],
        )
        self.assertIsNone(fetched["started_at"])
        self.assertIsNone(fetched["completed_at"])
        self.assertIsNone(fetched["result_schema_version"])
        self.assertIsNone(fetched["metrics"])
        self.assertIsNone(fetched["diagnostics"])
        self.assertNotIn("fills", fetched)
        self.assertNotIn("trades", fetched)

    async def test_create_queued_run_defaults_absent_terminal_fields(self):
        run = BacktestRunCreateIn(
            run_id="run-minimal-queued",
            status="queued",
            submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            request_schema_version=1,
            request=BacktestRequestPayload(**_request_payload()),
        )

        created = await main.create_backtest_run(run, db=self.db)

        self.assertIsNone(created["started_at"])
        self.assertIsNone(created["completed_at"])
        self.assertIsNone(created["error_code"])
        self.assertIsNone(created["error_message"])
        self.assertIsNone(created["result_schema_version"])
        self.assertIsNone(created["metrics"])
        self.assertIsNone(created["diagnostics"])
        self.assertEqual(run.fills, [])
        self.assertEqual(run.trades, [])

    async def test_get_missing_run_returns_404(self):
        with self.assertRaises(main.HTTPException) as ctx:
            await main.get_backtest_run("missing", db=self.db)

        self.assertEqual(ctx.exception.status_code, 404)

    async def test_list_filters_status_and_orders_newest_first(self):
        runs = (
            _run_payload(
                run_id="run-b",
                submitted_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
            ),
            _run_payload(
                run_id="run-newest",
                submitted_at=datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc),
            ),
            _run_payload(
                run_id="run-a",
                submitted_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
            ),
            _run_payload(
                run_id="run-failed",
                status="failed",
                submitted_at=datetime(2026, 6, 8, 12, 33, tzinfo=timezone.utc),
            ),
        )
        for run in runs:
            await main.create_backtest_run(BacktestRunCreateIn(**run), db=self.db)

        listed = await main.list_backtest_runs(status="queued", db=self.db)

        self.assertEqual(
            [run["run_id"] for run in listed],
            ["run-newest", "run-a", "run-b"],
        )

    async def test_list_filters_each_immutable_request_json_field(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-target",
                    request=_request_payload(
                        symbols=["GBPUSD", "EURUSD"],
                        timeframe="H1",
                        engine="vectorized",
                        strategy={
                            "strategy_id": "mean_reversion",
                            "parameters": {},
                        },
                    ),
                )
            ),
            db=self.db,
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-other",
                    request=_request_payload(
                        symbols=["USDJPY"],
                        timeframe="M15",
                        engine="event_driven",
                        strategy={
                            "strategy_id": "sma_crossover",
                            "parameters": {},
                        },
                    ),
                )
            ),
            db=self.db,
        )

        filters: tuple[dict[str, Any], ...] = (
            {"symbol": "EURUSD"},
            {"timeframe": "H1"},
            {"strategy": "mean_reversion"},
            {"engine": "vectorized"},
        )
        for query in filters:
            with self.subTest(query=query):
                listed = await main.list_backtest_runs(**query, db=self.db)
                self.assertEqual([run["run_id"] for run in listed], ["run-target"])

    async def test_list_submission_date_filters_include_boundary_timestamps(self):
        timestamps = (
            ("run-before", datetime(2026, 6, 8, 12, 29, tzinfo=timezone.utc)),
            ("run-from", datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc)),
            ("run-to", datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc)),
            ("run-after", datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc)),
        )
        for run_id, submitted_at in timestamps:
            await main.create_backtest_run(
                BacktestRunCreateIn(
                    **_run_payload(
                        run_id=run_id,
                        submitted_at=submitted_at,
                    )
                ),
                db=self.db,
            )

        listed = await main.list_backtest_runs(
            submitted_from=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            submitted_to=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
            db=self.db,
        )

        self.assertEqual(
            [run["run_id"] for run in listed],
            ["run-to", "run-from"],
        )

    async def test_list_combines_lifecycle_request_and_date_filters(self):
        matching_request = _request_payload(
            symbols=["GBPUSD", "EURUSD"],
            timeframe="H1",
            engine="vectorized",
            strategy={"strategy_id": "mean_reversion", "parameters": {}},
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-target",
                    status="running",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-wrong-status",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-wrong-request",
                    status="running",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

        listed = await main.list_backtest_runs(
            status="running",
            symbol="EURUSD",
            timeframe="H1",
            strategy="mean_reversion",
            engine="vectorized",
            submitted_from=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            submitted_to=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            db=self.db,
        )

        self.assertEqual([run["run_id"] for run in listed], ["run-target"])

    async def test_list_returns_empty_collection_when_no_runs_match(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        listed = await main.list_backtest_runs(symbol="USDJPY", db=self.db)

        self.assertEqual(listed, [])

    async def test_list_returns_all_matching_runs_without_a_hard_limit(self):
        for index in range(105):
            await main.create_backtest_run(
                BacktestRunCreateIn(
                    **_run_payload(
                        run_id=f"run-{index:03d}",
                        submitted_at=datetime(
                            2026,
                            6,
                            8,
                            12,
                            index // 60,
                            index % 60,
                            tzinfo=timezone.utc,
                        ),
                    )
                ),
                db=self.db,
            )

        listed = await main.list_backtest_runs(status="queued", db=self.db)

        self.assertEqual(len(listed), 105)
        self.assertEqual(listed[0]["run_id"], "run-104")
        self.assertEqual(listed[-1]["run_id"], "run-000")

    async def test_conditional_update_changes_fields_only_for_expected_status(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )
        started_at = datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc)

        updated = await main.conditional_update_backtest_run(
            "run-queued-1",
            BacktestRunConditionalUpdateIn(
                expected_status="queued",
                new_status="running",
                started_at=started_at,
            ),
            db=self.db,
        )
        stale_update = await main.conditional_update_backtest_run(
            "run-queued-1",
            BacktestRunConditionalUpdateIn(
                expected_status="queued",
                new_status="failed",
                completed_at=datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc),
                error_code="stale_claim",
                error_message="must not be stored",
            ),
            db=self.db,
        )
        fetched = await main.get_backtest_run("run-queued-1", db=self.db)

        self.assertEqual(updated, {"updated": True})
        self.assertEqual(stale_update, {"updated": False})
        self.assertEqual(fetched["status"], "running")
        self.assertEqual(
            fetched["started_at"].replace(tzinfo=timezone.utc),
            started_at,
        )
        self.assertIsNone(fetched["completed_at"])
        self.assertIsNone(fetched["error_code"])
        self.assertIsNone(fetched["error_message"])

    async def test_competing_claims_have_exactly_one_winner(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        claims = [
            await main.conditional_update_backtest_run(
                "run-queued-1",
                BacktestRunConditionalUpdateIn(
                    expected_status="queued",
                    new_status="running",
                    started_at=datetime(
                        2026,
                        6,
                        8,
                        12,
                        31 + offset,
                        tzinfo=timezone.utc,
                    ),
                ),
                db=self.db,
            )
            for offset in range(2)
        ]

        self.assertEqual(claims.count({"updated": True}), 1)
        self.assertEqual(claims.count({"updated": False}), 1)

    async def test_successful_completion_stores_all_artifacts_atomically(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    status="running",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )
        completed_at = datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc)

        completed = await main.complete_backtest_run(
            "run-queued-1",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=completed_at,
                result_schema_version=2,
                metrics={"total_return_pct": 1.25},
                diagnostics={"execution_duration_ms": 240000},
                fills=[
                    BacktestFillIn(
                        fill_sequence=0,
                        timestamp_ms=1714525200000,
                        symbol="EURUSD",
                        side="buy",
                        quantity=1000.0,
                        price=1.0715,
                        fees=0.15,
                        exit_reason=None,
                    ),
                    BacktestFillIn(
                        fill_sequence=1,
                        timestamp_ms=1714532400000,
                        symbol="EURUSD",
                        side="sell",
                        quantity=1000.0,
                        price=1.074,
                        fees=0.15,
                        exit_reason="stop_loss",
                    ),
                ],
                trades=[
                    BacktestClosedTradeIn(
                        trade_sequence=0,
                        trade_id="trade-1",
                        symbol="EURUSD",
                        quantity=1000.0,
                        entry_timestamp_ms=1714525200000,
                        entry_price=1.0715,
                        exit_timestamp_ms=1714532400000,
                        exit_price=1.074,
                        realized_pnl=2.5,
                        fees=0.3,
                        exit_reason="stop_loss",
                        stop_loss_price=1.069,
                        take_profit_price=1.081,
                    )
                ],
            ),
            db=self.db,
        )
        fetched = await main.get_backtest_run("run-queued-1", db=self.db)
        fill_result = await self.session.execute(
            select(backtest_fills).order_by(backtest_fills.c.fill_sequence)
        )
        trade_result = await self.session.execute(select(backtest_closed_trades))
        fills = [dict(row._mapping) for row in fill_result.fetchall()]
        trades = [dict(row._mapping) for row in trade_result.fetchall()]

        self.assertEqual(completed, {"updated": True})
        self.assertEqual(fetched["status"], "succeeded")
        self.assertEqual(
            fetched["completed_at"].replace(tzinfo=timezone.utc),
            completed_at,
        )
        self.assertEqual(fetched["result_schema_version"], 2)
        self.assertEqual(fetched["metrics"], {"total_return_pct": 1.25})
        self.assertEqual(
            fetched["diagnostics"],
            {"execution_duration_ms": 240000},
        )
        self.assertEqual([fill["fill_sequence"] for fill in fills], [0, 1])
        self.assertEqual(
            fills[1],
            {
                "run_id": "run-queued-1",
                "fill_sequence": 1,
                "timestamp_ms": 1714532400000,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1000.0,
                "price": 1.074,
                "fees": 0.15,
                "exit_reason": "stop_loss",
            },
        )
        self.assertEqual(
            trades[0],
            {
                "run_id": "run-queued-1",
                "trade_sequence": 0,
                "trade_id": "trade-1",
                "symbol": "EURUSD",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714525200000,
                "entry_price": 1.0715,
                "exit_timestamp_ms": 1714532400000,
                "exit_price": 1.074,
                "realized_pnl": 2.5,
                "fees": 0.3,
                "exit_reason": "stop_loss",
                "stop_loss_price": 1.069,
                "take_profit_price": 1.081,
            },
        )

    async def test_successful_completion_preserves_closed_trade_protective_prices(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    status="running",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

        completed = await main.complete_backtest_run(
            "run-queued-1",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=2,
                metrics={"trade_count": 2},
                diagnostics={"bars": 120},
                trades=[
                    BacktestClosedTradeIn(
                        trade_sequence=0,
                        trade_id="trade-no-protection",
                        symbol="EURUSD",
                        quantity=1000.0,
                        entry_timestamp_ms=1714525200000,
                        entry_price=1.0715,
                        exit_timestamp_ms=1714528800000,
                        exit_price=1.073,
                        realized_pnl=1.5,
                        fees=0.3,
                        exit_reason="signal",
                        stop_loss_price=None,
                        take_profit_price=None,
                    ),
                    BacktestClosedTradeIn(
                        trade_sequence=1,
                        trade_id="trade-configured-protection",
                        symbol="EURUSD",
                        quantity=1000.0,
                        entry_timestamp_ms=1714529400000,
                        entry_price=1.076,
                        exit_timestamp_ms=1714532400000,
                        exit_price=1.074,
                        realized_pnl=-2.0,
                        fees=0.3,
                        exit_reason="signal",
                        stop_loss_price=1.069,
                        take_profit_price=1.081,
                    ),
                ],
            ),
            db=self.db,
        )
        fetched_run = await main.get_backtest_run("run-queued-1", db=self.db)
        fetched_trades = await main.get_backtest_trades("run-queued-1", db=self.db)

        self.assertEqual(completed, {"updated": True})
        self.assertEqual(fetched_run["result_schema_version"], 2)
        self.assertEqual(
            [(trade["stop_loss_price"], trade["take_profit_price"]) for trade in fetched_trades],
            [(None, None), (1.069, 1.081)],
        )

    async def test_completion_does_not_store_artifacts_for_stale_status(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        completed = await main.complete_backtest_run(
            "run-queued-1",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=1,
                metrics={"total_return_pct": 1.25},
                diagnostics={"bars": 25},
                fills=[
                    BacktestFillIn(
                        fill_sequence=0,
                        timestamp_ms=1714525200000,
                        symbol="EURUSD",
                        side="buy",
                        quantity=1000.0,
                        price=1.0715,
                        fees=0.15,
                    )
                ],
                trades=[],
            ),
            db=self.db,
        )
        fetched = await main.get_backtest_run("run-queued-1", db=self.db)
        fill_result = await self.session.execute(select(backtest_fills))

        self.assertEqual(completed, {"updated": False})
        self.assertEqual(fetched["status"], "queued")
        self.assertIsNone(fetched["completed_at"])
        self.assertIsNone(fetched["metrics"])
        self.assertEqual(fill_result.fetchall(), [])

    async def test_completion_accepts_empty_artifact_collections(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    status="running",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

        completed = await main.complete_backtest_run(
            "run-queued-1",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=1,
                metrics={"trade_count": 0},
                diagnostics={"bars": 0},
                fills=[],
                trades=[],
            ),
            db=self.db,
        )
        fill_result = await self.session.execute(select(backtest_fills))
        trade_result = await self.session.execute(select(backtest_closed_trades))

        self.assertEqual(completed, {"updated": True})
        self.assertEqual(fill_result.fetchall(), [])
        self.assertEqual(trade_result.fetchall(), [])

    async def test_artifact_insert_failure_rolls_back_completion(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    status="running",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )
        fill = BacktestFillIn(
            fill_sequence=0,
            timestamp_ms=1714525200000,
            symbol="EURUSD",
            side="buy",
            quantity=1000.0,
            price=1.0715,
            fees=0.15,
            exit_reason=None,
        )
        duplicate_trade = BacktestClosedTradeIn(
            trade_sequence=0,
            trade_id="trade-1",
            symbol="EURUSD",
            quantity=1000.0,
            entry_timestamp_ms=1714525200000,
            entry_price=1.0715,
            exit_timestamp_ms=1714532400000,
            exit_price=1.074,
            realized_pnl=2.5,
            fees=0.3,
            exit_reason="signal",
        )

        with self.assertRaises(IntegrityError):
            await main.complete_backtest_run(
                "run-queued-1",
                BacktestRunCompleteIn(
                    expected_status="running",
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=1,
                    metrics={"total_return_pct": 1.25},
                    diagnostics={"execution_duration_ms": 240000},
                    fills=[fill],
                    trades=[duplicate_trade, duplicate_trade],
                ),
                db=self.db,
            )

        fetched = await main.get_backtest_run("run-queued-1", db=self.db)
        fill_result = await self.session.execute(select(backtest_fills))
        trade_result = await self.session.execute(select(backtest_closed_trades))

        self.assertEqual(fetched["status"], "running")
        self.assertIsNone(fetched["completed_at"])
        self.assertIsNone(fetched["result_schema_version"])
        self.assertIsNone(fetched["metrics"])
        self.assertIsNone(fetched["diagnostics"])
        self.assertEqual(fill_result.fetchall(), [])
        self.assertEqual(trade_result.fetchall(), [])

    async def test_create_succeeded_run_stores_normalized_fills_and_trades(self):
        completed_at = datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc)
        run = BacktestRunCreateIn(
            **_run_payload(
                run_id="run-succeeded-1",
                status="succeeded",
                started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                completed_at=completed_at,
                result_schema_version=2,
                metrics={"total_return_pct": 1.25},
                diagnostics={"execution_duration_ms": 240000},
                fills=[
                    {
                        "fill_sequence": 0,
                        "timestamp_ms": 1714525200000,
                        "symbol": "EURUSD",
                        "side": "buy",
                        "quantity": 1000.0,
                        "price": 1.0715,
                        "fees": 0.15,
                        "exit_reason": None,
                    }
                ],
                trades=[
                    {
                        "trade_sequence": 0,
                        "trade_id": "trade-1",
                        "symbol": "EURUSD",
                        "quantity": 1000.0,
                        "entry_timestamp_ms": 1714525200000,
                        "entry_price": 1.0715,
                        "exit_timestamp_ms": 1714532400000,
                        "exit_price": 1.074,
                        "realized_pnl": 2.5,
                        "fees": 0.3,
                        "exit_reason": "signal",
                        "stop_loss_price": 1.068,
                        "take_profit_price": None,
                    }
                ],
            )
        )

        created = await main.create_backtest_run(run, db=self.db)
        fill_result = await self.session.execute(select(backtest_fills))
        trade_result = await self.session.execute(select(backtest_closed_trades))
        fill_row = fill_result.fetchone()
        trade_row = trade_result.fetchone()
        if fill_row is None or trade_row is None:
            self.fail("Expected persisted fill and trade rows")
        fill = dict(fill_row._mapping)
        trade = dict(trade_row._mapping)

        self.assertEqual(created["status"], "succeeded")
        self.assertEqual(created["result_schema_version"], 2)
        self.assertEqual(fill["run_id"], "run-succeeded-1")
        self.assertEqual(fill["fill_sequence"], 0)
        self.assertEqual(fill["side"], "buy")
        self.assertEqual(trade["run_id"], "run-succeeded-1")
        self.assertEqual(trade["trade_sequence"], 0)
        self.assertEqual(trade["exit_reason"], "signal")
        self.assertEqual(trade["stop_loss_price"], 1.068)
        self.assertIsNone(trade["take_profit_price"])

    async def test_get_execution_logs_orders_by_sequence_and_preserves_exit_reasons(self):
        fills = [
            {
                "fill_sequence": 3,
                "timestamp_ms": 1714536000000,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1000.0,
                "price": 1.075,
                "fees": 0.15,
                "exit_reason": "take_profit",
            },
            {
                "fill_sequence": 0,
                "timestamp_ms": 1714525200000,
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 1000.0,
                "price": 1.0715,
                "fees": 0.15,
                "exit_reason": None,
            },
            {
                "fill_sequence": 2,
                "timestamp_ms": 1714532400000,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1000.0,
                "price": 1.074,
                "fees": 0.15,
                "exit_reason": "stop_loss",
            },
            {
                "fill_sequence": 1,
                "timestamp_ms": 1714528800000,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1000.0,
                "price": 1.073,
                "fees": 0.15,
                "exit_reason": "signal",
            },
        ]
        trades = [
            {
                "trade_sequence": 2,
                "trade_id": "trade-take-profit",
                "symbol": "EURUSD",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714533000000,
                "entry_price": 1.072,
                "exit_timestamp_ms": 1714536000000,
                "exit_price": 1.075,
                "realized_pnl": 3.0,
                "fees": 0.3,
                "exit_reason": "take_profit",
                "stop_loss_price": 1.068,
                "take_profit_price": 1.08,
            },
            {
                "trade_sequence": 0,
                "trade_id": "trade-signal",
                "symbol": "EURUSD",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714525200000,
                "entry_price": 1.0715,
                "exit_timestamp_ms": 1714528800000,
                "exit_price": 1.073,
                "realized_pnl": 1.5,
                "fees": 0.3,
                "exit_reason": "signal",
                "stop_loss_price": None,
                "take_profit_price": None,
            },
            {
                "trade_sequence": 1,
                "trade_id": "trade-stop-loss",
                "symbol": "EURUSD",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714529400000,
                "entry_price": 1.076,
                "exit_timestamp_ms": 1714532400000,
                "exit_price": 1.074,
                "realized_pnl": -2.0,
                "fees": 0.3,
                "exit_reason": "stop_loss",
                "stop_loss_price": 1.069,
                "take_profit_price": None,
            },
        ]
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-succeeded-logs",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=1,
                    metrics={"trade_count": 3},
                    diagnostics={"bars": 100},
                    fills=fills,
                    trades=trades,
                )
            ),
            db=self.db,
        )

        fetched_fills = await main.get_backtest_fills("run-succeeded-logs", db=self.db)
        fetched_trades = await main.get_backtest_trades("run-succeeded-logs", db=self.db)

        self.assertEqual(
            [fill["fill_sequence"] for fill in fetched_fills],
            [0, 1, 2, 3],
        )
        self.assertEqual(
            [fill["exit_reason"] for fill in fetched_fills],
            [None, "signal", "stop_loss", "take_profit"],
        )
        self.assertEqual(
            [trade["trade_sequence"] for trade in fetched_trades],
            [0, 1, 2],
        )
        self.assertEqual(
            [trade["exit_reason"] for trade in fetched_trades],
            ["signal", "stop_loss", "take_profit"],
        )
        self.assertEqual(fetched_trades[0]["realized_pnl"], 1.5)
        self.assertEqual(fetched_trades[0]["fees"], 0.3)
        self.assertIsNone(fetched_trades[0]["stop_loss_price"])
        self.assertIsNone(fetched_trades[0]["take_profit_price"])
        self.assertEqual(fetched_trades[1]["stop_loss_price"], 1.069)
        self.assertIsNone(fetched_trades[1]["take_profit_price"])
        self.assertEqual(fetched_trades[2]["stop_loss_price"], 1.068)
        self.assertEqual(fetched_trades[2]["take_profit_price"], 1.08)

    async def test_get_execution_logs_returns_empty_collections_and_missing_is_not_found(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-empty",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=1,
                    metrics={"trade_count": 0},
                    diagnostics={"bars": 0},
                )
            ),
            db=self.db,
        )

        self.assertEqual(await main.get_backtest_fills("run-empty", db=self.db), [])
        self.assertEqual(await main.get_backtest_trades("run-empty", db=self.db), [])

        for getter in (main.get_backtest_fills, main.get_backtest_trades):
            with self.subTest(getter=getter.__name__):
                with self.assertRaises(main.HTTPException) as ctx:
                    await getter("run-missing", db=self.db)
                self.assertEqual(ctx.exception.status_code, 404)

    async def test_delete_backtest_run_cascades_execution_logs(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-delete",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=1,
                    metrics={"trade_count": 1},
                    diagnostics={"bars": 10},
                    fills=[
                        {
                            "fill_sequence": 0,
                            "timestamp_ms": 1714525200000,
                            "symbol": "EURUSD",
                            "side": "buy",
                            "quantity": 1000.0,
                            "price": 1.0715,
                            "fees": 0.15,
                            "exit_reason": None,
                        }
                    ],
                    trades=[
                        {
                            "trade_sequence": 0,
                            "trade_id": "trade-delete",
                            "symbol": "EURUSD",
                            "quantity": 1000.0,
                            "entry_timestamp_ms": 1714525200000,
                            "entry_price": 1.0715,
                            "exit_timestamp_ms": 1714532400000,
                            "exit_price": 1.074,
                            "realized_pnl": 2.5,
                            "fees": 0.3,
                            "exit_reason": "signal",
                            "stop_loss_price": None,
                            "take_profit_price": None,
                        }
                    ],
                )
            ),
            db=self.db,
        )

        response = await main.delete_backtest_run("run-delete", db=self.db)
        run_result = await self.session.execute(select(backtest_runs))
        fill_result = await self.session.execute(select(backtest_fills))
        trade_result = await self.session.execute(select(backtest_closed_trades))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(run_result.fetchall(), [])
        self.assertEqual(fill_result.fetchall(), [])
        self.assertEqual(trade_result.fetchall(), [])

        with self.assertRaises(main.HTTPException) as ctx:
            await main.delete_backtest_run("run-delete", db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_rejects_unknown_request_schema_version(self):
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request_schema_version=2))

    def test_result_schema_version_supports_v1_and_v2_only(self):
        BacktestRunCreateIn(**_run_payload(result_schema_version=1))
        BacktestRunCreateIn(**_run_payload(result_schema_version=2))

        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(result_schema_version=3))

        with self.assertRaises(ValidationError):
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=3,
                metrics={},
                diagnostics={},
            )

    def test_create_rejects_incomplete_request_snapshot(self):
        request = _request_payload()
        request.pop("exchange")

        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request=request))

    def test_create_rejects_invalid_request_enums_and_unknown_fields(self):
        invalid_execution = _request_payload()
        invalid_execution["execution"] = {
            **invalid_execution["execution"],
            "gap_policy": "invented",
        }
        unknown_field = _request_payload(extra_default="must-not-be-reconstructed")

        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request=invalid_execution))
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request=unknown_field))

    def test_schema_uses_lifecycle_columns_and_json_request_only(self):
        self.assertEqual(
            set(backtest_runs.c.keys()),
            {
                "run_id",
                "status",
                "submitted_at",
                "started_at",
                "completed_at",
                "error_code",
                "error_message",
                "request_schema_version",
                "request",
                "result_schema_version",
                "metrics",
                "diagnostics",
            },
        )
        self.assertNotIn("symbol", backtest_runs.c)
        self.assertNotIn("timeframe", backtest_runs.c)
        self.assertNotIn("strategy_id", backtest_runs.c)
        self.assertNotIn("engine", backtest_runs.c)
        self.assertEqual(
            set(backtest_fills.c.keys()),
            {
                "run_id",
                "fill_sequence",
                "timestamp_ms",
                "symbol",
                "side",
                "quantity",
                "price",
                "fees",
                "exit_reason",
            },
        )
        self.assertEqual(
            set(backtest_closed_trades.c.keys()),
            {
                "run_id",
                "trade_sequence",
                "trade_id",
                "symbol",
                "quantity",
                "entry_timestamp_ms",
                "entry_price",
                "exit_timestamp_ms",
                "exit_price",
                "realized_pnl",
                "fees",
                "exit_reason",
                "stop_loss_price",
                "take_profit_price",
            },
        )

    def test_initial_schema_includes_durable_backtest_tables(self):
        schema_path = Path(__file__).resolve().parents[2] / "timescaledb-init" / "01-init.sql"
        sql = schema_path.read_text(encoding="utf-8").lower()

        self.assertIn("create table if not exists backtest_runs", sql)
        self.assertIn("create table if not exists backtest_fills", sql)
        self.assertIn("create table if not exists backtest_closed_trades", sql)
        self.assertIn("stop_loss_price double precision", sql)
        self.assertIn("take_profit_price double precision", sql)
        self.assertIn("add column if not exists stop_loss_price", sql)
        self.assertIn("add column if not exists take_profit_price", sql)
        self.assertIn("request jsonb not null", sql)
        self.assertIn("metrics jsonb", sql)
        self.assertIn("diagnostics jsonb", sql)
        self.assertNotIn("drop table", sql)

    def test_backtest_result_schema_v2_migration_adds_protective_prices(self):
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "timescaledb-init"
            / "05-backtest-result-schema-v2.sql"
        )
        sql = migration_path.read_text(encoding="utf-8").lower()

        self.assertIn("alter table if exists backtest_closed_trades", sql)
        self.assertIn("add column if not exists stop_loss_price", sql)
        self.assertIn("add column if not exists take_profit_price", sql)
        self.assertNotIn("drop table", sql)


if __name__ == "__main__":
    unittest.main()
