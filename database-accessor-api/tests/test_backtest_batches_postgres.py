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
from app import crud
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
