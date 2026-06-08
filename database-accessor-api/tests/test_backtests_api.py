import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from pydantic import ValidationError
from sqlalchemy import create_engine, select
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
                result_schema_version=1,
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
        self.assertEqual(fetched["result_schema_version"], 1)
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
            },
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
                result_schema_version=1,
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
        self.assertEqual(created["result_schema_version"], 1)
        self.assertEqual(fill["run_id"], "run-succeeded-1")
        self.assertEqual(fill["fill_sequence"], 0)
        self.assertEqual(fill["side"], "buy")
        self.assertEqual(trade["run_id"], "run-succeeded-1")
        self.assertEqual(trade["trade_sequence"], 0)
        self.assertEqual(trade["exit_reason"], "signal")

    def test_create_rejects_unknown_request_schema_version(self):
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request_schema_version=2))

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
            },
        )

    def test_sql_reset_is_scoped_to_backtest_tables(self):
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "timescaledb-init"
            / "05-init-backtest-persistence.sql"
        )
        sql = migration_path.read_text(encoding="utf-8").lower()

        self.assertIn("drop table if exists backtest_run_summaries", sql)
        self.assertIn("create table backtest_runs", sql)
        self.assertIn("request jsonb not null", sql)
        self.assertIn("metrics jsonb", sql)
        self.assertIn("diagnostics jsonb", sql)
        self.assertNotIn("drop table if exists markets", sql)
        self.assertNotIn("drop table if exists candles", sql)


if __name__ == "__main__":
    unittest.main()
