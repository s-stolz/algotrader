"""Opt-in PostgreSQL transaction coverage for Backtest Batch submission races."""

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
from app.models import backtest_batch_events, backtest_batches, backtest_runs, metadata
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.getenv("BACKTEST_BATCH_TEST_DATABASE_URL"),
    "set BACKTEST_BATCH_TEST_DATABASE_URL to a local PostgreSQL database",
)
class BacktestBatchPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.schema = f"batch_test_{uuid4().hex}"
        url = os.environ["BACKTEST_BATCH_TEST_DATABASE_URL"]
        self.admin_engine = create_async_engine(url)
        async with self.admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(
            url, connect_args={"server_settings": {"search_path": self.schema}}
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        async with self.admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin_engine.dispose()

    def _payload(self, batch_id: str, run_id: str, *, definition: str = "original") -> dict:
        return {
            "batch_id": batch_id,
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
                    "member_ordinal": 0,
                    "request_schema_version": 3,
                    "request": {"symbols": ["EURUSD"], "timeframe": "M1"},
                }
            ],
        }

    async def _control(self, session, *, batch_id: str, command: str, command_id: str) -> dict:
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
        }[command]
        result = await backtest_execution.control_batch(
            session, batch_id=batch_id, command=command, command_id=command_id, policy=policy
        )
        assert result is not None
        return result

    async def _batch(self, session, batch_id: str) -> dict:
        result = await crud.get_backtest_batch(session, batch_id)
        assert result is not None
        return result

    async def test_simultaneous_same_id_transactions_return_one_complete_batch(self) -> None:
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

        async def submit(batch_id: str, run_id: str):
            async with self.sessions() as session:
                return await crud.create_backtest_batch(
                    RacingSession(session), self._payload(batch_id, run_id)
                )

        first, second = await asyncio.wait_for(
            asyncio.gather(
                submit("batch-first", "run-first"), submit("batch-second", "run-second")
            ),
            timeout=20,
        )
        assert first is not None and second is not None
        self.assertEqual(first["batch_id"], second["batch_id"])
        async with self.sessions() as session:
            self.assertEqual(
                await session.scalar(select(func.count()).select_from(backtest_batches)), 1
            )
            self.assertEqual(
                await session.scalar(select(func.count()).select_from(backtest_runs)), 1
            )
            self.assertEqual(
                await session.scalar(select(func.count()).select_from(backtest_batch_events)), 1
            )
            members = await crud.list_backtest_batch_members(session, first["batch_id"])
            self.assertEqual(
                [(row["run_id"], row["member_ordinal"]) for row in members],
                [("run-first" if first["batch_id"] == "batch-first" else "run-second", 0)],
            )
            with self.assertRaises(crud.BatchSubmissionConflictError):
                await crud.create_backtest_batch(
                    session, self._payload("batch-conflict", "run-conflict", definition="changed")
                )

    async def test_pause_drains_active_work_and_resume_rejoins_behind_waiter(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(text("INSERT INTO backtest_execution_slot (slot_id) VALUES (1)"))
            await session.commit()
            payload = self._payload("batch-pause", "member-0")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "member-1", "member_ordinal": 1}
            )
            await crud.create_backtest_batch(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session, run_id="member-0", owner_token="owner-0", started_at=now
                )
            )
            pause = await self._control(
                session, batch_id="batch-pause", command="pause", command_id="pause-1"
            )
            self.assertEqual((pause["status"], pause["lifecycle_revision"]), ("pausing", 2))
            self.assertEqual(
                await self._control(
                    session, batch_id="batch-pause", command="pause", command_id="pause-1"
                ),
                pause,
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session, run_id="member-1", owner_token="owner-1", started_at=now
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
            batch = await self._batch(session, "batch-pause")
            self.assertEqual((batch["status"], batch["lifecycle_revision"]), ("paused", 3))
            state = await backtest_execution.read_queue_state(session)
            self.assertEqual(state["queued_entries"], [])
            await session.execute(
                text("""INSERT INTO backtest_runs
                (run_id, status, submitted_at, request_schema_version, request)
                VALUES ('waiter', 'queued', :now, 2, '{}'::jsonb)"""),
                {"now": now},
            )
            await session.execute(
                text("INSERT INTO backtest_queue_turns (run_id) VALUES ('waiter')")
            )
            await session.commit()
            with self.assertRaises(backtest_execution.BatchCommandConflictError):
                await self._control(
                    session, batch_id="batch-pause", command="resume", command_id="pause-1"
                )
            resumed = await self._control(
                session, batch_id="batch-pause", command="resume", command_id="resume-1"
            )
            self.assertEqual((resumed["status"], resumed["lifecycle_revision"]), ("running", 4))
            state = await backtest_execution.read_queue_state(session)
            self.assertEqual(
                [entry["run_id"] for entry in state["queued_entries"]], ["waiter", "member-1"]
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session, run_id="member-1", owner_token="owner-1", started_at=now
                )
            )
            self.assertTrue(
                await backtest_execution.claim(
                    session, run_id="waiter", owner_token="waiter-owner", started_at=now
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
                    session, run_id="member-1", owner_token="owner-1", started_at=now
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
            batch = await self._batch(session, "batch-pause")
            self.assertEqual(batch["status"], "completed")
            events = await crud.list_backtest_batch_events(session, "batch-pause")
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
            await session.execute(text("INSERT INTO backtest_execution_slot (slot_id) VALUES (1)"))
            await session.commit()
            payload = self._payload("batch-cancel-pause", "member-active")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "member-next", "member_ordinal": 1}
            )
            await crud.create_backtest_batch(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session, run_id="member-active", owner_token="owner", started_at=now
                )
            )
            pause = await self._control(
                session, batch_id="batch-cancel-pause", command="pause", command_id="pause-1"
            )
            self.assertEqual(pause["status"], "pausing")
            self.assertEqual(
                await backtest_execution.cancel_run(
                    session, run_id="member-active", requested_at=now
                ),
                "accepted",
            )
            self.assertEqual(
                (await self._batch(session, "batch-cancel-pause"))["status"], "pausing"
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
            self.assertEqual((await self._batch(session, "batch-cancel-pause"))["status"], "paused")
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertIsNone((await backtest_execution.read_slot(session))["owner_token"])
            resumed = await self._control(
                session, batch_id="batch-cancel-pause", command="resume", command_id="resume-1"
            )
            self.assertEqual(resumed["status"], "running")
            self.assertEqual(
                await backtest_execution.cancel_run(
                    session, run_id="member-next", requested_at=now
                ),
                "accepted",
            )
            self.assertEqual(
                (await self._batch(session, "batch-cancel-pause"))["status"], "completed"
            )
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            events = await crud.list_backtest_batch_events(session, "batch-cancel-pause")
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
            await session.execute(text("INSERT INTO backtest_execution_slot (slot_id) VALUES (1)"))
            await session.commit()
            await crud.create_backtest_batch(session, self._payload("batch-idle", "idle-run"))
            pause = await self._control(
                session, batch_id="batch-idle", command="pause", command_id="pause-idle"
            )
            self.assertEqual(pause["status"], "paused")
            no_op = await self._control(
                session, batch_id="batch-idle", command="pause", command_id="pause-again"
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
            self.assertEqual((await self._batch(session, "batch-idle"))["status"], "paused")
            await self._control(
                session, batch_id="batch-idle", command="resume", command_id="resume-idle"
            )
            self.assertEqual(
                await self._control(
                    session, batch_id="batch-idle", command="pause", command_id="pause-again"
                ),
                pause,
            )
            self.assertEqual(len(await crud.list_backtest_batch_events(session, "batch-idle")), 3)
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"][0]["run_id"],
                "idle-run",
            )

    async def test_retract_draining_pause_then_final_member_completion_wins(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(text("INSERT INTO backtest_execution_slot (slot_id) VALUES (1)"))
            await session.commit()
            payload = self._payload("batch-retract", "first-member")
            payload["raw_count"] = payload["member_count"] = 2
            payload["members"].append(
                {**payload["members"][0], "run_id": "last-member", "member_ordinal": 1}
            )
            await crud.create_backtest_batch(session, payload)
            self.assertTrue(
                await backtest_execution.claim(
                    session, run_id="first-member", owner_token="first-owner", started_at=now
                )
            )
            await self._control(
                session, batch_id="batch-retract", command="pause", command_id="first-pause"
            )
            resumed = await self._control(
                session, batch_id="batch-retract", command="resume", command_id="retract"
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
                    session, run_id="last-member", owner_token="last-owner", started_at=now
                )
            )
            final_pause = await self._control(
                session, batch_id="batch-retract", command="pause", command_id="final-pause"
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
            self.assertEqual((await self._batch(session, "batch-retract"))["status"], "completed")
            self.assertEqual(
                await self._control(
                    session, batch_id="batch-retract", command="pause", command_id="final-pause"
                ),
                final_pause,
            )
            with self.assertRaises(backtest_execution.BatchCommandConflictError):
                await self._control(
                    session,
                    batch_id="batch-retract",
                    command="resume",
                    command_id="after-completion",
                )

    async def test_claim_and_pause_race_respects_the_committed_pause(self) -> None:
        now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        async with self.sessions() as session:
            await session.execute(text("INSERT INTO backtest_execution_slot (slot_id) VALUES (1)"))
            await session.commit()
            await crud.create_backtest_batch(session, self._payload("batch-race", "race-run"))

        async def claim():
            async with self.sessions() as session:
                return await backtest_execution.claim(
                    session, run_id="race-run", owner_token="race-owner", started_at=now
                )

        async def pause():
            async with self.sessions() as session:
                return await self._control(
                    session, batch_id="batch-race", command="pause", command_id="race-pause"
                )

        claimed, paused = await asyncio.wait_for(asyncio.gather(claim(), pause()), timeout=10)
        async with self.sessions() as session:
            self.assertEqual(paused["status"], "pausing" if claimed else "paused")
            self.assertEqual((await self._batch(session, "batch-race"))["status"], paused["status"])
            self.assertEqual(
                (await backtest_execution.read_queue_state(session))["queued_entries"], []
            )
            self.assertFalse(
                await backtest_execution.claim(
                    session, run_id="race-run", owner_token="late-owner", started_at=now
                )
            )

    @unittest.skipUnless(
        os.getenv("BACKTESTER_TEST_PYTHON"),
        "set BACKTESTER_TEST_PYTHON to run the public mixed-preview acceptance flow",
    )
    async def test_mixed_preview_retry_and_fresh_workspace_read(self) -> None:
        database = make_url(os.environ["BACKTEST_BATCH_TEST_DATABASE_URL"])
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
                BACKTESTER_BATCH_ACCEPTANCE_ENABLED="1",
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
            self.assertEqual(observed["first_batch_id"], observed["retried_batch_id"])
            self.assertEqual(observed["first_batch_id"], observed["reloaded_batch_id"])
            self.assertEqual(observed["batch_count"], 1)
            self.assertEqual(observed["member_count"], 2)
            self.assertEqual(observed["event_revisions"], [0])
            print(
                f"persisted mixed preview: batch={observed['first_batch_id']} "
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
from app.backtest_batches import BacktestBatchService
from app.backtest_runs import BacktestRunService
from app.sweeps import SweepPreviewService
from db_accessor_client import DatabaseAccessorClient
from tests.adapters.api.test_backtests_routes import _FakeRunRepository
from tests.adapters.api.test_sweep_preview_routes import _definition

definition = _definition()
definition['markets'] = [1]
definition['timeframes'] = ['M1']
definition['allowed_directions'] = ['long_only']
definition['parameter_axes'] = {
    'fast_window': {'mode': 'range', 'start': 4, 'stop': 7, 'step': 1},
    'slow_window': {'mode': 'constant', 'value': 6},
    'quantity': {'mode': 'constant', 'value': 0.1},
}
preview_service = SweepPreviewService(
    markets=lambda: [{'symbol_id': 1, 'symbol': 'EURUSD', 'exchange': 'FX'}],
    max_candidate_count=100,
)
def app():
    return create_app(
        service=BacktestRunService(repository=_FakeRunRepository()),
        preview_service=preview_service,
        batch_service=BacktestBatchService(
            preview=preview_service, client_factory=DatabaseAccessorClient,
        ),
    )
with TestClient(app()) as client:
    preview_response = client.post('/backtests/sweeps/preview', json=definition)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    ready = [row for row in preview['candidates'] if row['status'] == 'ready']
    request = {**definition, 'submission_id': str(uuid4())}
    first = client.post('/backtests/batches', json=request)
    retry = client.post('/backtests/batches', json=request)
    assert first.status_code == retry.status_code == 202, (first.text, retry.text)
    first_batch_id = first.json()['batch_id']
    retried_batch_id = retry.json()['batch_id']
with TestClient(app()) as workspace:
    batches = workspace.get('/backtests/batches').json()
    detail = workspace.get(f'/backtests/batches/{first_batch_id}').json()
    members = workspace.get(f'/backtests/batches/{first_batch_id}/members').json()
    events = workspace.get(f'/backtests/batches/{first_batch_id}/events').json()
    assert all(isinstance(value, list) for value in (batches, members, events))
    print(json.dumps({
        'raw': preview['raw_count'], 'ready': preview['ready_count'],
        'excluded': preview['excluded_count'],
        'first_batch_id': first_batch_id, 'retried_batch_id': retried_batch_id,
        'reloaded_batch_id': detail['batch_id'], 'batch_count': len(batches),
        'member_count': len(members),
        'member_ids': [member['run_id'] for member in members],
        'ordinals': [member['member_ordinal'] for member in members],
        'requests_match_preview': [member['request'] for member in members]
            == [row['request'] for row in ready],
        'event_revisions': [event['revision'] for event in events],
    }))
"""
