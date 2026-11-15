"""Execution-log pagination against PostgreSQL in a disposable schema."""

import os
import unittest

import test_backtests_postgres as fixtures
from app import crud
from app.backtest_execution_log import get_execution_log
from app.models import backtest_closed_trades, backtest_runs
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@unittest.skipUnless(os.getenv("BACKTEST_TEST_DATABASE_URL"), "requires local PostgreSQL")
class ExecutionLogPostgresTests(unittest.IsolatedAsyncioTestCase):
    sessions: async_sessionmaker[AsyncSession]
    asyncSetUp = fixtures.BacktestPostgresTests.asyncSetUp
    asyncTearDown = fixtures.BacktestPostgresTests.asyncTearDown
    _payload = fixtures.BacktestPostgresTests._payload

    async def test_execution_log_combines_pages_without_duplicates(self):
        async with self.sessions() as session:
            await crud.create_backtest(session, self._payload("log", "run"))
            events = [
                dict(
                    order_id="cancelled",
                    outcome="submit",
                    timestamp_ms=1,
                    side="sell",
                    limit_price=99,
                    quantity=2,
                ),
                dict(order_id="cancelled", outcome="cancel", timestamp_ms=250, limit_price=None),
                dict(order_id="filled", outcome="filled", timestamp_ms=2),
                dict(order_id="filled", outcome="cancel", timestamp_ms=500),
                dict(order_id="partial-reversal", outcome="submit", timestamp_ms=1, quantity=11),
                dict(order_id="partial-reversal", outcome="filled", timestamp_ms=500, quantity=1),
                dict(order_id="partial-reversal", outcome="insufficient_margin", timestamp_ms=500),
                dict(order_id="legacy", outcome="expired", timestamp_ms=250),
                dict(order_id="legacy", outcome="cancel", timestamp_ms=260),
                dict(order_id="unknown", outcome="future_outcome", timestamp_ms=600),
                dict(order_id="bad-time", outcome="cancel", timestamp_ms="bad"),
            ]
            await session.execute(
                update(backtest_runs)
                .where(backtest_runs.c.run_id == "run")
                .values(
                    status="succeeded",
                    result_schema_version=3,
                    diagnostics={"order_events": events},
                )
            )
            for seq in range(1, 24):
                await session.execute(
                    insert(backtest_closed_trades).values(
                        run_id="run",
                        trade_sequence=seq,
                        trade_id=f"trade-{seq}",
                        symbol="EURUSD",
                        trade_direction="long",
                        quantity=1,
                        entry_timestamp_ms=1,
                        entry_price=100,
                        exit_timestamp_ms=250 if seq == 23 else seq * 10,
                        exit_price=101,
                        realized_pnl=1,
                        fees=0.1,
                        exit_reason="signal",
                    )
                )
            await session.commit()
            pages = [
                await get_execution_log(
                    session, "run", page=p, page_size=10, include_unexecuted=True
                )
                for p in range(1, 5)
            ]
            assert all(page is not None for page in pages)
            rows = [row for page in pages if page for row in page["items"]]
            self.assertEqual([page["total"] for page in pages if page], [25] * 4)
            self.assertEqual([len(page["items"]) for page in pages if page], [10, 10, 5, 0])
            self.assertEqual(rows[0]["order"]["order_id"], "legacy")
            self.assertIsNone(rows[0]["order"]["side"])
            self.assertEqual(rows[1]["trade"]["sequence"], 23)
            self.assertEqual(rows[2]["order"]["side"], "sell")
            self.assertIsNone(rows[2]["order"]["planned_price"])
            self.assertEqual(rows[2]["order"]["planned_quantity"], 2)
            self.assertEqual(
                [r["trade"]["sequence"] for r in rows if r["kind"] == "trade"],
                list(range(23, 0, -1)),
            )
            for index, expected in enumerate(rows[:4]):
                boundary = await get_execution_log(
                    session, "run", page=index + 1, page_size=1, include_unexecuted=True
                )
                assert boundary is not None
                self.assertEqual(boundary["items"], [expected])
            trades = await get_execution_log(
                session, "run", page=1, page_size=10, include_unexecuted=False
            )
            assert trades is not None
            self.assertEqual(trades["total"], 23)
            self.assertTrue(all(row["kind"] == "trade" for row in trades["items"]))
            self.assertIsNone(
                await get_execution_log(
                    session, "missing", page=1, page_size=10, include_unexecuted=True
                )
            )
            light = await crud.get_backtest_run(session, "run", include_diagnostics=False)
            assert light is not None
            self.assertIsNone(light["diagnostics"])
            full = await crud.get_backtest_run(session, "run")
            assert full is not None
            self.assertEqual(full["diagnostics"]["order_events"], events)
            members = await crud.list_backtest_members(session, "log", include_diagnostics=False)
            self.assertIsNone(members[0]["diagnostics"])

    async def test_malformed_diagnostics_are_empty(self):
        async with self.sessions() as session:
            await crud.create_backtest(session, self._payload("log", "run"))
            for diagnostics in [
                None,
                {},
                {"order_events": {}},
                {"order_events": [None, 1, "x", []]},
            ]:
                await session.execute(
                    update(backtest_runs)
                    .where(backtest_runs.c.run_id == "run")
                    .values(diagnostics=diagnostics)
                )
                page = await get_execution_log(
                    session, "run", page=1, page_size=10, include_unexecuted=True
                )
                assert page is not None
                self.assertEqual((page["total"], page["items"]), (0, []))
