"""Live PostgreSQL proof of the execution slot migration and owner exclusion."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
from app import backtest_execution
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

RUN_LIVE = os.environ.get("RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS") == "1"
ROOT = Path(__file__).resolve().parents[2]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name] = value.strip().strip('"').strip("'")
    return values


@unittest.skipUnless(RUN_LIVE, "set RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS=1")
class BacktestExecutionPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        env_dir = Path(os.environ.get("BACKTEST_INTEGRATION_ENV_DIR", ROOT / "config"))
        shared = _read_env(env_dir / ".env.shared")
        secrets = _read_env(env_dir / ".env.secrets.db")
        self.connection_options: dict[str, Any] = {
            "host": "127.0.0.1",
            "port": int(shared["TIMESCALEDB_PUBLISHED_PORT"]),
            "database": shared["TIMESCALEDB_DB"],
            "user": shared["TIMESCALEDB_USER"],
            "password": secrets["TIMESCALEDB_PASSWORD"],
        }
        self.schema = f"backtest_execution_test_{uuid4().hex}"
        self.db = await asyncpg.connect(**self.connection_options)
        await self.db.execute(f'CREATE SCHEMA "{self.schema}"')
        await self.db.execute(f'SET search_path TO "{self.schema}"')
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V001__base_schema.sql").read_text()
        )

    async def asyncTearDown(self) -> None:
        await self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.db.close()

    async def _insert_run(self, run_id: str, status: str, submitted_at: str) -> None:
        await self.db.execute(
            """INSERT INTO backtest_runs
               (run_id, status, submitted_at, request_schema_version, request)
               VALUES ($1, $2, $3::timestamptz, 2, '{}'::jsonb)""",
            run_id,
            status,
            datetime.fromisoformat(submitted_at.replace("Z", "+00:00")),
        )

    async def _migrate(self) -> None:
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V007__equity_replay_descriptor.sql").read_text()
        )
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V008__immutable_backtest_batches.sql").read_text()
        )
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V009__backtest_execution_slot.sql").read_text()
        )

    async def test_migration_preserves_history_and_rejects_legacy_claim(self) -> None:
        await self._insert_run("queued", "queued", "2026-06-08T12:30:00Z")
        await self._insert_run("running", "running", "2026-06-08T12:31:00Z")
        await self._insert_run("success", "succeeded", "2026-06-08T12:32:00Z")
        await self.db.execute("""INSERT INTO backtest_fills
               (run_id, fill_sequence, timestamp_ms, symbol, side, quantity, price, fees)
               VALUES ('success', 0, 1, 'EURUSD', 'buy', 1, 1, 0)""")

        await self._migrate()

        states = await self.db.fetch("SELECT run_id, status FROM backtest_runs ORDER BY run_id")
        self.assertEqual(
            [(row["run_id"], row["status"]) for row in states],
            [("queued", "queued"), ("running", "running"), ("success", "succeeded")],
        )
        self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_fills"), 1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.db.execute("UPDATE backtest_runs SET status='running' WHERE run_id='queued'")

    async def test_two_database_connections_cannot_claim_separate_slots(self) -> None:
        await self._insert_run("first", "queued", "2026-06-08T12:30:00Z")
        await self._insert_run("second", "queued", "2026-06-08T12:31:00Z")
        await self._migrate()
        other = await asyncpg.connect(**self.connection_options)
        await other.execute(f'SET search_path TO "{self.schema}"')
        try:
            await self.db.execute("BEGIN")
            await other.execute("BEGIN")
            self.assertEqual(
                await self.db.execute(
                    """UPDATE backtest_execution_slot SET owner_token='owner-a', run_id='first'
                       WHERE slot_id=1 AND owner_token IS NULL"""
                ),
                "UPDATE 1",
            )
            competing = asyncio.create_task(
                other.execute(
                    """UPDATE backtest_execution_slot SET owner_token='owner-b', run_id='second'
                       WHERE slot_id=1 AND owner_token IS NULL"""
                )
            )
            await asyncio.sleep(0.1)
            self.assertFalse(competing.done())
            await self.db.execute("UPDATE backtest_runs SET status='running' WHERE run_id='first'")
            await self.db.execute("COMMIT")
            self.assertEqual(await competing, "UPDATE 0")
            await other.execute("ROLLBACK")
            self.assertEqual(
                await self.db.fetchval("SELECT run_id FROM backtest_execution_slot"), "first"
            )
            self.assertEqual(
                await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='second'"),
                "queued",
            )
        finally:
            if self.db.is_in_transaction():
                await self.db.execute("ROLLBACK")
            if other.is_in_transaction():
                await other.execute("ROLLBACK")
            await other.close()

    async def test_accessor_claim_and_settlement_are_fenced_across_connections(self) -> None:
        await self._insert_run("first", "queued", "2026-06-08T12:30:00Z")
        await self._insert_run("second", "queued", "2026-06-08T12:31:00Z")
        await self._migrate()
        engine = create_async_engine(
            URL.create(
                "postgresql+asyncpg",
                username=self.connection_options["user"],
                password=self.connection_options["password"],
                host=self.connection_options["host"],
                port=self.connection_options["port"],
                database=self.connection_options["database"],
            )
        )
        started_at = datetime.fromisoformat("2026-06-08T12:32:00+00:00")

        async def attempt(token: str) -> bool:
            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    return await backtest_execution.claim(
                        session, run_id="first", owner_token=token, started_at=started_at
                    )

        try:
            first, second = await asyncio.gather(attempt("owner-a"), attempt("owner-b"))
            self.assertEqual(int(first) + int(second), 1)
            winner = "owner-a" if first else "owner-b"
            self.assertEqual(
                await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='second'"),
                "queued",
            )

            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    self.assertFalse(
                        await backtest_execution.settle(
                            session,
                            run_id="first",
                            owner_token="stale-owner",
                            terminal={
                                "status": "failed",
                                "completed_at": started_at,
                                "error_code": "x",
                                "error_message": "x",
                            },
                        )
                    )
                    self.assertTrue(
                        await backtest_execution.settle(
                            session,
                            run_id="first",
                            owner_token=winner,
                            terminal={
                                "status": "failed",
                                "completed_at": started_at,
                                "error_code": "backtest_failed",
                                "error_message": "Backtest execution failed",
                            },
                        )
                    )
            self.assertEqual(
                await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='first'"),
                "failed",
            )
            self.assertIsNone(
                await self.db.fetchval("SELECT owner_token FROM backtest_execution_slot")
            )
        finally:
            await engine.dispose()

    async def test_restart_reconciliation_preserves_queued_work_once(self) -> None:
        await self._insert_run("interrupted", "running", "2026-06-08T12:30:00Z")
        await self._insert_run("waiting", "queued", "2026-06-08T12:31:00Z")
        await self._migrate()
        engine = create_async_engine(
            URL.create(
                "postgresql+asyncpg",
                username=self.connection_options["user"],
                password=self.connection_options["password"],
                host=self.connection_options["host"],
                port=self.connection_options["port"],
                database=self.connection_options["database"],
            )
        )
        try:
            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    completed_at = datetime.fromisoformat("2026-06-08T12:35:00+00:00")
                    options: dict[str, Any] = dict(
                        completed_at=completed_at,
                        error_code="worker_interrupted",
                        error_message="Backtest worker was interrupted before completion",
                    )
                    self.assertEqual(await backtest_execution.reconcile(session, **options), 1)
                    self.assertEqual(await backtest_execution.reconcile(session, **options), 0)
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT status FROM backtest_runs WHERE run_id='interrupted'"
                ),
                "failed",
            )
            self.assertEqual(
                await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='waiting'"),
                "queued",
            )
        finally:
            await engine.dispose()

    async def test_two_worker_processes_cannot_claim_separate_runs(self) -> None:
        await self._insert_run("first", "queued", "2026-06-08T12:30:00Z")
        await self._insert_run("second", "queued", "2026-06-08T12:31:00Z")
        await self._migrate()

        async def attempt(token: str) -> bool:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(Path(__file__).resolve()),
                self.schema,
                token,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            self.assertEqual(process.returncode, 0, stderr.decode())
            return stdout.strip() == b"1"

        first, second = await asyncio.gather(attempt("worker-a"), attempt("worker-b"))
        self.assertEqual(int(first) + int(second), 1)
        self.assertEqual(
            await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='first'"),
            "running",
        )
        self.assertEqual(
            await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='second'"),
            "queued",
        )


async def _claim_from_worker_process(schema: str, token: str) -> None:
    env_dir = Path(os.environ.get("BACKTEST_INTEGRATION_ENV_DIR", ROOT / "config"))
    shared = _read_env(env_dir / ".env.shared")
    secrets = _read_env(env_dir / ".env.secrets.db")
    engine = create_async_engine(
        URL.create(
            "postgresql+asyncpg",
            username=shared["TIMESCALEDB_USER"],
            password=secrets["TIMESCALEDB_PASSWORD"],
            host="127.0.0.1",
            port=int(shared["TIMESCALEDB_PUBLISHED_PORT"]),
            database=shared["TIMESCALEDB_DB"],
        )
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'SET search_path TO "{schema}"'))
            await connection.commit()
            async with AsyncSession(bind=connection) as session:
                claimed = await backtest_execution.claim(
                    session,
                    run_id="first",
                    owner_token=token,
                    started_at=datetime.fromisoformat("2026-06-08T12:32:00+00:00"),
                )
                print(int(claimed))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_claim_from_worker_process(sys.argv[1], sys.argv[2]))
