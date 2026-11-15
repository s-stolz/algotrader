import json
import os
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import ValidationError
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("TIMESCALEDB_USER", "test")
os.environ.setdefault("TIMESCALEDB_PASSWORD", "test")
os.environ.setdefault("TIMESCALEDB_HOST", "localhost")
os.environ.setdefault("TIMESCALEDB_PORT", "5432")
os.environ.setdefault("TIMESCALEDB_DB", "test")

import main  # noqa: E402
from app import backtest_execution, crud  # noqa: E402
from app.models import (  # noqa: E402
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
from app.schemas import (  # noqa: E402
    BacktestClosedTradeIn,
    BacktestCommandIn,
    BacktestControlPolicyIn,
    BacktestCreateIn,
    BacktestExecutionClaimIn,
    BacktestExecutionReconcileIn,
    BacktestExecutionSettleIn,
    BacktestExecutionSlotOut,
    BacktestFillIn,
    BacktestRequestPayload,
    BacktestRunOut,
    EquityReplayDescriptor,
)


class InMemoryAsyncSession:
    def __init__(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()
        sqlite_connection = cast(sqlite3.Connection, self.connection.connection.driver_connection)
        sqlite_connection.create_function(
            "clock_timestamp", 0, lambda: datetime.now(timezone.utc).isoformat(" ")
        )
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


def _seed_execution_slot(session: InMemoryAsyncSession) -> None:
    session.connection.execute(insert(backtest_execution_slot).values(slot_id=1))
    session.connection.commit()


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
            "allowed_directions": "long_and_short",
            "trade_accounting_policy": "average_cost",
            "gap_policy": "error",
            "intrabar_exit_policy": "take_profit_first",
            "commission_bps": 1.5,
            "slippage_bps": 0.75,
        },
        "run_metadata": {
            "source": "queued-smoke",
            "tags": ["durable", "api"],
        },
    }
    payload.update(overrides)
    return payload


def _replay_descriptor() -> EquityReplayDescriptor:
    return EquityReplayDescriptor(
        **{
            "schema_version": 1,
            "fingerprint_algorithm": "sha256-ts-close-v1",
            "fingerprint_digest": "0" * 64,
            "source_point_count": 1,
            "first_timestamp_ms": 1714525200000,
            "last_timestamp_ms": 1714525200000,
        }
    )


def _run_payload(**overrides):
    payload = {
        "run_id": "run-queued-1",
        "backtest_id": "backtest-1",
        "run_ordinal": 0,
        "status": "queued",
        "submitted_at": datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "request_schema_version": 3,
        "request": _request_payload(),
        "result_schema_version": None,
        "metrics": None,
        "diagnostics": None,
        "fills": [],
        "trades": [],
    }
    payload.update(overrides)
    payload["request"]["strategy"]["strategy_version"] = 1
    if payload["status"] == "succeeded" and "replay_descriptor" not in overrides:
        payload["replay_descriptor"] = _replay_descriptor().model_dump()
    return payload


class BacktestRunApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = InMemoryAsyncSession()

    def tearDown(self):
        self.session.close()

    @property
    def db(self) -> AsyncSession:
        return cast(AsyncSession, self.session)

    async def test_execution_controls_round_trip_through_storage_http(self):
        async def database():
            yield self.db

        schedule = {
            "entry_start_minute_utc": 0,
            "last_entry_minute_utc": 720,
            "exit_minute_utc": 1020,
        }
        main.app.dependency_overrides[main.get_db] = database
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                for index, controls in enumerate(
                    (
                        {},
                        {"daily_schedule": schedule},
                        {"max_entries_per_day": 1},
                        {"daily_schedule": schedule, "max_entries_per_day": 2},
                        {
                            "execution_mode": "orders",
                            "candle_quote": "mid",
                            "spread": 0.0002,
                            "max_position_quantity": 10_000,
                            "intrabar_execution_policy": "optimistic",
                        },
                        {"execution_mode": "orders", "candle_quote": "bid", "spread": 0.0},
                    )
                ):
                    with self.subTest(controls=controls):
                        payload = self._backtest_payload(
                            backtest_id=f"controls-{index}", submission_id=f"controls-{index}"
                        )
                        payload["accepted_at"] = payload["accepted_at"].isoformat()
                        member = payload["members"][0]
                        member["run_id"] = f"execution-controls-{index}"
                        member["request"]["execution"].update(controls)
                        if index == 4:
                            member["request"]["market_min_move"] = 0.00001
                        response = await client.post("/backtests", json=payload)
                        self.assertEqual(response.status_code, 201, response.text)
                        saved = await client.get(f"/backtest-runs/execution-controls-{index}")
                        self.assertEqual(saved.status_code, 200)
                        self.assertEqual(
                            saved.json()["request"]["execution"], member["request"]["execution"]
                        )
                        self.assertEqual(saved.json()["request"], member["request"])
        finally:
            main.app.dependency_overrides.pop(main.get_db, None)

    def test_execution_controls_reject_invalid_values_and_omit_unlimited_defaults(self):
        for controls in (
            {"execution_mode": "orders"},
            {"execution_mode": "orders", "candle_quote": "last"},
            {"spread": -0.1},
            {"spread": float("nan")},
            {"max_position_quantity": 0},
            {"intrabar_execution_policy": "guess"},
            {"max_entries_per_day": 0},
            {"max_entries_per_day": True},
            {"max_entries_per_day": 1.5},
            {"max_entries_per_day": "2"},
            {
                "daily_schedule": {
                    "entry_start_minute_utc": 100,
                    "last_entry_minute_utc": 99,
                    "exit_minute_utc": 200,
                }
            },
            {
                "daily_schedule": {
                    "entry_start_minute_utc": 0,
                    "last_entry_minute_utc": 99,
                    "exit_minute_utc": 1440,
                }
            },
            {
                "daily_schedule": {
                    "entry_start_minute_utc": False,
                    "last_entry_minute_utc": 99,
                    "exit_minute_utc": 200,
                }
            },
            {
                "daily_schedule": {
                    "entry_start_minute_utc": 0,
                    "last_entry_minute_utc": 99,
                    "exit_minute_utc": 200,
                    "unknown": 1,
                }
            },
        ):
            with self.subTest(controls=controls), self.assertRaises(ValueError):
                payload = _request_payload()
                payload["execution"].update(controls)
                BacktestRequestPayload(**payload)
        original = _request_payload()
        payload = _request_payload()
        payload["execution"].update(daily_schedule=None, max_entries_per_day=None)
        self.assertEqual(BacktestRequestPayload(**payload).model_dump(), original)

    def _backtest_payload(self, **overrides):
        request = _request_payload()
        request["strategy"]["strategy_version"] = 1
        payload = {
            "backtest_id": "backtest-1",
            "submission_id": "submission-1",
            "accepted_at": datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            "definition_schema_version": 1,
            "accepted_definition": {"schema_version": 1, "selections": {"markets": [1]}},
            "strategy_metadata": {"strategy_id": "sma_crossover", "strategy_version": 1},
            "raw_count": 2,
            "member_count": 1,
            "excluded_count": 1,
            "members": [
                {
                    "run_id": "member-1",
                    "run_ordinal": 0,
                    "request_schema_version": 3,
                    "request": request,
                }
            ],
        }
        payload.update(overrides)
        return payload

    async def _cancel_backtest(self, command_id: str):
        return await main.control_backtest(
            "backtest-1",
            "cancel",
            BacktestCommandIn(
                command_id=command_id,
                policy=BacktestControlPolicyIn(
                    **{
                        "accepted_statuses": ["queued", "running", "pausing", "paused"],
                        "effective_statuses": ["cancelling", "cancelled"],
                        "active_status": "cancelling",
                        "idle_status": "cancelled",
                        "queue_action": "remove",
                    }
                ),
            ),
            db=self.db,
        )

    async def test_cancel_backtest_from_queued_is_atomic_and_identity_stable(self):
        from fastapi import HTTPException

        payload = self._backtest_payload()
        payload.update(raw_count=2, member_count=2, excluded_count=0)
        payload["members"].append({**payload["members"][0], "run_id": "member-2", "run_ordinal": 1})
        await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        _seed_execution_slot(self.session)
        accepted = await self._cancel_backtest("cancel-1")
        self.assertEqual(
            accepted,
            {
                "backtest_id": "backtest-1",
                "command_id": "cancel-1",
                "status": "cancelled",
                "lifecycle_revision": 1,
            },
        )
        backtest = await main.get_backtest("backtest-1", db=self.db)
        assert backtest is not None
        self.assertEqual(backtest["completed_at"], backtest["cancel_requested_at"])
        self.assertEqual(backtest["cancellation_source"], "user")
        members = await main.list_backtest_members("backtest-1", db=self.db)
        self.assertEqual([member["status"] for member in members], ["cancelled", "cancelled"])
        self.assertEqual({member["cancellation_source"] for member in members}, {"backtest"})
        self.assertEqual((await main.get_backtest_queue_state(db=self.db))["queued_entries"], [])
        self.assertEqual(await self._cancel_backtest("cancel-1"), accepted)
        self.assertEqual((await self._cancel_backtest("cancel-2"))["lifecycle_revision"], 1)
        events = await main.list_backtest_events("backtest-1", db=self.db)
        self.assertEqual(
            [(event["revision"], event["event_type"], event["command_id"]) for event in events],
            [(0, "accepted", None), (1, "cancel", "cancel-1")],
        )
        with self.assertRaises(HTTPException) as missing:
            await main.control_backtest(
                "missing",
                "cancel",
                BacktestCommandIn(
                    command_id="missing",
                    policy=BacktestControlPolicyIn(
                        **{
                            "accepted_statuses": ["queued"],
                            "effective_statuses": ["cancelled"],
                            "active_status": "cancelling",
                            "idle_status": "cancelled",
                            "queue_action": "remove",
                        }
                    ),
                ),
                db=self.db,
            )
        self.assertEqual(missing.exception.status_code, 404)

    async def test_cancel_backtest_keeps_prior_success_and_active_slot_until_settlement(self):
        payload = self._backtest_payload()
        payload.update(raw_count=3, member_count=3, excluded_count=0)
        payload["members"].extend(
            [
                {
                    **payload["members"][0],
                    "run_id": f"member-{ordinal}",
                    "run_ordinal": ordinal - 1,
                }
                for ordinal in (2, 3)
            ]
        )
        await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        _seed_execution_slot(self.session)
        at = datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc)
        self.assertTrue(
            await backtest_execution.claim(
                self.db,
                run_id="member-1",
                owner_token="owner-1",
                started_at=at,
                worker_id="worker-test",
            )
        )
        self.assertTrue(
            await backtest_execution.settle(
                self.db,
                run_id="member-1",
                owner_token="owner-1",
                terminal={
                    "status": "succeeded",
                    "completed_at": at,
                    "result_schema_version": 3,
                    "metrics": {"profit_factor": None, "total_return_pct": 2.5},
                    "diagnostics": {"source": "prior-success"},
                    "replay_descriptor": _replay_descriptor().model_dump(),
                },
            )
        )
        self.assertTrue(
            await backtest_execution.claim(
                self.db,
                run_id="member-2",
                owner_token="owner-2",
                started_at=at,
                worker_id="worker-test",
            )
        )
        accepted = await self._cancel_backtest("cancel-running")
        self.assertEqual(accepted["status"], "cancelling")
        backtest = await main.get_backtest("backtest-1", db=self.db)
        assert backtest is not None
        self.assertIsNone(backtest["completed_at"])
        self.assertIsNotNone(backtest["cancel_requested_at"])
        members = await main.list_backtest_members("backtest-1", db=self.db)
        self.assertEqual(
            [run["status"] for run in members], ["succeeded", "cancelling", "cancelled"]
        )
        self.assertEqual(members[0]["metrics"], {"profit_factor": None, "total_return_pct": 2.5})
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "member-2")
        self.assertEqual((await main.get_backtest_queue_state(db=self.db))["queued_entries"], [])
        self.assertFalse(
            await backtest_execution.settle(
                self.db,
                run_id="member-2",
                owner_token="owner-2",
                terminal={
                    "status": "succeeded",
                    "completed_at": at,
                    "result_schema_version": 3,
                    "metrics": {"profit_factor": None, "total_return_pct": 99},
                },
            )
        )
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "member-2")
        self.assertTrue(
            await backtest_execution.settle(
                self.db,
                run_id="member-2",
                owner_token="owner-2",
                terminal={"status": "cancelled", "completed_at": at},
            )
        )
        backtest = await main.get_backtest("backtest-1", db=self.db)
        assert backtest is not None
        self.assertEqual(backtest["status"], "cancelled")
        self.assertIsNotNone(backtest["completed_at"])
        self.assertEqual((await self._cancel_backtest("cancel-running"))["status"], "cancelling")
        self.assertEqual(
            (await main.get_backtest_run("member-1", db=self.db))["metrics"],
            {"profit_factor": None, "total_return_pct": 2.5},
        )

    async def test_cancel_pausing_backtest_dominates_later_resume_and_normal_result(self):
        from fastapi import HTTPException

        payload = self._backtest_payload()
        payload.update(raw_count=2, member_count=2, excluded_count=0)
        payload["members"].append({**payload["members"][0], "run_id": "member-2", "run_ordinal": 1})
        await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        _seed_execution_slot(self.session)
        at = datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc)
        self.assertTrue(
            await backtest_execution.claim(
                self.db,
                run_id="member-1",
                owner_token="owner",
                started_at=at,
                worker_id="worker-test",
            )
        )
        pause = await main.control_backtest(
            "backtest-1",
            "pause",
            BacktestCommandIn(
                command_id="pause",
                policy=BacktestControlPolicyIn(
                    accepted_statuses=["queued", "running"],
                    effective_statuses=["pausing", "paused"],
                    active_status="pausing",
                    idle_status="paused",
                    queue_action="remove",
                ),
            ),
            db=self.db,
        )
        self.assertEqual(pause["status"], "pausing")
        accepted = await self._cancel_backtest("cancel")
        self.assertEqual(accepted["status"], "cancelling")
        with self.assertRaises(HTTPException) as conflict:
            await main.control_backtest(
                "backtest-1",
                "resume",
                BacktestCommandIn(
                    command_id="resume",
                    policy=BacktestControlPolicyIn(
                        accepted_statuses=["pausing", "paused"],
                        effective_statuses=["queued", "running"],
                        active_status="running",
                        idle_status="running",
                        queue_action="append",
                    ),
                ),
                db=self.db,
            )
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertFalse(
            await backtest_execution.settle(
                self.db,
                run_id="member-1",
                owner_token="owner",
                terminal={
                    "status": "failed",
                    "completed_at": at,
                    "error_code": "late",
                    "error_message": "late",
                },
            )
        )
        self.assertTrue(
            await backtest_execution.settle(
                self.db,
                run_id="member-1",
                owner_token="owner",
                terminal={"status": "cancelled", "completed_at": at},
            )
        )
        self.assertEqual((await main.get_backtest("backtest-1", db=self.db))["status"], "cancelled")
        self.assertEqual((await self._cancel_backtest("cancel")), accepted)

    def test_market_increment_validation_and_legacy_omission(self):
        original = _request_payload()
        self.assertEqual(BacktestRequestPayload(**original).model_dump(), original)
        self.assertEqual(
            BacktestRequestPayload(**{**original, "market_min_move": None}).model_dump(), original
        )
        for invalid in (0, -1, True, "0.01", float("nan"), float("inf")):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                BacktestRequestPayload(**{**original, "market_min_move": invalid})

    async def test_backtest_acceptance_preserves_market_price_increment(self):
        payload = self._backtest_payload()
        payload["members"][0]["request"]["market_min_move"] = 0.00001
        accepted = BacktestCreateIn(**payload)
        await main.create_backtest(accepted, db=self.db)
        members = await main.list_backtest_members("backtest-1", db=self.db)
        self.assertEqual(members[0]["request"]["market_min_move"], 0.00001)
        stored = BacktestRunOut(**members[0]).model_dump(mode="json")
        self.assertEqual(stored["request"]["market_min_move"], 0.00001)

    async def test_backtest_acceptance_retry_and_ordered_inspection(self):
        payload = self._backtest_payload()
        first = await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        retried = await main.create_backtest(
            BacktestCreateIn(**{**payload, "backtest_id": "discarded-id"}), db=self.db
        )
        assert first is not None and retried is not None
        self.assertEqual(first["backtest_id"], retried["backtest_id"])
        self.assertEqual(first["status"], "queued")
        self.assertEqual(first["lifecycle_revision"], 0)
        members = await main.list_backtest_members("backtest-1", db=self.db)
        self.assertEqual(
            [(run["run_id"], run["run_ordinal"]) for run in members], [("member-1", 0)]
        )
        self.assertEqual(members[0]["request"], payload["members"][0]["request"])
        events = await main.list_backtest_events("backtest-1", db=self.db)
        self.assertEqual(
            [(event["revision"], event["event_type"]) for event in events], [(0, "accepted")]
        )
        self.assertIsNone(events[0]["prior_status"])
        self.assertEqual(len(await main.list_backtest_runs(db=self.db)), 1)

    async def test_backtest_retry_after_concurrent_identity_winner(self):
        from app import crud

        winner = self._backtest_payload()
        retry = self._backtest_payload(backtest_id="discarded-id")

        class ConcurrentWinnerSession:
            def __init__(self, session):
                self.session = session
                self.raced = False

            async def execute(self, statement, params=None):
                if (
                    getattr(getattr(statement, "table", None), "name", None) == "backtests"
                    and not self.raced
                ):
                    self.raced = True
                    await crud.create_backtest(
                        self.session, BacktestCreateIn(**winner).model_dump()
                    )
                    raise IntegrityError(
                        "INSERT backtests", {}, Exception("duplicate submission_id")
                    )
                return await self.session.execute(statement, params)

            async def commit(self):
                await self.session.commit()

            async def rollback(self):
                await self.session.rollback()

        racing_session = ConcurrentWinnerSession(self.session)
        accepted = await crud.create_backtest(
            cast(AsyncSession, racing_session), BacktestCreateIn(**retry).model_dump()
        )
        assert accepted is not None
        self.assertTrue(racing_session.raced)
        self.assertEqual(accepted["backtest_id"], winner["backtest_id"])
        self.assertEqual(len(await main.list_backtests(db=self.db)), 1)
        self.assertEqual(len(await main.list_backtest_members("backtest-1", db=self.db)), 1)
        self.assertEqual(len(await main.list_backtest_events("backtest-1", db=self.db)), 1)

    async def test_backtest_identity_conflict_and_rollback(self):
        from app import crud
        from fastapi import HTTPException

        payload = self._backtest_payload()
        await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        changed = self._backtest_payload(
            backtest_id="backtest-2", accepted_definition={"changed": True}
        )
        with self.assertRaises(HTTPException) as conflict:
            await main.create_backtest(BacktestCreateIn(**changed), db=self.db)
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(len(await main.list_backtests(db=self.db)), 1)

        invalid = self._backtest_payload(backtest_id="backtest-3", submission_id="submission-3")
        invalid["members"][0]["run_id"] = "member-1"
        with self.assertRaises(IntegrityError):
            await crud.create_backtest(self.db, BacktestCreateIn(**invalid).model_dump())
        self.assertIsNone(await crud.get_backtest(self.db, "backtest-3"))

    async def test_backtest_delete_rechecks_state_and_removes_members_events_and_commands(self):
        _seed_execution_slot(self.session)
        await main.create_backtest(BacktestCreateIn(**self._backtest_payload()), db=self.db)
        for status in ("queued", "running", "pausing", "paused", "cancelling"):
            await self.session.execute(update(backtests).values(status=status))
            await self.session.commit()
            with self.assertRaises(main.HTTPException) as conflict:
                await main.delete_backtest("backtest-1", db=self.db)
            self.assertEqual(conflict.exception.status_code, 409)
            self.assertIsNotNone(await crud.get_backtest(self.db, "backtest-1"))
        await self.session.execute(update(backtests).values(status="completed"))
        await self.session.commit()
        with self.assertRaises(main.HTTPException) as conflict:
            await main.delete_backtest("backtest-1", db=self.db)
        self.assertEqual(conflict.exception.status_code, 409)

        await self.session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == "member-1")
            .values(
                status="succeeded", completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc)
            )
        )
        await self.session.execute(
            insert(backtest_commands).values(
                backtest_id="backtest-1",
                command_id="command-1",
                command="pause",
                status="paused",
                lifecycle_revision=1,
                occurred_at=datetime(2026, 6, 8, 12, 34, tzinfo=timezone.utc),
            )
        )
        await self.session.commit()
        response = await main.delete_backtest("backtest-1", db=self.db)
        self.assertEqual(response.status_code, 204)
        for table in (
            backtests,
            backtest_runs,
            backtest_events,
            backtest_commands,
            backtest_queue_turns,
        ):
            rows = (await self.session.execute(select(table))).fetchall()
            self.assertEqual(rows, [], table.name)
        with self.assertRaises(main.HTTPException) as missing:
            await main.delete_backtest("backtest-1", db=self.db)
        self.assertEqual(missing.exception.status_code, 404)

    async def test_backtest_delete_rolls_back_when_child_removal_fails(self):
        _seed_execution_slot(self.session)
        await main.create_backtest(BacktestCreateIn(**self._backtest_payload()), db=self.db)
        await self.session.execute(
            update(backtests).values(
                status="cancelled",
                cancel_requested_at=datetime(2026, 6, 8, 12, 34, tzinfo=timezone.utc),
                cancellation_source="user",
                cancellation_reason="user_requested",
            )
        )
        await self.session.execute(
            update(backtest_runs).values(
                status="succeeded", completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc)
            )
        )
        await self.session.commit()

        await self.session.execute(text("""CREATE TRIGGER reject_event_delete
            BEFORE DELETE ON backtest_events BEGIN
                SELECT RAISE(ABORT, 'injected event deletion failure');
            END"""))
        await self.session.commit()
        with self.assertRaisesRegex(IntegrityError, "injected event deletion failure"):
            await crud.delete_backtest(self.db, "backtest-1")
        self.assertIsNotNone(await crud.get_backtest(self.db, "backtest-1"))
        self.assertEqual(len(await crud.list_backtest_members(self.db, "backtest-1")), 1)
        self.assertEqual(len(await crud.list_backtest_events(self.db, "backtest-1")), 1)

    async def test_individual_member_cancellation_preserves_other_members_and_completes_backtest(
        self,
    ):
        payload = self._backtest_payload()
        payload["raw_count"] = 2
        payload["member_count"] = 2
        payload["excluded_count"] = 0
        payload["members"].append(
            {
                **payload["members"][0],
                "run_id": "member-2",
                "run_ordinal": 1,
            }
        )
        await main.create_backtest(BacktestCreateIn(**payload), db=self.db)
        _seed_execution_slot(self.session)
        first = await main.cancel_backtest_run("member-1", db=self.db)
        assert first is not None
        self.assertEqual(first["status"], "cancelled")
        backtest = await main.get_backtest("backtest-1", db=self.db)
        assert backtest is not None
        self.assertEqual(backtest["status"], "queued")
        self.assertEqual(
            await main.claim_backtest_execution(
                BacktestExecutionClaimIn(
                    run_id="member-2",
                    owner_token="owner-2",
                    started_at=datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc),
                    worker_id="worker-test",
                ),
                db=self.db,
            ),
            {"updated": True},
        )
        second = await main.cancel_backtest_run("member-2", db=self.db)
        assert second is not None
        self.assertEqual(second["status"], "cancelling")
        backtest = await main.get_backtest("backtest-1", db=self.db)
        assert backtest is not None
        self.assertEqual(backtest["status"], "running")
        self.assertEqual(
            await main.settle_backtest_execution(
                BacktestExecutionSettleIn(
                    run_id="member-2",
                    owner_token="owner-2",
                    status="cancelled",
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                ),
                db=self.db,
            ),
            {"updated": True},
        )
        backtest = await main.get_backtest("backtest-1", db=self.db)
        self.assertEqual(backtest["status"], "completed")
        self.assertEqual(backtest["lifecycle_revision"], 4)
        events = await main.list_backtest_events("backtest-1", db=self.db)
        self.assertEqual(
            [event["event_type"] for event in events],
            ["accepted", "member_cancelled", "started", "member_cancel_requested", "completed"],
        )
        self.assertEqual(
            [run["status"] for run in await main.list_backtest_members("backtest-1", db=self.db)],
            ["cancelled", "cancelled"],
        )

    def test_backtest_rejects_unresolved_or_multi_market_member(self):
        payload = self._backtest_payload()
        payload["members"][0]["request"]["symbols"] = ["EURUSD", "USDJPY"]
        with self.assertRaises(ValidationError):
            BacktestCreateIn(**payload)
        payload = self._backtest_payload()
        payload["members"][0]["request"]["strategy"].pop("strategy_version")
        with self.assertRaises(ValidationError):
            BacktestCreateIn(**payload)

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
            await _seed_run(SeedRun(**run), db=self.db)

        listed = await main.list_backtest_runs(status="queued", db=self.db)

        self.assertEqual(
            [run["run_id"] for run in listed],
            ["run-newest", "run-a", "run-b"],
        )

    async def test_list_filters_each_immutable_request_json_field(self):
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-target",
                    request=_request_payload(
                        symbols=["EURUSD"],
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
        await _seed_run(
            SeedRun(
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
            await _seed_run(
                SeedRun(
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
            symbols=["EURUSD"],
            timeframe="H1",
            engine="vectorized",
            strategy={"strategy_id": "mean_reversion", "parameters": {}},
        )
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-target",
                    status="running",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-wrong-status",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await _seed_run(
            SeedRun(
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
        await _seed_run(
            SeedRun(**_run_payload()),
            db=self.db,
        )

        listed = await main.list_backtest_runs(symbol="USDJPY", db=self.db)

        self.assertEqual(listed, [])

    async def test_list_returns_all_matching_runs_without_a_hard_limit(self):
        for index in range(105):
            await _seed_run(
                SeedRun(
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
                "trade_direction": "long",
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
                "trade_direction": "long",
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
                "trade_direction": "long",
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
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-succeeded-logs",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
                    metrics={"profit_factor": None, "trade_count": 3, "ending_equity": 10000.0},
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
            [trade["trade_direction"] for trade in fetched_trades],
            ["long", "long", "long"],
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
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-empty",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
                    metrics={"profit_factor": None, "trade_count": 0, "ending_equity": 10000.0},
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

    def test_create_rejects_unknown_request_schema_version(self):
        with self.assertRaises(ValidationError):
            SeedRun(**_run_payload(request_schema_version=1))

    def test_create_rejects_incomplete_request_snapshot(self):
        request = _request_payload()
        request.pop("exchange")

        with self.assertRaises(ValidationError):
            SeedRun(**_run_payload(request=request))

    def test_create_rejects_invalid_request_enums_and_unknown_fields(self):
        invalid_execution = _request_payload()
        invalid_execution["execution"] = {
            **invalid_execution["execution"],
            "gap_policy": "invented",
        }
        unknown_field = _request_payload(extra_default="must-not-be-reconstructed")

        with self.assertRaises(ValidationError):
            SeedRun(**_run_payload(request=invalid_execution))
        with self.assertRaises(ValidationError):
            SeedRun(**_run_payload(request=unknown_field))

    def test_closed_trade_direction_is_required_and_constrained(self):
        base_trade = {
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

        BacktestClosedTradeIn(**{**base_trade, "trade_direction": "long"})
        BacktestClosedTradeIn(**{**base_trade, "trade_direction": "short"})

        with self.assertRaises(ValidationError):
            BacktestClosedTradeIn(**base_trade)
        with self.assertRaises(ValidationError):
            BacktestClosedTradeIn(**{**base_trade, "trade_direction": "flat"})

    def test_schema_uses_lifecycle_columns_and_json_request_only(self):
        self.assertEqual(
            set(backtest_runs.c.keys()),
            {
                "run_id",
                "status",
                "submitted_at",
                "started_at",
                "completed_at",
                "cancel_requested_at",
                "cancellation_source",
                "cancellation_reason",
                "error_code",
                "error_message",
                "request_schema_version",
                "request",
                "result_schema_version",
                "metrics",
                "diagnostics",
                "replay_descriptor",
                "backtest_id",
                "run_ordinal",
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
                "trade_direction",
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
        self.assertFalse(backtest_closed_trades.c.trade_direction.nullable)

    def test_initial_schema_includes_durable_backtest_tables(self):
        schema_path = (
            Path(__file__).resolve().parents[2]
            / "timescaledb-init"
            / "migrations"
            / "V001__base_schema.sql"
        )
        sql = schema_path.read_text(encoding="utf-8").lower()
        self.assertIn("create table if not exists backtest_runs", sql)
        self.assertIn("create table if not exists backtest_fills", sql)
        self.assertIn("create table if not exists backtest_closed_trades", sql)
        self.assertIn("trade_direction varchar(8) not null", sql)
        self.assertIn("backtest_closed_trades_trade_direction_check", sql)
        self.assertIn("trade_direction in ('long', 'short')", sql)
        self.assertIn("stop_loss_price double precision", sql)
        self.assertIn("take_profit_price double precision", sql)
        self.assertIn("request jsonb not null", sql)
        self.assertIn("metrics jsonb", sql)
        self.assertIn("diagnostics jsonb", sql)
        self.assertNotIn("drop table", sql)


class BacktestExecutionApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = InMemoryAsyncSession()
        self.db = cast(AsyncSession, self.session)
        _seed_execution_slot(self.session)
        self.started_at = datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc)
        self.completed_at = datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc)

    def tearDown(self):
        self.session.close()

    async def _create_queue(self):
        await _seed_run(SeedRun(**_run_payload(run_id="run-a")), db=self.db)
        await _seed_run(
            SeedRun(
                **_run_payload(
                    run_id="run-b",
                    submitted_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

    async def _claim(self, run_id: str, token: str):
        return await main.claim_backtest_execution(
            BacktestExecutionClaimIn(
                run_id=run_id,
                owner_token=token,
                started_at=self.started_at,
                worker_id="worker-test",
            ),
            db=self.db,
        )

    async def test_queued_cancel_is_immediate_idempotent_and_leaves_next_turn(self):
        from fastapi import HTTPException

        await self._create_queue()
        cancelled = await main.cancel_backtest_run("run-a", db=self.db)
        assert cancelled is not None
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["cancellation_source"], "user")
        self.assertEqual(cancelled["cancellation_reason"], "user_requested")
        self.assertEqual(cancelled["completed_at"], cancelled["cancel_requested_at"])
        repeated = await main.cancel_backtest_run("run-a", db=self.db)
        slot = await main.get_backtest_execution_slot(db=self.db)
        assert repeated is not None and slot is not None
        self.assertEqual(repeated["cancel_requested_at"], cancelled["cancel_requested_at"])
        self.assertIsNone(slot["owner_token"])
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": True})
        with self.assertRaises(HTTPException) as missing:
            await main.cancel_backtest_run("missing", db=self.db)
        self.assertEqual(missing.exception.status_code, 404)

    async def test_active_cancel_fences_late_result_until_reaped_settlement(self):
        from fastapi import HTTPException

        await self._create_queue()
        await self._claim("run-a", "owner-a")
        accepted = await main.cancel_backtest_run("run-a", db=self.db)
        assert accepted is not None
        self.assertEqual(accepted["status"], "cancelling")
        self.assertIsNone(accepted["completed_at"])
        slot = await main.get_backtest_execution_slot(db=self.db)
        repeated = await main.cancel_backtest_run("run-a", db=self.db)
        assert slot is not None and repeated is not None
        self.assertEqual(slot["run_id"], "run-a")
        self.assertEqual(repeated["status"], "cancelling")
        normal = BacktestExecutionSettleIn(
            run_id="run-a",
            owner_token="owner-a",
            status="failed",
            completed_at=self.completed_at,
            error_code="late",
            error_message="late",
        )
        self.assertEqual(
            await main.settle_backtest_execution(normal, db=self.db), {"updated": False}
        )
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "run-a")
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": False})
        cancelled = BacktestExecutionSettleIn(
            run_id="run-a",
            owner_token="owner-a",
            status="cancelled",
            completed_at=self.completed_at,
        )
        self.assertEqual(
            await main.settle_backtest_execution(cancelled, db=self.db), {"updated": True}
        )
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], None)
        self.assertEqual((await main.get_backtest_run("run-a", db=self.db))["status"], "cancelled")
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": True})
        self.assertEqual(
            await main.settle_backtest_execution(
                BacktestExecutionSettleIn(
                    run_id="run-b",
                    owner_token="owner-b",
                    status="failed",
                    completed_at=self.completed_at,
                    error_code="failure",
                    error_message="failed",
                ),
                db=self.db,
            ),
            {"updated": True},
        )
        with self.assertRaises(HTTPException) as conflict:
            await main.cancel_backtest_run("run-b", db=self.db)
        self.assertEqual(conflict.exception.status_code, 409)

    async def test_restart_reconciles_cancelling_only_after_verified_slot_clear(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        await main.cancel_backtest_run("run-a", db=self.db)
        request = BacktestExecutionReconcileIn(
            completed_at=self.completed_at,
            error_code="worker_interrupted",
            error_message="Backtest worker was interrupted before completion",
        )
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db), {"reconciled": None}
        )
        self.session.connection.execute(
            backtest_execution_slot.update().values(owner_token=None, run_id=None)
        )
        self.session.connection.commit()
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db), {"reconciled": 1}
        )
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db), {"reconciled": 0}
        )
        run = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual((run["status"], run["error_code"]), ("cancelled", None))
        self.assertEqual((await main.get_backtest_run("run-b", db=self.db))["status"], "queued")

    def _successful_settlement(self) -> BacktestExecutionSettleIn:
        return BacktestExecutionSettleIn(
            run_id="run-a",
            owner_token="owner-a",
            status="succeeded",
            completed_at=self.completed_at,
            result_schema_version=3,
            metrics={"profit_factor": None, "trade_count": 1, "ending_equity": 10000.0},
            diagnostics={},
            replay_descriptor=_replay_descriptor(),
            fills=[
                BacktestFillIn(
                    fill_sequence=0,
                    timestamp_ms=1714525200000,
                    symbol="EURUSD",
                    side="buy",
                    quantity=1.0,
                    price=1.0,
                    fees=0.0,
                    exit_reason=None,
                )
            ],
        )

    async def test_slot_route_result_matches_declared_response_schema(self):
        slot = await main.get_backtest_execution_slot(db=self.db)

        self.assertEqual(
            BacktestExecutionSlotOut.model_validate(slot).model_dump(),
            {
                "owner_token": None,
                "run_id": None,
                "fault_code": None,
                "fault_message": None,
            },
        )

    def test_claim_requires_worker_identity(self):
        for worker in ({}, {"worker_id": None}, {"worker_id": ""}):
            with self.subTest(worker=worker), self.assertRaises(ValidationError):
                BacktestExecutionClaimIn.model_validate(
                    {
                        "run_id": "run-a",
                        "owner_token": "owner-a",
                        "started_at": self.started_at,
                        **worker,
                    }
                )

    async def test_claim_requires_oldest_queue_entry_and_one_free_slot(self):
        await self._create_queue()

        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": False})
        self.assertEqual(await self._claim("run-a", "owner-a"), {"updated": True})
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": False})
        slot = await main.get_backtest_execution_slot(db=self.db)
        self.assertEqual(slot["run_id"], "run-a")
        self.assertEqual(slot["owner_token"], "owner-a")
        self.assertEqual((await main.get_backtest_run("run-b", db=self.db))["status"], "queued")

    async def _post_settlement(self, payload: dict) -> tuple[int, dict]:
        async def database():
            yield self.db

        async def receive():
            return {"type": "http.request", "body": json.dumps(payload).encode()}

        messages = []

        async def send(message):
            messages.append(message)

        main.app.dependency_overrides[main.get_db] = database
        try:
            await main.app(
                {
                    "type": "http",
                    "http_version": "1.1",
                    "method": "POST",
                    "scheme": "http",
                    "path": "/backtest-execution/settle",
                    "query_string": b"",
                    "headers": [(b"content-type", b"application/json")],
                },
                receive,
                send,
            )
        finally:
            main.app.dependency_overrides.pop(main.get_db)
        return messages[0]["status"], json.loads(messages[1]["body"])

    async def test_stale_owner_cannot_write_result_and_settlement_releases_slot(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        settlement = self._successful_settlement().model_dump(mode="json")
        settlement.update(run_id="run-a", owner_token="stale-owner", status="succeeded")

        self.assertEqual(await self._post_settlement(settlement), (200, {"updated": False}))
        stale_run = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual(stale_run["status"], "running")
        self.assertIsNone(stale_run["replay_descriptor"])
        settlement["owner_token"] = "owner-a"
        self.assertEqual(await self._post_settlement(settlement), (200, {"updated": True}))
        completed = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["metrics"], settlement["metrics"])
        self.assertEqual(completed["replay_descriptor"], settlement["replay_descriptor"])
        self.assertEqual(len(await main.get_backtest_fills("run-a", db=self.db)), 1)
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": True})

    async def _assert_saved_profit_factor(self, value):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        settlement = self._successful_settlement().model_dump(mode="json")
        settlement["metrics"]["profit_factor"] = value
        self.assertEqual(await self._post_settlement(settlement), (200, {"updated": True}))
        completed = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual(completed["metrics"]["profit_factor"], value)

    async def test_settlement_preserves_finite_profit_factor(self):
        await self._assert_saved_profit_factor(2.5)

    async def test_settlement_preserves_zero_profit_factor(self):
        await self._assert_saved_profit_factor(0.0)

    async def test_settlement_preserves_infinite_profit_factor(self):
        await self._assert_saved_profit_factor("infinity")

    async def test_settlement_preserves_null_profit_factor(self):
        await self._assert_saved_profit_factor(None)

    def test_profit_factor_union_is_required_and_strict(self):
        payload = self._successful_settlement().model_dump()
        for value in (0.0, 2.5, "infinity", None):
            metrics = {**payload["metrics"], "profit_factor": value}
            result = BacktestExecutionSettleIn.model_validate({**payload, "metrics": metrics})
            self.assertEqual(result.model_dump(mode="json")["metrics"], metrics)
        for value in (
            True,
            False,
            -1,
            float("nan"),
            float("inf"),
            -float("inf"),
            "2",
            "Infinity",
            {},
            [],
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "profit_factor"):
                BacktestExecutionSettleIn.model_validate(
                    {**payload, "metrics": {**payload["metrics"], "profit_factor": value}}
                )
        metrics = {
            key: value for key, value in payload["metrics"].items() if key != "profit_factor"
        }
        with self.assertRaisesRegex(ValueError, "profit_factor"):
            BacktestExecutionSettleIn.model_validate({**payload, "metrics": metrics})

    def test_success_requires_finite_ending_equity(self):
        payload = self._successful_settlement().model_dump()
        for metrics in (
            {"profit_factor": None},
            *(
                {"profit_factor": None, "ending_equity": value}
                for value in (None, True, "10000", float("nan"), float("inf"))
            ),
        ):
            with self.subTest(metrics=metrics):
                with self.assertRaisesRegex(ValueError, "metrics.ending_equity"):
                    BacktestExecutionSettleIn.model_validate({**payload, "metrics": metrics})
        for value in (10000.0, 0.0, -25.0):
            with self.subTest(value=value):
                result = BacktestExecutionSettleIn.model_validate(
                    {**payload, "metrics": {"profit_factor": None, "ending_equity": value}}
                )
                self.assertEqual(result.metrics, {"profit_factor": None, "ending_equity": value})

    async def test_settlement_rejects_missing_invalid_or_failed_replay_metadata(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        success = self._successful_settlement().model_dump(mode="json")
        success.update(run_id="run-a", owner_token="owner-a", status="succeeded")
        missing = {key: value for key, value in success.items() if key != "replay_descriptor"}
        invalid = {**success, "replay_descriptor": {"schema_version": 999}}
        failed = {
            "run_id": "run-a",
            "owner_token": "owner-a",
            "status": "failed",
            "completed_at": self.completed_at.isoformat(),
            "error_code": "backtest_failed",
            "error_message": "Backtest execution failed",
            "replay_descriptor": success["replay_descriptor"],
        }
        for payload in (missing, {**success, "replay_descriptor": None}, invalid, failed):
            with self.subTest(payload=payload):
                status, _ = await self._post_settlement(payload)
                self.assertEqual(status, 422)
                run = await main.get_backtest_run("run-a", db=self.db)
                self.assertEqual(run["status"], "running")
                self.assertIsNone(run["replay_descriptor"])
                self.assertEqual(
                    (await main.get_backtest_execution_slot(db=self.db))["owner_token"],
                    "owner-a",
                )

    async def test_failed_artifact_write_keeps_slot_and_running_history(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        fill = BacktestFillIn(
            fill_sequence=0,
            timestamp_ms=1714525200000,
            symbol="EURUSD",
            side="buy",
            quantity=1.0,
            price=1.0,
            fees=0.0,
            exit_reason=None,
        )
        with self.assertRaises(IntegrityError):
            await main.settle_backtest_execution(
                BacktestExecutionSettleIn(
                    run_id="run-a",
                    owner_token="owner-a",
                    status="succeeded",
                    completed_at=self.completed_at,
                    result_schema_version=3,
                    metrics={"profit_factor": None, "ending_equity": 10000.0},
                    diagnostics={},
                    replay_descriptor=_replay_descriptor(),
                    fills=[fill, fill],
                ),
                db=self.db,
            )

        self.assertEqual((await main.get_backtest_run("run-a", db=self.db))["status"], "running")
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "run-a")
        self.assertEqual(await main.get_backtest_fills("run-a", db=self.db), [])
        self.assertIsNone((await main.get_backtest_run("run-a", db=self.db))["replay_descriptor"])

    async def test_reconcile_is_idempotent_and_preserves_queue(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        request = BacktestExecutionReconcileIn(
            completed_at=self.completed_at,
            error_code="worker_interrupted",
            error_message="Backtest worker was interrupted before completion",
        )
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db),
            {"reconciled": None},
        )
        self.session.connection.execute(
            backtest_execution_slot.update().values(owner_token=None, run_id=None)
        )
        self.session.connection.commit()
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db),
            {"reconciled": 1},
        )
        self.assertEqual(
            await main.reconcile_backtest_execution(request, db=self.db),
            {"reconciled": 0},
        )
        run = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual((run["status"], run["error_code"]), ("failed", "worker_interrupted"))
        self.assertEqual((await main.get_backtest_run("run-b", db=self.db))["status"], "queued")


if __name__ == "__main__":
    unittest.main()


class SeedRun(BacktestRunOut):
    fills: list[BacktestFillIn] = []
    trades: list[BacktestClosedTradeIn] = []


async def _seed_run(run: SeedRun, *, db: AsyncSession):
    """Materialize a parent and seed execution artifacts for read/settlement tests."""
    data = run.model_dump()
    fills, trades = data.pop("fills"), data.pop("trades")
    parent_id = f"parent-{run.run_id}"
    data["backtest_id"] = parent_id
    payload = BacktestRunApiTests()._backtest_payload(
        backtest_id=parent_id,
        submission_id=parent_id,
        accepted_at=run.submitted_at,
        raw_count=1,
        member_count=1,
        excluded_count=0,
        members=[
            {
                "run_id": run.run_id,
                "run_ordinal": 0,
                "request_schema_version": 3,
                "request": data["request"],
            }
        ],
    )
    await main.create_backtest(BacktestCreateIn(**payload), db=db)
    await db.execute(
        update(backtest_runs).where(backtest_runs.c.run_id == run.run_id).values(**data)
    )
    if run.status != "queued":
        await db.execute(
            backtest_queue_turns.delete().where(backtest_queue_turns.c.backtest_id == parent_id)
        )
    if fills:
        await db.execute(insert(backtest_fills), [{"run_id": run.run_id, **f} for f in fills])
    if trades:
        await db.execute(
            insert(backtest_closed_trades), [{"run_id": run.run_id, **t} for t in trades]
        )
    await db.commit()
    return await main.get_backtest_run(run.run_id, db=db)
