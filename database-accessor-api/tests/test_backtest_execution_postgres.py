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
from app import backtest_execution, crud
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
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V010__backtest_worker_heartbeat.sql").read_text()
        )
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V011__backtest_batch_turns.sql").read_text()
        )
        await self.db.execute(
            (
                ROOT / "timescaledb-init/migrations/V012__backtest_batch_event_prior_status.sql"
            ).read_text()
        )
        for pause_migration in (ROOT / "timescaledb-init/migrations").glob("V013__*.sql"):
            await self.db.execute(pause_migration.read_text())
        await self.db.execute(
            (ROOT / "timescaledb-init/migrations/V014__backtest_run_cancellation.sql").read_text()
        )

    async def test_cancel_and_completion_are_serialized_at_the_slot(self) -> None:
        await self._insert_run("active", "queued", "2026-06-08T12:30:00Z")
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
        at = datetime.fromisoformat("2026-06-08T12:32:00+00:00")

        async def operate(operation):
            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    return await operation(session)

        try:
            self.assertTrue(
                await operate(
                    lambda session: backtest_execution.claim(
                        session,
                        run_id="active",
                        owner_token="owner",
                        started_at=at,
                    )
                )
            )
            cancel, normal = await asyncio.gather(
                operate(
                    lambda session: backtest_execution.cancel_run(
                        session,
                        run_id="active",
                        requested_at=at,
                    )
                ),
                operate(
                    lambda session: backtest_execution.settle(
                        session,
                        run_id="active",
                        owner_token="owner",
                        terminal={
                            "status": "failed",
                            "completed_at": at,
                            "error_code": "failure",
                            "error_message": "failed",
                        },
                    )
                ),
            )
            state = await self.db.fetchrow(
                "SELECT status, cancel_requested_at FROM backtest_runs WHERE run_id='active'"
            )
            if normal:
                self.assertEqual((cancel, state["status"]), ("conflict", "failed"))
                self.assertIsNone(state["cancel_requested_at"])
            else:
                self.assertEqual((cancel, state["status"]), ("accepted", "cancelling"))
                self.assertEqual(
                    await self.db.fetchval("SELECT run_id FROM backtest_execution_slot"), "active"
                )
                self.assertTrue(
                    await operate(
                        lambda session: backtest_execution.settle(
                            session,
                            run_id="active",
                            owner_token="owner",
                            terminal={"status": "cancelled", "completed_at": at},
                        )
                    )
                )
            self.assertEqual(
                await self.db.fetchval("SELECT count(*) FROM backtest_fills WHERE run_id='active'"),
                0,
            )
            self.assertIsNone(
                await self.db.fetchval("SELECT owner_token FROM backtest_execution_slot")
            )
            self.assertTrue(
                await operate(
                    lambda session: backtest_execution.claim(
                        session,
                        run_id="waiting",
                        owner_token="next",
                        started_at=at,
                    )
                )
            )
        finally:
            await engine.dispose()

    async def test_heartbeat_and_queue_read_leave_durable_lifecycle_untouched(self) -> None:
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
        try:
            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    first = await backtest_execution.record_heartbeat(
                        session,
                        worker_id="worker-a",
                        owner_token=None,
                        fault_code=None,
                        fault_message=None,
                    )
                    state = await backtest_execution.read_queue_state(session)
                    self.assertEqual(first["worker_id"], "worker-a")
                    self.assertEqual(
                        [run["run_id"] for run in state["queued_runs"]], ["first", "second"]
                    )
                    self.assertIsNone(state["active_run"])
                    self.assertEqual(state["heartbeats"][0]["worker_id"], "worker-a")
                    await backtest_execution.record_heartbeat(
                        session,
                        worker_id="worker-a",
                        owner_token=None,
                        fault_code="reconciliation_failed",
                        fault_message="Operator restart required",
                    )
                    faulted = await backtest_execution.read_queue_state(session)
                    self.assertEqual(
                        faulted["heartbeats"][0]["fault_code"], "reconciliation_failed"
                    )
            self.assertEqual(
                await self.db.fetchval("SELECT count(*) FROM backtest_worker_heartbeats"), 1
            )
            self.assertEqual(
                await self.db.fetchval("SELECT count(*) FROM backtest_runs WHERE status='queued'"),
                2,
            )
            self.assertIsNone(
                await self.db.fetchval("SELECT owner_token FROM backtest_execution_slot")
            )
        finally:
            await engine.dispose()

    async def test_active_owner_heartbeat_survives_more_than_32_newer_idle_rows(self) -> None:
        await self._insert_run("active", "running", "2026-06-08T12:30:00Z")
        await self._migrate()
        await self.db.execute("""UPDATE backtest_runs SET started_at=now() - interval '1 minute'
               WHERE run_id='active'""")
        await self.db.execute(
            """UPDATE backtest_execution_slot SET owner_token='active-owner', run_id='active'
               WHERE slot_id=1"""
        )
        await self.db.execute("""INSERT INTO backtest_worker_heartbeats
               (worker_id, owner_token, heartbeat_at)
               VALUES ('active-worker', 'active-owner', now() - interval '1 second')""")
        await self.db.executemany(
            """INSERT INTO backtest_worker_heartbeats
               (worker_id, owner_token, heartbeat_at) VALUES ($1, NULL, now())""",
            [(f"idle-{index}",) for index in range(40)],
        )
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
                    state = await backtest_execution.read_queue_state(session)
            self.assertEqual(state["active_run"]["run_id"], "active")
            self.assertEqual([beat["worker_id"] for beat in state["heartbeats"]], ["active-worker"])
            self.assertEqual(
                await self.db.fetchval("SELECT owner_token FROM backtest_execution_slot"),
                "active-owner",
            )
            self.assertEqual(
                await self.db.fetchval("SELECT status FROM backtest_runs WHERE run_id='active'"),
                "running",
            )
        finally:
            await engine.dispose()

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

    async def test_batches_and_standalone_runs_take_durable_turns_through_restart(self) -> None:
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
        accepted_at = datetime.fromisoformat("2026-06-08T12:30:00+00:00")

        async def operate(operation):
            async with engine.connect() as connection:
                await connection.execute(text(f'SET search_path TO "{self.schema}"'))
                await connection.commit()
                async with AsyncSession(bind=connection) as session:
                    return await operation(session)

        async def add_standalone(session, run_id):
            return await crud.insert_backtest_run(
                session,
                {
                    "run_id": run_id,
                    "status": "queued",
                    "submitted_at": accepted_at,
                    "request_schema_version": 2,
                    "request": {},
                },
            )

        async def add_batch(session, batch_id, size):
            return await crud.create_backtest_batch(
                session,
                {
                    "batch_id": batch_id,
                    "submission_id": f"submission-{batch_id}",
                    "accepted_at": accepted_at,
                    "definition_schema_version": 1,
                    "accepted_definition": {},
                    "strategy_metadata": {},
                    "raw_count": size,
                    "member_count": size,
                    "excluded_count": 0,
                    "members": [
                        {
                            "run_id": f"{batch_id}-{ordinal}",
                            "member_ordinal": ordinal,
                            "request_schema_version": 3,
                            "request": {"symbols": ["EURUSD"], "strategy": {"strategy_version": 1}},
                        }
                        for ordinal in range(size)
                    ],
                },
            )

        async def turn(session, run_id, terminal, token):
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id=run_id,
                    owner_token=token,
                    started_at=accepted_at,
                )
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session,
                    run_id="other",
                    owner_token="other",
                    started_at=accepted_at,
                )
            )
            return await backtest_execution.settle(
                session,
                run_id=run_id,
                owner_token=token,
                terminal=terminal,
            )

        success = {
            "status": "succeeded",
            "completed_at": accepted_at,
            "result_schema_version": 3,
            "metrics": {"trade_count": 1},
            "diagnostics": {},
            "replay_descriptor": {"fingerprint_digest": "saved"},
            "fills": [
                {
                    "fill_sequence": 0,
                    "timestamp_ms": 1,
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 1.0,
                    "price": 1.0,
                    "fees": 0.0,
                }
            ],
        }
        failure = {
            "status": "failed",
            "completed_at": accepted_at,
            "error_code": "backtest_failed",
            "error_message": "Backtest failed",
        }
        try:
            await operate(lambda session: add_standalone(session, "standalone-1"))
            await operate(lambda session: add_batch(session, "batch-a", 2))
            await operate(lambda session: add_standalone(session, "standalone-2"))
            await operate(lambda session: add_batch(session, "batch-b", 3))
            self.assertEqual(
                [
                    entry["run_id"]
                    for entry in (await operate(backtest_execution.read_queue_state))[
                        "queued_entries"
                    ]
                ],
                ["standalone-1", "batch-a-0", "standalone-2", "batch-b-0"],
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "standalone-1", success, "owner-1"))
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "batch-a-0", success, "owner-2"))
            )
            await operate(lambda session: add_standalone(session, "standalone-3"))
            self.assertEqual(
                [
                    entry["run_id"]
                    for entry in (await operate(backtest_execution.read_queue_state))[
                        "queued_entries"
                    ]
                ],
                ["standalone-2", "batch-b-0", "batch-a-1", "standalone-3"],
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "standalone-2", failure, "owner-3"))
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "batch-b-0", success, "owner-4"))
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "batch-a-1", failure, "owner-5"))
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT status FROM backtest_batches WHERE batch_id='batch-a'"
                ),
                "completed",
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT count(*) FROM backtest_fills WHERE run_id='batch-a-0'"
                ),
                1,
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT replay_descriptor->>'fingerprint_digest' FROM backtest_runs "
                    "WHERE run_id='batch-a-0'"
                ),
                "saved",
            )
            self.assertTrue(
                await self.db.fetchval(
                    "SELECT replay_descriptor IS NULL FROM backtest_runs WHERE run_id='batch-a-1'"
                )
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT lifecycle_revision FROM backtest_batches WHERE batch_id='batch-a'"
                ),
                2,
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT count(*) FROM backtest_batch_events WHERE batch_id='batch-a'"
                ),
                3,
            )
            events = await self.db.fetch(
                "SELECT revision, event_type, prior_status, status, trigger_run_id "
                "FROM backtest_batch_events WHERE batch_id='batch-a' ORDER BY revision"
            )
            self.assertEqual(
                [tuple(event.values()) for event in events],
                [
                    (0, "accepted", None, "queued", None),
                    (1, "started", "queued", "running", "batch-a-0"),
                    (2, "completed", "running", "completed", "batch-a-1"),
                ],
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "standalone-3", success, "owner-6"))
            )
            self.assertTrue(
                await operate(
                    lambda session: backtest_execution.claim(
                        session,
                        run_id="batch-b-1",
                        owner_token="interrupted",
                        started_at=accepted_at,
                    )
                )
            )
            await self.db.execute(
                "UPDATE backtest_execution_slot SET owner_token=NULL, run_id=NULL WHERE slot_id=1"
            )
            self.assertEqual(
                await operate(
                    lambda session: backtest_execution.reconcile(
                        session,
                        completed_at=accepted_at,
                        error_code="worker_interrupted",
                        error_message="Worker interrupted",
                    )
                ),
                1,
            )
            self.assertEqual(
                await operate(
                    lambda session: backtest_execution.reconcile(
                        session,
                        completed_at=accepted_at,
                        error_code="worker_interrupted",
                        error_message="Worker interrupted",
                    )
                ),
                0,
            )
            self.assertEqual(
                [
                    entry["run_id"]
                    for entry in (await operate(backtest_execution.read_queue_state))[
                        "queued_entries"
                    ]
                ],
                ["batch-b-2"],
            )
            self.assertTrue(
                await operate(lambda session: turn(session, "batch-b-2", success, "owner-7"))
            )
            self.assertEqual(
                await self.db.fetchval(
                    "SELECT status FROM backtest_batches WHERE batch_id='batch-b'"
                ),
                "completed",
            )
            self.assertEqual(await self.db.fetchval("SELECT count(*) FROM backtest_queue_turns"), 0)
        finally:
            await engine.dispose()


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
