"""Opt-in PostgreSQL transaction coverage for Backtest submission races."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import uvicorn
from app import backtest_execution, crud
from app.models import (
    backtest_closed_trades,
    backtest_commands,
    backtest_events,
    backtest_execution_slot,
    backtest_fills,
    backtest_queue_turns,
    backtest_runs,
    backtests,
    metadata,
)
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.getenv("BACKTEST_TEST_DATABASE_URL"),
    "set BACKTEST_TEST_DATABASE_URL to a local PostgreSQL database",
)
class BacktestPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.schema = f"backtest_test_{uuid4().hex}"
        url = os.environ["BACKTEST_TEST_DATABASE_URL"]
        self.admin_engine = create_async_engine(url)
        async with self.admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(
            url, connect_args={"server_settings": {"search_path": self.schema}}
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        async with self.admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin_engine.dispose()

    def _payload(self, backtest_id: str, run_id: str, *, definition: str = "original") -> dict:
        return {
            "backtest_id": backtest_id,
            "submission_id": "same-submission",
            "accepted_at": datetime(2026, 9, 26, tzinfo=timezone.utc),
            "definition_schema_version": 1,
            "accepted_definition": {"schema_version": 1, "selection": definition},
            "strategy_metadata": {"strategy_id": "sma_crossover", "strategy_version": 1},
            "raw_count": 1,
            "member_count": 1,
            "excluded_count": 0,
            "members": [
                {
                    "run_id": run_id,
                    "run_ordinal": 0,
                    "request_schema_version": 3,
                    "request": {
                        "symbols": ["EURUSD"],
                        "timeframe": "M1",
                        "strategy": {"strategy_version": 1},
                    },
                }
            ],
        }

    async def _control(self, session, *, backtest_id: str, command: str, command_id: str) -> dict:
        policy = {
            "pause": {
                "accepted_statuses": ["queued", "running"],
                "effective_statuses": ["pausing", "paused"],
                "active_status": "pausing",
                "idle_status": "paused",
                "queue_action": "remove",
            },
            "resume": {
                "accepted_statuses": ["pausing", "paused"],
                "effective_statuses": ["queued", "running"],
                "active_status": "running",
                "idle_status": "running",
                "queue_action": "append",
            },
            "cancel": {
                "accepted_statuses": ["queued", "running", "pausing", "paused"],
                "effective_statuses": ["cancelling", "cancelled"],
                "active_status": "cancelling",
                "idle_status": "cancelled",
                "queue_action": "remove",
            },
        }[command]
        result = await backtest_execution.control_backtest(
            session, backtest_id=backtest_id, command=command, command_id=command_id, policy=policy
        )
        assert result is not None
        return result

    async def _backtest(self, session, backtest_id: str) -> dict:
        result = await crud.get_backtest(session, backtest_id)
        assert result is not None
        return result

    async def test_rename_is_durable_and_changes_only_name(self) -> None:
        async with self.sessions() as session:
            await crud.create_backtest(session, self._payload("backtest", "member"))

        tables = [
            backtest_runs,
            backtests,
            backtest_events,
            backtest_commands,
            backtest_execution_slot,
            backtest_queue_turns,
            backtest_fills,
            backtest_closed_trades,
        ]

        async def snapshot():
            async with self.sessions() as session:
                return {
                    table.name: [
                        dict(row._mapping)
                        for row in (
                            await session.execute(
                                select(table).order_by(*table.primary_key.columns)
                            )
                        ).fetchall()
                    ]
                    for table in tables
                }

        before = await snapshot()
        for name, expected in [
            ("  Duplicate  ", "Duplicate"),
            ("Duplicate", "Duplicate"),
            (" ", None),
            ("😀" * 120, "😀" * 120),
        ]:
            async with self.sessions() as session:
                saved = await crud.rename_backtest(session, "backtest", name)
                assert saved is not None
                self.assertEqual(saved["name"], expected)
            after = await snapshot()
            self.assertEqual(after["backtests"][0]["name"], expected)
            after["backtests"][0]["name"] = before["backtests"][0]["name"]
            self.assertEqual(after, before)
        async with self.sessions() as session:
            self.assertIsNone(await crud.rename_backtest(session, "missing", "x"))
            for name in ["x" * 121, "a\nb", 123]:
                with self.assertRaises(ValueError):
                    await crud.rename_backtest(session, "backtest", name)

    async def test_named_and_unnamed_backtests_preserve_queue_and_members(self) -> None:
        from app.schemas import BacktestCreateIn
        from test_backtests_api import _request_payload

        for index, name in enumerate([None, " ", "  Duplicate  ", "Duplicate", "😀" * 120]):
            payload = self._payload(f"backtest-{index}", f"run-{index}")
            payload["submission_id"] = f"submission-{index}"
            payload["name"] = name
            payload["members"][0]["request"] = _request_payload()
            payload["members"][0]["request"]["strategy"]["strategy_version"] = 1
            accepted = BacktestCreateIn(**payload).model_dump()
            async with self.sessions() as session:
                await crud.create_backtest(session, accepted)
            async with self.sessions() as session:
                saved = await crud.get_backtest(session, payload["backtest_id"])
                assert saved is not None
                self.assertEqual(saved["name"], accepted["name"])
                self.assertEqual(saved["accepted_definition"], accepted["accepted_definition"])
                members = await crud.list_backtest_members(session, payload["backtest_id"])
                self.assertEqual(members[0]["run_ordinal"], 0)
                self.assertEqual(members[0]["request"], accepted["members"][0]["request"])
                state = await backtest_execution.read_queue_state(session)
                self.assertEqual(len(state["queued_entries"]), index + 1)

    async def test_simultaneous_same_id_transactions_return_one_complete_backtest(self) -> None:
        barrier = asyncio.Barrier(2)

        class RacingSession:
            def __init__(self, session):
                self.session = session
                self.has_read = False

            async def execute(self, statement, params=None):
                result = await self.session.execute(statement, params or {})
                if not self.has_read:
                    self.has_read = True
                    await asyncio.wait_for(barrier.wait(), timeout=10)
                return result

            async def commit(self):
                await self.session.commit()

            async def rollback(self):
                await self.session.rollback()

        async def submit(backtest_id: str, run_id: str):
            async with self.sessions() as session:
                return await crud.create_backtest(
                    RacingSession(session), self._payload(backtest_id, run_id)
                )

        first, second = await asyncio.wait_for(
            asyncio.gather(
                submit("backtest-first", "run-first"), submit("backtest-second", "run-second")
            ),
            timeout=20,
        )
        assert first is not None and second is not None
        self.assertEqual(first["backtest_id"], second["backtest_id"])
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(backtests)), 1)
            self.assertEqual(
                await session.scalar(select(func.count()).select_from(backtest_runs)), 1
            )
            self.assertEqual(
                await session.scalar(select(func.count()).select_from(backtest_events)), 1
            )
            members = await crud.list_backtest_members(session, first["backtest_id"])
            self.assertEqual(
                [(row["run_id"], row["run_ordinal"]) for row in members],
                [("run-first" if first["backtest_id"] == "backtest-first" else "run-second", 0)],
            )
            with self.assertRaises(crud.BacktestSubmissionConflictError):
                await crud.create_backtest(
                    session,
                    self._payload("backtest-conflict", "run-conflict", definition="changed"),
                )

    async def test_pause_drains_active_work_and_resume_rejoins_behind_waiter(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            payload = self._payload("backtest-pause", "member-0")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "member-1", "run_ordinal": 1}
            )
            await crud.create_backtest(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="member-0",
                    owner_token="owner-0",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            pause = await self._control(
                session, backtest_id="backtest-pause", command="pause", command_id="pause-1"
            )
            self.assertEqual((pause["status"], pause["lifecycle_revision"]), ("pausing", 2))
            self.assertEqual(
                await self._control(
                    session, backtest_id="backtest-pause", command="pause", command_id="pause-1"
                ),
                pause,
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session,
                    run_id="member-1",
                    owner_token="owner-1",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="member-0",
                    owner_token="owner-0",
                    terminal={
                        "status": "succeeded",
                        "completed_at": now,
                        "result_schema_version": 3,
                        "metrics": {"total_return_pct": 2.5},
                        "diagnostics": {"source": "draining-test"},
                        "replay_descriptor": {
                            "schema_version": 1,
                            "fingerprint_algorithm": "sha256-ts-close-v1",
                            "fingerprint_digest": "0" * 64,
                            "source_point_count": 1,
                            "first_timestamp_ms": 1714525200000,
                            "last_timestamp_ms": 1714525200000,
                        },
                    },
                )
            )
            saved_member = await crud.get_backtest_run(session, "member-0")
            assert saved_member is not None
            self.assertEqual(saved_member["status"], "succeeded")
            self.assertEqual(saved_member["metrics"], {"total_return_pct": 2.5})
            self.assertEqual(saved_member["replay_descriptor"]["source_point_count"], 1)
            backtest = await self._backtest(session, "backtest-pause")
            self.assertEqual((backtest["status"], backtest["lifecycle_revision"]), ("paused", 3))
            state = await backtest_execution.read_queue_state(session)
            self.assertEqual(state["queued_entries"], [])
            waiter = self._payload("waiter-backtest", "waiter")
            waiter["submission_id"] = "waiter-submission"
            await crud.create_backtest(session, waiter)
            with self.assertRaises(backtest_execution.BacktestCommandConflictError):
                await self._control(
                    session, backtest_id="backtest-pause", command="resume", command_id="pause-1"
                )
            resumed = await self._control(
                session, backtest_id="backtest-pause", command="resume", command_id="resume-1"
            )
            self.assertEqual((resumed["status"], resumed["lifecycle_revision"]), ("running", 4))
            state = await backtest_execution.read_queue_state(session)
            self.assertEqual(
                [entry["run_id"] for entry in state["queued_entries"]], ["waiter", "member-1"]
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session,
                    run_id="member-1",
                    owner_token="owner-1",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="waiter",
                    owner_token="waiter-owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="waiter",
                    owner_token="waiter-owner",
                    terminal={
                        "status": "failed",
                        "completed_at": now,
                        "error_code": "test_failure",
                        "error_message": "Expected",
                    },
                )
            )
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="member-1",
                    owner_token="owner-1",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="member-1",
                    owner_token="owner-1",
                    terminal={
                        "status": "failed",
                        "completed_at": now,
                        "error_code": "test_failure",
                        "error_message": "Expected",
                    },
                )
            )
            backtest = await self._backtest(session, "backtest-pause")
            self.assertEqual(backtest["status"], "completed")
            events = await crud.list_backtest_events(session, "backtest-pause")
            self.assertEqual(
                [
                    (event["revision"], event["prior_status"], event["status"], event["command_id"])
                    for event in events
                ],
                [
                    (0, None, "queued", None),
                    (1, "queued", "running", None),
                    (2, "running", "pausing", "pause-1"),
                    (3, "pausing", "paused", None),
                    (4, "paused", "running", "resume-1"),
                    (5, "running", "completed", None),
                ],
            )

    async def test_cancellation_during_pause_preserves_the_next_member_until_resume(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            payload = self._payload("backtest-cancel-pause", "member-active")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "member-next", "run_ordinal": 1}
            )
            await crud.create_backtest(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="member-active",
                    owner_token="owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            pause = await self._control(
                session, backtest_id="backtest-cancel-pause", command="pause", command_id="pause-1"
            )
            self.assertEqual(pause["status"], "pausing")
            self.assertEqual(
                await backtest_execution.cancel_run(
                    session, run_id="member-active", requested_at=now
                ),
                "accepted",
            )
            self.assertEqual(
                (await self._backtest(session, "backtest-cancel-pause"))["status"], "pausing"
            )
            self.assertEqual((await backtest_execution.read_slot(session))["owner_token"], "owner")
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="member-active",
                    owner_token="owner",
                    terminal={"status": "cancelled", "completed_at": now},
                )
            )
            self.assertEqual(
                (await self._backtest(session, "backtest-cancel-pause"))["status"], "paused"
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertIsNone((await backtest_execution.read_slot(session))["owner_token"])
            resumed = await self._control(
                session,
                backtest_id="backtest-cancel-pause",
                command="resume",
                command_id="resume-1",
            )
            self.assertEqual(resumed["status"], "running")
            self.assertEqual(
                await backtest_execution.cancel_run(
                    session, run_id="member-next", requested_at=now
                ),
                "accepted",
            )
            self.assertEqual(
                (await self._backtest(session, "backtest-cancel-pause"))["status"], "completed"
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            events = await crud.list_backtest_events(session, "backtest-cancel-pause")
            self.assertEqual(
                [event["event_type"] for event in events],
                [
                    "accepted",
                    "started",
                    "pause",
                    "member_cancel_requested",
                    "paused",
                    "resume",
                    "member_cancelled",
                    "completed",
                ],
            )

    async def test_idle_pause_resume_and_restart_preserve_eligibility(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("backtest-idle", "idle-run"))
            pause = await self._control(
                session, backtest_id="backtest-idle", command="pause", command_id="pause-idle"
            )
            self.assertEqual(pause["status"], "paused")
            no_op = await self._control(
                session, backtest_id="backtest-idle", command="pause", command_id="pause-again"
            )
            self.assertEqual(no_op, pause)
        async with self.sessions() as session:
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertEqual(
                await backtest_execution.reconcile(
                    session,
                    completed_at=now,
                    error_code="worker_interrupted",
                    error_message="Interrupted",
                ),
                0,
            )
            self.assertEqual((await self._backtest(session, "backtest-idle"))["status"], "paused")
            await self._control(
                session, backtest_id="backtest-idle", command="resume", command_id="resume-idle"
            )
            self.assertEqual(
                await self._control(
                    session, backtest_id="backtest-idle", command="pause", command_id="pause-again"
                ),
                pause,
            )
            self.assertEqual(len(await crud.list_backtest_events(session, "backtest-idle")), 3)
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"][0]["run_id"],
                "idle-run",
            )

    async def test_first_claim_after_idle_pause_records_actual_start(self) -> None:
        now = datetime(2026, 9, 27, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("resumed", "first-run"))
            await self._control(session, backtest_id="resumed", command="pause", command_id="pause")
            await self._control(
                session, backtest_id="resumed", command="resume", command_id="resume"
            )
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="first-run",
                    owner_token="owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            saved = await self._backtest(session, "resumed")
            self.assertEqual(saved["started_at"], now)

    async def test_queue_snapshot_excludes_concurrent_backtest_settlement(self) -> None:
        now = datetime(2026, 9, 27, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            payload = self._payload("snapshot", "active")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append({**payload["members"][0], "run_id": "next", "run_ordinal": 1})
            await crud.create_backtest(session, payload)
            await backtest_execution.claim(
                session,
                run_id="active",
                owner_token="owner",
                started_at=now,
                worker_id="worker-test",
            )

        slot_read = asyncio.Event()
        finish_read = asyncio.Event()

        class PausedReader:
            def __init__(self, session):
                self.session = session

            async def execute(self, statement):
                result = await self.session.execute(statement)
                if "fault_message" in str(statement) and "SELECT" in str(statement):
                    slot_read.set()
                    await finish_read.wait()
                return result

        async def read():
            async with self.sessions() as session:
                return await backtest_execution.read_queue_state(PausedReader(session))

        async def settle():
            async with self.sessions() as session:
                return await backtest_execution.settle(
                    session,
                    run_id="active",
                    owner_token="owner",
                    terminal={
                        "status": "failed",
                        "completed_at": now,
                        "error_code": "test_failure",
                        "error_message": "Test failure",
                    },
                )

        reading = asyncio.create_task(read())
        await asyncio.wait_for(slot_read.wait(), timeout=5)
        settling = asyncio.create_task(settle())
        try:
            done, _ = await asyncio.wait({settling}, timeout=0.2)
            self.assertFalse(done, "Settlement must wait for the queue snapshot to finish")
        finally:
            finish_read.set()
            snapshot, settled = await asyncio.wait_for(asyncio.gather(reading, settling), timeout=5)
        self.assertTrue(settled)
        self.assertEqual(snapshot["active_run"]["run_id"], "active")
        self.assertEqual(snapshot["queued_entries"], [])

    async def test_retract_draining_pause_then_final_member_completion_wins(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            payload = self._payload("backtest-retract", "first-member")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "last-member", "run_ordinal": 1}
            )
            await crud.create_backtest(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="first-member",
                    owner_token="first-owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            await self._control(
                session, backtest_id="backtest-retract", command="pause", command_id="first-pause"
            )
            resumed = await self._control(
                session, backtest_id="backtest-retract", command="resume", command_id="retract"
            )
            self.assertEqual(resumed["status"], "running")
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="first-member",
                    owner_token="first-owner",
                    terminal={
                        "status": "failed",
                        "completed_at": now,
                        "error_code": "test_failure",
                        "error_message": "Expected",
                    },
                )
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"][0]["run_id"],
                "last-member",
            )
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="last-member",
                    owner_token="last-owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            final_pause = await self._control(
                session, backtest_id="backtest-retract", command="pause", command_id="final-pause"
            )
            self.assertEqual(final_pause["status"], "pausing")
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="last-member",
                    owner_token="last-owner",
                    terminal={
                        "status": "failed",
                        "completed_at": now,
                        "error_code": "test_failure",
                        "error_message": "Expected",
                    },
                )
            )
            self.assertEqual(
                (await self._backtest(session, "backtest-retract"))["status"], "completed"
            )
            self.assertEqual(
                await self._control(
                    session,
                    backtest_id="backtest-retract",
                    command="pause",
                    command_id="final-pause",
                ),
                final_pause,
            )
            with self.assertRaises(backtest_execution.BacktestCommandConflictError):
                await self._control(
                    session,
                    backtest_id="backtest-retract",
                    command="resume",
                    command_id="after-completion",
                )

    async def test_claim_and_pause_race_respects_the_committed_pause(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("backtest-race", "race-run"))

        async def claim():
            async with self.sessions() as session:
                return await backtest_execution.claim(
                    session,
                    run_id="race-run",
                    owner_token="race-owner",
                    started_at=now,
                    worker_id="worker-test",
                )

        async def pause():
            async with self.sessions() as session:
                return await self._control(
                    session, backtest_id="backtest-race", command="pause", command_id="race-pause"
                )

        claimed, paused = await asyncio.wait_for(asyncio.gather(claim(), pause()), timeout=10)
        async with self.sessions() as session:
            self.assertEqual(paused["status"], "pausing" if claimed else "paused")
            self.assertEqual(
                (await self._backtest(session, "backtest-race"))["status"], paused["status"]
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session,
                    run_id="race-run",
                    owner_token="late-owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )

    @unittest.skipUnless(
        os.getenv("BACKTESTER_TEST_PYTHON"),
        "set BACKTESTER_TEST_PYTHON to run the public mixed-preview acceptance flow",
    )
    async def test_cancel_paused_partly_successful_backtest_preserves_result(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            payload = self._payload("backtest-partial", "first")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "second", "run_ordinal": 1}
            )
            await crud.create_backtest(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session,
                    run_id="first",
                    owner_token="first-owner",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            self.assertTrue(
                await backtest_execution.settle(
                    session,
                    run_id="first",
                    owner_token="first-owner",
                    terminal={
                        "status": "succeeded",
                        "completed_at": now,
                        "result_schema_version": 3,
                        "metrics": {"total_return_pct": 2.5},
                        "diagnostics": {},
                        "replay_descriptor": {"schema_version": 1},
                    },
                )
            )
            self.assertEqual(
                (
                    await self._control(
                        session, backtest_id="backtest-partial", command="pause", command_id="pause"
                    )
                )["status"],
                "paused",
            )
            accepted = await self._control(
                session, backtest_id="backtest-partial", command="cancel", command_id="cancel"
            )
            self.assertEqual((accepted["status"], accepted["command_id"]), ("cancelled", "cancel"))
            backtest = await self._backtest(session, "backtest-partial")
            self.assertEqual(backtest["cancel_requested_at"], backtest["completed_at"])
            self.assertEqual(backtest["cancellation_source"], "user")
            members = await crud.list_backtest_members(session, "backtest-partial")
            self.assertEqual([member["status"] for member in members], ["succeeded", "cancelled"])
            self.assertEqual(members[0]["metrics"], {"total_return_pct": 2.5})
            self.assertEqual(members[1]["cancellation_source"], "backtest")
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertEqual(
                await self._control(
                    session, backtest_id="backtest-partial", command="cancel", command_id="cancel"
                ),
                accepted,
            )
            events = await crud.list_backtest_events(session, "backtest-partial")
            self.assertEqual(
                [event["event_type"] for event in events],
                ["accepted", "started", "pause", "cancel"],
            )

    async def test_cancel_claim_race_and_restart_never_retries_member(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("backtest-race", "only"))

        async def claim():
            async with self.sessions() as session:
                return await backtest_execution.claim(
                    session,
                    run_id="only",
                    owner_token="owner",
                    started_at=now,
                    worker_id="worker-test",
                )

        async def cancel():
            async with self.sessions() as session:
                return await self._control(
                    session, backtest_id="backtest-race", command="cancel", command_id="cancel-race"
                )

        claimed, accepted = await asyncio.wait_for(asyncio.gather(claim(), cancel()), timeout=20)
        async with self.sessions() as session:
            self.assertEqual(accepted["status"], "cancelling" if claimed else "cancelled")
            self.assertEqual(
                (await self._backtest(session, "backtest-race"))["status"], accepted["status"]
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            if claimed:
                self.assertEqual((await backtest_execution.read_slot(session))["run_id"], "only")
                self.assertFalse(
                    await backtest_execution.settle(
                        session,
                        run_id="only",
                        owner_token="owner",
                        terminal={
                            "status": "failed",
                            "completed_at": now,
                            "error_code": "late_result",
                            "error_message": "late",
                        },
                    )
                )
                await session.execute(text("""UPDATE backtest_execution_slot
                    SET run_id=NULL, owner_token=NULL WHERE slot_id=1"""))
                await session.commit()
                self.assertEqual(
                    await backtest_execution.reconcile(
                        session,
                        completed_at=now,
                        error_code="worker_interrupted",
                        error_message="Interrupted",
                    ),
                    1,
                )
                self.assertEqual(
                    await backtest_execution.reconcile(
                        session,
                        completed_at=now,
                        error_code="worker_interrupted",
                        error_message="Interrupted",
                    ),
                    0,
                )
            self.assertEqual(
                (await self._backtest(session, "backtest-race"))["status"], "cancelled"
            )
            self.assertEqual(
                (await crud.list_backtest_members(session, "backtest-race"))[0]["status"],
                "cancelled",
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session,
                    run_id="only",
                    owner_token="retry",
                    started_at=now,
                    worker_id="worker-test",
                )
            )
            events = await crud.list_backtest_events(session, "backtest-race")
            self.assertEqual([event["event_type"] for event in events].count("cancel"), 1)

    async def test_concurrent_same_id_cancel_has_one_event_and_one_receipt(self) -> None:
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("backtest-retry", "only"))

        async def cancel():
            async with self.sessions() as session:
                return await self._control(
                    session, backtest_id="backtest-retry", command="cancel", command_id="same-id"
                )

        first, second = await asyncio.wait_for(asyncio.gather(cancel(), cancel()), timeout=20)
        self.assertEqual(first, second)
        self.assertEqual((first["status"], first["lifecycle_revision"]), ("cancelled", 1))
        async with self.sessions() as session:
            events = await crud.list_backtest_events(session, "backtest-retry")
            self.assertEqual([event["event_type"] for event in events], ["accepted", "cancel"])
            receipts = await session.scalar(text("SELECT COUNT(*) FROM backtest_commands"))
            self.assertEqual(receipts, 1)

    async def test_cancel_receipt_failure_rolls_back_members_and_event(self) -> None:
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
            await crud.create_backtest(session, self._payload("backtest-rollback", "only"))
            await session.execute(text("""CREATE FUNCTION reject_cancel_receipt() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'reject receipt'; END $$"""))
            await session.execute(text("""CREATE TRIGGER reject_cancel_receipt
                BEFORE INSERT ON backtest_commands FOR EACH ROW
                WHEN (NEW.command = 'cancel') EXECUTE FUNCTION reject_cancel_receipt()"""))
            await session.commit()
            with self.assertRaises(Exception) as rejected:
                await self._control(
                    session, backtest_id="backtest-rollback", command="cancel", command_id="reject"
                )
            self.assertIn("reject receipt", str(rejected.exception))
            backtest = await self._backtest(session, "backtest-rollback")
            self.assertEqual((backtest["status"], backtest["lifecycle_revision"]), ("queued", 0))
            self.assertIsNone(backtest["cancel_requested_at"])
            self.assertEqual(
                (await crud.list_backtest_members(session, "backtest-rollback"))[0]["status"],
                "queued",
            )
            self.assertEqual(len(await crud.list_backtest_events(session, "backtest-rollback")), 1)
            self.assertEqual(
                len((await backtest_execution.read_queue_state(session))["queued_entries"]), 1
            )

    async def test_mixed_preview_retry_and_fresh_workspace_read(self) -> None:
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO backtest_execution_slot (slot_id) VALUES (1) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            await session.commit()
        database = make_url(os.environ["BACKTEST_TEST_DATABASE_URL"])
        os.environ.update(
            TIMESCALEDB_USER=database.username or "",
            TIMESCALEDB_PASSWORD=database.password or "",
            TIMESCALEDB_HOST=database.host or "",
            TIMESCALEDB_PORT=str(database.port or 5432),
            TIMESCALEDB_DB=database.database or "",
        )
        import main

        async def isolated_session():
            async with self.sessions() as session:
                yield session

        main.app.dependency_overrides[main.get_db] = isolated_session
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", lifespan="off"))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(server.started)
            env = dict(
                os.environ,
                DATABASE_ACCESSOR_HOST="127.0.0.1",
                DATABASE_ACCESSOR_PORT=str(port),
            )
            env["PYTHONPATH"] = os.pathsep.join(
                [
                    str(ROOT / "backtester"),
                    str(ROOT / "backtester" / "src"),
                    str(ROOT / "libs" / "db_accessor_client"),
                ]
            )
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    os.environ["BACKTESTER_TEST_PYTHON"],
                    "-c",
                    _PUBLIC_FLOW,
                ],
                capture_output=True,
                text=True,
                env=env,
                cwd=ROOT / "backtester",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            self.assertEqual((observed["raw"], observed["ready"], observed["excluded"]), (4, 2, 2))
            self.assertEqual(observed["ordinals"], [0, 1])
            self.assertTrue(observed["requests_match_preview"])
            self.assertEqual(observed["first_backtest_id"], observed["retried_backtest_id"])
            self.assertEqual(observed["first_backtest_id"], observed["reloaded_backtest_id"])
            self.assertEqual(observed["backtest_count"], 1)
            self.assertEqual(observed["member_count"], 2)
            self.assertEqual(observed["event_revisions"], [0])
            self.assertEqual(observed["pause_status"], "paused")
            self.assertEqual(observed["cancel_status"], "cancelled")
            self.assertEqual(observed["cancel_retry"], observed["cancel_response"])
            self.assertEqual(observed["cancelled_member_count"], 2)
            self.assertEqual(observed["cancel_events"], ["accepted", "pause", "cancel"])
            print(
                f"persisted mixed preview: backtest={observed['first_backtest_id']} "
                f"members={observed['member_ids']} ordinals={observed['ordinals']}"
            )
        finally:
            server.should_exit = True
            await task
            listener.close()
            main.app.dependency_overrides.clear()


_PUBLIC_FLOW = """
import json
from uuid import uuid4
from fastapi.testclient import TestClient
from adapters.api.app import create_app
from app.backtests import BacktestService
from app.backtest_runs import BacktestRunService
from app.backtest_definitions import BacktestPreviewService
from db_accessor_client import DatabaseAccessorClient
from tests.adapters.api.test_backtests_routes import _FakeRunRepository
from tests.adapters.api.test_backtests_preview import _definition

definition = _definition()
definition['markets'] = [1]
definition['timeframes'] = ['M1']
definition['allowed_directions'] = ['long_only']
definition['parameter_axes'] = {
    'fast_window': {'mode': 'range', 'start': 4, 'stop': 7, 'step': 1},
    'slow_window': {'mode': 'constant', 'value': 6},
    'quantity': {'mode': 'constant', 'value': 0.1},
}
preview_service = BacktestPreviewService(
    markets=lambda: [{'symbol_id': 1, 'symbol': 'EURUSD', 'exchange': 'FX'}],
    max_candidate_count=100,
)
def app():
    return create_app(
        service=BacktestRunService(repository=_FakeRunRepository()),
        preview_service=preview_service,
        backtest_service=BacktestService(
            preview=preview_service, client_factory=DatabaseAccessorClient,
        ),
    )
with TestClient(app()) as client:
    preview_response = client.post('/backtests/preview', json=definition)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    ready = [row for row in preview['candidates'] if row['status'] == 'ready']
    request = {**definition, 'submission_id': str(uuid4())}
    first = client.post('/backtests', json=request)
    retry = client.post('/backtests', json=request)
    assert first.status_code == retry.status_code == 202, (first.text, retry.text)
    first_backtest_id = first.json()['backtest_id']
    retried_backtest_id = retry.json()['backtest_id']
with TestClient(app()) as workspace:
    backtests = workspace.get('/backtests').json()
    detail = workspace.get(f'/backtests/{first_backtest_id}').json()
    members = workspace.get(f'/backtests/{first_backtest_id}/runs').json()
    events = workspace.get(f'/backtests/{first_backtest_id}/events').json()
    assert all(isinstance(value, list) for value in (backtests, members, events))
    pause = workspace.post(f'/backtests/{first_backtest_id}/pause',
                           json={'command_id': str(uuid4())})
    assert pause.status_code == 200, pause.text
    cancel_id = str(uuid4())
    cancel = workspace.post(f'/backtests/{first_backtest_id}/cancel',
                            json={'command_id': cancel_id})
    retry = workspace.post(f'/backtests/{first_backtest_id}/cancel',
                           json={'command_id': cancel_id})
    assert cancel.status_code == retry.status_code == 200, (cancel.text, retry.text)
    assert cancel.json()['command_id'] == cancel_id
    cancelled_detail = workspace.get(f'/backtests/{first_backtest_id}').json()
    cancelled_members = workspace.get(f'/backtests/{first_backtest_id}/runs').json()
    cancelled_events = workspace.get(f'/backtests/{first_backtest_id}/events').json()
    print(json.dumps({
        'raw': preview['raw_count'], 'ready': preview['ready_count'],
        'excluded': preview['excluded_count'],
        'first_backtest_id': first_backtest_id, 'retried_backtest_id': retried_backtest_id,
        'reloaded_backtest_id': detail['backtest_id'], 'backtest_count': len(backtests),
        'member_count': len(members),
        'member_ids': [member['run_id'] for member in members],
        'ordinals': [member['run_ordinal'] for member in members],
        'requests_match_preview': [member['request'] for member in members]
            == [row['request'] for row in ready],
        'event_revisions': [event['revision'] for event in events],
        'pause_status': pause.json()['status'], 'cancel_status': cancelled_detail['status'],
        'cancel_response': cancel.json(), 'cancel_retry': retry.json(),
        'cancelled_member_count': sum(member['status'] == 'cancelled'
                                      for member in cancelled_members),
        'cancel_events': [event['event_type'] for event in cancelled_events],
    }))
"""
