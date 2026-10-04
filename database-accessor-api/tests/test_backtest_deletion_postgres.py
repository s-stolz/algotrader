"""Opt-in real PostgreSQL deletion and immutable-membership proof."""

from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from uuid import uuid4

import asyncpg
from app import crud
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]


def _env(path: Path) -> dict[str, str]:
    return {
        name: value.strip().strip('"').strip("'")
        for line in path.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
        for name, value in [line.split("=", 1)]
    }


@unittest.skipUnless(
    os.environ.get("RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS") == "1",
    "set RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS=1",
)
class BacktestDeletionPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        config = Path(os.environ.get("BACKTEST_INTEGRATION_ENV_DIR", ROOT / "config"))
        shared, secrets = _env(config / ".env.shared"), _env(config / ".env.secrets.db")
        self.options = {
            "host": "127.0.0.1",
            "port": int(shared["TIMESCALEDB_PUBLISHED_PORT"]),
            "database": shared["TIMESCALEDB_DB"],
            "user": shared["TIMESCALEDB_USER"],
            "password": secrets["TIMESCALEDB_PASSWORD"],
        }
        self.schema = f"backtest_delete_test_{uuid4().hex}"
        self.db = await asyncpg.connect(**self.options)
        await self.db.execute(f'CREATE SCHEMA "{self.schema}"')
        await self.db.execute(f'SET search_path TO "{self.schema}"')
        for version in (
            "V001",
            "V007",
            "V008",
            "V009",
            "V010",
            "V011",
            "V012",
            "V013",
            "V014",
            "V015",
            "V016",
            "V017",
        ):
            migration = next((ROOT / "timescaledb-init/migrations").glob(f"{version}__*.sql"))
            await self.db.execute(migration.read_text())
        self.engine = create_async_engine(
            URL.create(
                "postgresql+asyncpg",
                username=self.options["user"],
                password=self.options["password"],
                host=self.options["host"],
                port=self.options["port"],
                database=self.options["database"],
            ),
            connect_args={"server_settings": {"search_path": self.schema}},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        await self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.db.close()

    async def _seed_batch(self, batch_id: str, status: str, members: tuple[str, ...]) -> None:
        cancelled = status == "cancelled"
        await self.db.execute(
            """INSERT INTO backtest_batches
               (batch_id, submission_id, status, accepted_at, lifecycle_revision,
                definition_schema_version, accepted_definition, strategy_metadata,
                raw_count, member_count, excluded_count, cancel_requested_at,
                cancellation_source, cancellation_reason)
               VALUES ($1, $1, $2, now(), 1, 1, '{}'::jsonb, '{}'::jsonb,
                       $3, $3, 0, CASE WHEN $4 THEN now() END,
                       CASE WHEN $4 THEN 'user' END, CASE WHEN $4 THEN 'user_requested' END)""",
            batch_id,
            status,
            len(members),
            cancelled,
        )
        for ordinal, run_id in enumerate(members):
            await self.db.execute(
                """INSERT INTO backtest_runs
                   (run_id, batch_id, member_ordinal, status, submitted_at, completed_at,
                    request_schema_version, request, replay_descriptor, metrics, diagnostics)
                   VALUES ($1, $2, $3, 'succeeded', now(), now(), 3,
                           '{"symbols":["EURUSD"],"strategy":{"strategy_version":1}}'::jsonb,
                           '{"schema_version":1}'::jsonb, '{}'::jsonb, '{}'::jsonb)""",
                run_id,
                batch_id,
                ordinal,
            )
            await self.db.execute(
                """INSERT INTO backtest_fills
                   (run_id, fill_sequence, timestamp_ms, symbol, side, quantity, price, fees)
                   VALUES ($1, 0, 1000, 'EURUSD', 'buy', 1, 1, 0)""",
                run_id,
            )
            await self.db.execute(
                """INSERT INTO backtest_closed_trades
                   (run_id, trade_sequence, trade_id, symbol, trade_direction, quantity,
                    entry_timestamp_ms, entry_price, exit_timestamp_ms, exit_price,
                    realized_pnl, fees, exit_reason)
                   VALUES ($1, 0, $1, 'EURUSD', 'long', 1, 1000, 1, 2000, 2,
                           1, 0, 'signal')""",
                run_id,
            )
        await self.db.execute(
            """INSERT INTO backtest_batch_events
               (batch_id, revision, event_type, status, occurred_at)
               VALUES ($1, 0, 'accepted', 'queued', now())""",
            batch_id,
        )
        await self.db.execute(
            """INSERT INTO backtest_batch_commands
               (batch_id, command_id, command, status, lifecycle_revision, occurred_at)
               VALUES ($1, 'cancel-command', 'cancel', $2, 1, now())""",
            batch_id,
            status,
        )

    async def test_delete_whole_batch_artifacts_and_reject_direct_member(self) -> None:
        await self._seed_batch("target", "completed", ("one", "two"))
        await self.db.execute("""UPDATE backtest_runs SET status = 'failed', metrics = NULL,
            diagnostics = NULL, replay_descriptor = NULL WHERE run_id = 'two'""")
        await self._seed_batch("unrelated", "cancelled", ("other",))
        with self.assertRaises(asyncpg.PostgresError):
            await self.db.execute("DELETE FROM backtest_runs WHERE run_id = 'one'")
        async with self.sessions() as session:
            self.assertTrue(await crud.delete_backtest_batch(session, "target"))
        for table in (
            "backtest_batches",
            "backtest_runs",
            "backtest_fills",
            "backtest_closed_trades",
            "backtest_batch_events",
            "backtest_batch_commands",
        ):
            self.assertEqual(
                await self.db.fetchval(
                    f"SELECT count(*) FROM {table} WHERE "
                    + (
                        "batch_id = 'target'"
                        if table
                        in {
                            "backtest_batches",
                            "backtest_runs",
                            "backtest_batch_events",
                            "backtest_batch_commands",
                        }
                        else "run_id IN ('one', 'two')"
                    )
                ),
                0,
            )
            self.assertEqual(await self.db.fetchval(f"SELECT count(*) FROM {table}"), 1)

    async def test_cancelled_batch_preserves_earlier_success_until_explicit_delete(self) -> None:
        await self._seed_batch("cancelled-target", "cancelled", ("success", "cancelled"))
        await self.db.execute("""UPDATE backtest_runs SET status = 'cancelled',
            cancel_requested_at = now(), cancellation_source = 'batch',
            cancellation_reason = 'batch_cancel_requested', metrics = NULL,
            diagnostics = NULL, replay_descriptor = NULL WHERE run_id = 'cancelled'""")
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_fills WHERE run_id = 'success'"),
            1,
        )
        async with self.sessions() as session:
            self.assertTrue(await crud.delete_backtest_batch(session, "cancelled-target"))
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_batches"), 0)
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_runs"), 0)
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_fills"), 0)

    async def test_standalone_terminal_delete_retains_unrelated_and_rejects_active(self) -> None:
        for run_id, status in (
            ("success", "succeeded"),
            ("failure", "failed"),
            ("cancelled", "cancelled"),
            ("active", "queued"),
            ("unrelated", "succeeded"),
        ):
            cancelled = status == "cancelled"
            await self.db.execute(
                """INSERT INTO backtest_runs
                   (run_id, status, submitted_at, completed_at, cancel_requested_at,
                    cancellation_source, cancellation_reason, request_schema_version, request)
                   VALUES ($1, $2::varchar, now(), CASE WHEN $2::text != 'queued' THEN now() END,
                           CASE WHEN $3 THEN now() END,
                           CASE WHEN $3 THEN 'user' END,
                           CASE WHEN $3 THEN 'user_requested' END, 2, '{}'::jsonb)""",
                run_id,
                status,
                cancelled,
            )
        await self.db.execute("""INSERT INTO backtest_fills
            (run_id, fill_sequence, timestamp_ms, symbol, side, quantity, price, fees)
            VALUES ('success', 0, 1000, 'EURUSD', 'buy', 1, 1, 0)""")
        async with self.sessions() as session:
            with self.assertRaises(crud.BacktestDeletionConflictError):
                await crud.delete_backtest_run(session, "active")
            for run_id in ("success", "failure", "cancelled"):
                self.assertTrue(await crud.delete_backtest_run(session, run_id))
            self.assertFalse(await crud.delete_backtest_run(session, "missing"))
        self.assertEqual(
            [
                row["run_id"]
                for row in await self.db.fetch("SELECT run_id FROM backtest_runs ORDER BY run_id")
            ],
            ["active", "unrelated"],
        )
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_fills"), 0)

    async def test_state_race_and_failure_roll_back_without_partial_removal(self) -> None:
        await self._seed_batch("race", "completed", ("member",))
        await self.db.execute("""CREATE FUNCTION reject_delete() RETURNS trigger LANGUAGE plpgsql
            AS $$ BEGIN RAISE EXCEPTION 'delete rejected'; END $$""")
        await self.db.execute("""CREATE TRIGGER reject_delete BEFORE DELETE ON backtest_batch_events
            FOR EACH ROW EXECUTE FUNCTION reject_delete()""")
        async with self.sessions() as session:
            with self.assertRaises(Exception):
                await crud.delete_backtest_batch(session, "race")
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_runs WHERE batch_id = 'race'"), 1
        )
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_fills WHERE run_id = 'member'"), 1
        )
        await self.db.execute("DROP TRIGGER reject_delete ON backtest_batch_events")

        lock = await asyncpg.connect(**self.options)
        try:
            await lock.execute(f'SET search_path TO "{self.schema}"')
            async with self.sessions() as session:
                async with lock.transaction():
                    await lock.execute(
                        "UPDATE backtest_batches SET status = 'running' WHERE batch_id = 'race'"
                    )
                    waiting = asyncio.create_task(crud.delete_backtest_batch(session, "race"))
                    await asyncio.sleep(0.1)
                    self.assertFalse(waiting.done())
                with self.assertRaises(crud.BacktestDeletionConflictError):
                    await asyncio.wait_for(waiting, timeout=5)
        finally:
            await lock.close()
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_runs WHERE batch_id = 'race'"), 1
        )
