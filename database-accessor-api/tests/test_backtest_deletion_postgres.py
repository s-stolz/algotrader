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
            "V020",
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

    async def _seed_backtest(self, backtest_id: str, status: str, members: tuple[str, ...]) -> None:
        cancelled = status == "cancelled"
        await self.db.execute(
            """INSERT INTO backtests
               (backtest_id, submission_id, status, accepted_at, lifecycle_revision,
                definition_schema_version, accepted_definition, strategy_metadata,
                raw_count, member_count, excluded_count, cancel_requested_at,
                cancellation_source, cancellation_reason)
               VALUES ($1, $1, $2, now(), 1, 1, '{}'::jsonb, '{}'::jsonb,
                       $3, $3, 0, CASE WHEN $4 THEN now() END,
                       CASE WHEN $4 THEN 'user' END, CASE WHEN $4 THEN 'user_requested' END)""",
            backtest_id,
            status,
            len(members),
            cancelled,
        )
        for ordinal, run_id in enumerate(members):
            await self.db.execute(
                """INSERT INTO backtest_runs
                   (run_id, backtest_id, run_ordinal, status, submitted_at, completed_at,
                    request_schema_version, request, replay_descriptor, metrics, diagnostics)
                   VALUES ($1, $2, $3, 'succeeded', now(), now(), 3,
                           '{"symbols":["EURUSD"],"strategy":{"strategy_version":1}}'::jsonb,
                           '{"schema_version":1}'::jsonb, '{}'::jsonb, '{}'::jsonb)""",
                run_id,
                backtest_id,
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
            """INSERT INTO backtest_events
               (backtest_id, revision, event_type, status, occurred_at)
               VALUES ($1, 0, 'accepted', 'queued', now())""",
            backtest_id,
        )
        await self.db.execute(
            """INSERT INTO backtest_commands
               (backtest_id, command_id, command, status, lifecycle_revision, occurred_at)
               VALUES ($1, 'cancel-command', 'cancel', $2, 1, now())""",
            backtest_id,
            status,
        )

    async def test_cutover_requires_verified_exit_and_preserves_markets(self) -> None:
        upgrade_schema = f"backtest_upgrade_{uuid4().hex}"
        await self.db.execute(f'CREATE SCHEMA "{upgrade_schema}"')
        try:
            await self.db.execute(f'SET search_path TO "{upgrade_schema}"')
            await self.db.execute("DROP FUNCTION pg_temp.normalized_experiment_name(jsonb)")
            for migration in sorted((ROOT / "timescaledb-init/migrations").glob("V*.sql")):
                version = int(migration.name[1:4])
                if version == 1 or 7 <= version <= 17:
                    await self.db.execute(migration.read_text())
            await self.db.execute("""INSERT INTO markets
                (symbol, exchange, market_type, min_move, timezone)
                VALUES ('KEEP', 'FX', 'fixture', 0.01, 'UTC')""")
            await self.db.execute("""INSERT INTO backtest_runs
                (run_id, status, submitted_at, request_schema_version, request)
                VALUES ('active', 'running', now(), 2, '{}')""")
            await self.db.execute("""UPDATE backtest_execution_slot
                SET run_id = 'active', owner_token = 'owner' WHERE slot_id = 1""")
            migration = ROOT / "timescaledb-init/migrations/V020__unified_backtests.sql"
            with self.assertRaisesRegex(asyncpg.PostgresError, "Stop and settle"):
                async with self.db.transaction():
                    await self.db.execute(migration.read_text())
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT owner_token FROM backtest_execution_slot WHERE slot_id = 1"
                ),
                "owner",
            )
            await self.db.execute("""UPDATE backtest_execution_slot
                SET run_id = NULL, owner_token = NULL WHERE slot_id = 1""")
            async with self.db.transaction():
                await self.db.execute(migration.read_text())
            self.assertEqual(await self.db.fetchval("SELECT symbol FROM markets"), "KEEP")
            await self._seed_backtest("new-backtest", "completed", ("new-run",))
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT backtest_id FROM backtest_runs WHERE run_id = 'new-run'"
                ),
                "new-backtest",
            )
        finally:
            await self.db.execute(f'SET search_path TO "{self.schema}"')
            await self.db.execute(f'DROP SCHEMA "{upgrade_schema}" CASCADE')

    async def test_delete_whole_backtest_artifacts_and_reject_direct_member(self) -> None:
        await self._seed_backtest("target", "completed", ("one", "two"))
        await self.db.execute("""UPDATE backtest_runs SET status = 'failed', metrics = NULL,
            diagnostics = NULL, replay_descriptor = NULL WHERE run_id = 'two'""")
        await self._seed_backtest("unrelated", "cancelled", ("other",))
        with self.assertRaises(asyncpg.PostgresError):
            await self.db.execute("DELETE FROM backtest_runs WHERE run_id = 'one'")
        async with self.sessions() as session:
            self.assertTrue(await crud.delete_backtest(session, "target"))
        for table in (
            "backtests",
            "backtest_runs",
            "backtest_fills",
            "backtest_closed_trades",
            "backtest_events",
            "backtest_commands",
        ):
            self.assertEqual(
                await self.db.fetchval(
                    f"SELECT count(*) FROM {table} WHERE "
                    + (
                        "backtest_id = 'target'"
                        if table
                        in {
                            "backtests",
                            "backtest_runs",
                            "backtest_events",
                            "backtest_commands",
                        }
                        else "run_id IN ('one', 'two')"
                    )
                ),
                0,
            )
            self.assertEqual(await self.db.fetchval(f"SELECT count(*) FROM {table}"), 1)

    async def test_cancelled_backtest_preserves_earlier_success_until_explicit_delete(self) -> None:
        await self._seed_backtest("cancelled-target", "cancelled", ("success", "cancelled"))
        await self.db.execute("""UPDATE backtest_runs SET status = 'cancelled',
            cancel_requested_at = now(), cancellation_source = 'backtest',
            cancellation_reason = 'backtest_cancel_requested', metrics = NULL,
            diagnostics = NULL, replay_descriptor = NULL WHERE run_id = 'cancelled'""")
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_fills WHERE run_id = 'success'"),
            1,
        )
        async with self.sessions() as session:
            self.assertTrue(await crud.delete_backtest(session, "cancelled-target"))
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtests"), 0)
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_runs"), 0)
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_fills"), 0)

    async def test_state_race_and_failure_roll_back_without_partial_removal(self) -> None:
        await self._seed_backtest("race", "completed", ("member",))
        await self.db.execute("""CREATE FUNCTION reject_delete() RETURNS trigger LANGUAGE plpgsql
            AS $$ BEGIN RAISE EXCEPTION 'delete rejected'; END $$""")
        await self.db.execute("""CREATE TRIGGER reject_delete BEFORE DELETE ON backtest_events
            FOR EACH ROW EXECUTE FUNCTION reject_delete()""")
        async with self.sessions() as session:
            with self.assertRaises(Exception):
                await crud.delete_backtest(session, "race")
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_runs WHERE backtest_id = 'race'"),
            1,
        )
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_fills WHERE run_id = 'member'"), 1
        )
        await self.db.execute("DROP TRIGGER reject_delete ON backtest_events")

        lock = await asyncpg.connect(**self.options)
        try:
            await lock.execute(f'SET search_path TO "{self.schema}"')
            async with self.sessions() as session:
                async with lock.transaction():
                    await lock.execute(
                        "UPDATE backtests SET status = 'running' WHERE backtest_id = 'race'"
                    )
                    waiting = asyncio.create_task(crud.delete_backtest(session, "race"))
                    await asyncio.sleep(0.1)
                    self.assertFalse(waiting.done())
                with self.assertRaises(crud.BacktestDeletionConflictError):
                    await asyncio.wait_for(waiting, timeout=5)
        finally:
            await lock.close()
        self.assertEqual(
            await self.db.fetchval("SELECT count(*) FROM backtest_runs WHERE backtest_id = 'race'"),
            1,
        )
