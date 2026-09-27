import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("TIMESCALEDB_USER", "test")
os.environ.setdefault("TIMESCALEDB_PASSWORD", "test")
os.environ.setdefault("TIMESCALEDB_HOST", "localhost")
os.environ.setdefault("TIMESCALEDB_PORT", "5432")
os.environ.setdefault("TIMESCALEDB_DB", "test")

import main  # noqa: E402
from app import crud  # noqa: E402
from app.models import (  # noqa: E402
    backtest_closed_trades,
    backtest_execution_slot,
    backtest_fills,
    backtest_runs,
    metadata,
)
from app.schemas import (  # noqa: E402
    BacktestBatchCreateIn,
    BacktestClosedTradeIn,
    BacktestExecutionClaimIn,
    BacktestExecutionReconcileIn,
    BacktestExecutionSettleIn,
    BacktestExecutionSlotOut,
    BacktestFillIn,
    BacktestRequestPayload,
    BacktestRunCompleteIn,
    BacktestRunConditionalUpdateIn,
    BacktestRunCreateIn,
    EquityReplayDescriptor,
)


class InMemoryAsyncSession:
    def __init__(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()
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
        "persist_result": False,
        "run_metadata": {
            "label": "queued-smoke",
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
        "status": "queued",
        "submitted_at": datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "request_schema_version": 2,
        "request": _request_payload(),
        "result_schema_version": None,
        "metrics": None,
        "diagnostics": None,
        "fills": [],
        "trades": [],
    }
    payload.update(overrides)
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

    def _batch_payload(self, **overrides):
        request = _request_payload()
        request["strategy"]["strategy_version"] = 1
        payload = {
            "batch_id": "batch-1",
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
                    "member_ordinal": 0,
                    "request_schema_version": 3,
                    "request": request,
                }
            ],
        }
        payload.update(overrides)
        return payload

    async def test_batch_acceptance_retry_and_ordered_inspection(self):
        payload = self._batch_payload()
        first = await main.create_backtest_batch(BacktestBatchCreateIn(**payload), db=self.db)
        retried = await main.create_backtest_batch(
            BacktestBatchCreateIn(**{**payload, "batch_id": "discarded-id"}), db=self.db
        )
        assert first is not None and retried is not None
        self.assertEqual(first["batch_id"], retried["batch_id"])
        self.assertEqual(first["status"], "queued")
        self.assertEqual(first["lifecycle_revision"], 0)
        members = await main.list_backtest_batch_members("batch-1", db=self.db)
        self.assertEqual(
            [(run["run_id"], run["member_ordinal"]) for run in members], [("member-1", 0)]
        )
        self.assertEqual(members[0]["request"], payload["members"][0]["request"])
        events = await main.list_backtest_batch_events("batch-1", db=self.db)
        self.assertEqual(
            [(event["revision"], event["event_type"]) for event in events], [(0, "accepted")]
        )
        self.assertIsNone(events[0]["prior_status"])
        self.assertEqual(len(await main.list_backtest_runs(db=self.db)), 1)
        self.assertEqual(len(await main.list_backtest_runs(membership="standalone", db=self.db)), 0)

    async def test_batch_retry_after_concurrent_identity_winner(self):
        from app import crud

        winner = self._batch_payload()
        retry = self._batch_payload(batch_id="discarded-id")

        class ConcurrentWinnerSession:
            def __init__(self, session):
                self.session = session
                self.raced = False

            async def execute(self, statement, params=None):
                if (
                    getattr(getattr(statement, "table", None), "name", None) == "backtest_batches"
                    and not self.raced
                ):
                    self.raced = True
                    await crud.create_backtest_batch(
                        self.session, BacktestBatchCreateIn(**winner).model_dump()
                    )
                    raise IntegrityError(
                        "INSERT backtest_batches", {}, Exception("duplicate submission_id")
                    )
                return await self.session.execute(statement, params)

            async def commit(self):
                await self.session.commit()

            async def rollback(self):
                await self.session.rollback()

        racing_session = ConcurrentWinnerSession(self.session)
        accepted = await crud.create_backtest_batch(
            cast(AsyncSession, racing_session), BacktestBatchCreateIn(**retry).model_dump()
        )
        assert accepted is not None
        self.assertTrue(racing_session.raced)
        self.assertEqual(accepted["batch_id"], winner["batch_id"])
        self.assertEqual(len(await main.list_backtest_batches(db=self.db)), 1)
        self.assertEqual(len(await main.list_backtest_batch_members("batch-1", db=self.db)), 1)
        self.assertEqual(len(await main.list_backtest_batch_events("batch-1", db=self.db)), 1)

    async def test_batch_identity_conflict_and_rollback(self):
        from app import crud
        from fastapi import HTTPException

        payload = self._batch_payload()
        await main.create_backtest_batch(BacktestBatchCreateIn(**payload), db=self.db)
        changed = self._batch_payload(batch_id="batch-2", accepted_definition={"changed": True})
        with self.assertRaises(HTTPException) as conflict:
            await main.create_backtest_batch(BacktestBatchCreateIn(**changed), db=self.db)
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(len(await main.list_backtest_batches(db=self.db)), 1)

        invalid = self._batch_payload(batch_id="batch-3", submission_id="submission-3")
        invalid["members"][0]["run_id"] = "member-1"
        with self.assertRaises(IntegrityError):
            await crud.create_backtest_batch(self.db, BacktestBatchCreateIn(**invalid).model_dump())
        self.assertIsNone(await crud.get_backtest_batch(self.db, "batch-3"))

    async def test_batch_member_cannot_be_individually_deleted(self):
        from fastapi import HTTPException

        await main.create_backtest_batch(BacktestBatchCreateIn(**self._batch_payload()), db=self.db)
        with self.assertRaises(HTTPException) as conflict:
            await main.delete_backtest_run("member-1", db=self.db)
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertIsNotNone(await main.get_backtest_run("member-1", db=self.db))

    async def test_standalone_claim_cannot_consume_batch_member(self):
        await main.create_backtest_batch(BacktestBatchCreateIn(**self._batch_payload()), db=self.db)
        result = await main.conditional_update_backtest_run(
            "member-1",
            BacktestRunConditionalUpdateIn(
                expected_status="queued",
                new_status="running",
                started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
            ),
            db=self.db,
        )
        self.assertEqual(result, {"updated": False})
        self.assertEqual((await main.get_backtest_run("member-1", db=self.db))["status"], "queued")

    async def test_global_claim_selects_older_batch_before_standalone(self):
        await main.create_backtest_batch(BacktestBatchCreateIn(**self._batch_payload()), db=self.db)
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="standalone",
                    submitted_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )
        _seed_execution_slot(self.session)
        for run_id, expected in (("standalone", False), ("member-1", True)):
            result = await main.claim_backtest_execution(
                BacktestExecutionClaimIn(
                    run_id=run_id,
                    owner_token="owner",
                    started_at=datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc),
                ),
                db=self.db,
            )
            self.assertEqual(result, {"updated": expected})
        self.assertEqual((await main.get_backtest_run("member-1", db=self.db))["status"], "running")
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "member-1")

    async def test_individual_member_cancellation_preserves_other_members_and_completes_batch(self):
        payload = self._batch_payload()
        payload["raw_count"] = 2
        payload["member_count"] = 2
        payload["excluded_count"] = 0
        payload["members"].append(
            {
                **payload["members"][0],
                "run_id": "member-2",
                "member_ordinal": 1,
            }
        )
        await main.create_backtest_batch(BacktestBatchCreateIn(**payload), db=self.db)
        _seed_execution_slot(self.session)
        first = await main.cancel_backtest_run("member-1", db=self.db)
        assert first is not None
        self.assertEqual(first["status"], "cancelled")
        batch = await main.get_backtest_batch("batch-1", db=self.db)
        assert batch is not None
        self.assertEqual(batch["status"], "queued")
        self.assertEqual(
            await main.claim_backtest_execution(
                BacktestExecutionClaimIn(
                    run_id="member-2",
                    owner_token="owner-2",
                    started_at=datetime(2026, 6, 8, 12, 32, tzinfo=timezone.utc),
                ),
                db=self.db,
            ),
            {"updated": True},
        )
        second = await main.cancel_backtest_run("member-2", db=self.db)
        assert second is not None
        self.assertEqual(second["status"], "cancelling")
        batch = await main.get_backtest_batch("batch-1", db=self.db)
        assert batch is not None
        self.assertEqual(batch["status"], "running")
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
        batch = await main.get_backtest_batch("batch-1", db=self.db)
        self.assertEqual(batch["status"], "completed")
        self.assertEqual(batch["lifecycle_revision"], 4)
        events = await main.list_backtest_batch_events("batch-1", db=self.db)
        self.assertEqual(
            [event["event_type"] for event in events],
            ["accepted", "member_cancelled", "started", "member_cancel_requested", "completed"],
        )
        self.assertEqual(
            [
                run["status"]
                for run in await main.list_backtest_batch_members("batch-1", db=self.db)
            ],
            ["cancelled", "cancelled"],
        )

    def test_member_cannot_be_created_through_standalone_route(self):
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(batch_id="batch-1", member_ordinal=0))

    def test_batch_rejects_unresolved_or_multi_market_member(self):
        payload = self._batch_payload()
        payload["members"][0]["request"]["symbols"] = ["EURUSD", "USDJPY"]
        with self.assertRaises(ValidationError):
            BacktestBatchCreateIn(**payload)
        payload = self._batch_payload()
        payload["members"][0]["request"]["strategy"].pop("strategy_version")
        with self.assertRaises(ValidationError):
            BacktestBatchCreateIn(**payload)

    async def test_create_queued_run_and_get_preserves_complete_request(self):
        created = await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        fetched = await main.get_backtest_run(created["run_id"], db=self.db)

        self.assertEqual(fetched["run_id"], "run-queued-1")
        self.assertEqual(fetched["status"], "queued")
        self.assertEqual(fetched["request_schema_version"], 2)
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

    async def test_create_version_three_preserves_exact_strategy_identity(self):
        request = _request_payload()
        request["strategy"] = {**request["strategy"], "strategy_version": 1}
        created = await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="versioned",
                    request_schema_version=3,
                    request=request,
                )
            ),
            db=self.db,
        )

        fetched = await main.get_backtest_run(created["run_id"], db=self.db)

        self.assertEqual(fetched["request_schema_version"], 3)
        self.assertEqual(fetched["request"]["strategy"], request["strategy"])

    async def test_create_queued_run_defaults_absent_terminal_fields(self):
        run = BacktestRunCreateIn(
            run_id="run-minimal-queued",
            status="queued",
            submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
            request_schema_version=2,
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
            await main.create_backtest_run(BacktestRunCreateIn(**run), db=self.db)

        listed = await main.list_backtest_runs(status="queued", db=self.db)

        self.assertEqual(
            [run["run_id"] for run in listed],
            ["run-newest", "run-a", "run-b"],
        )

    async def test_list_filters_each_immutable_request_json_field(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-target",
                    request=_request_payload(
                        symbols=["GBPUSD", "EURUSD"],
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
        await main.create_backtest_run(
            BacktestRunCreateIn(
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
            await main.create_backtest_run(
                BacktestRunCreateIn(
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
            symbols=["GBPUSD", "EURUSD"],
            timeframe="H1",
            engine="vectorized",
            strategy={"strategy_id": "mean_reversion", "parameters": {}},
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-target",
                    status="running",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-wrong-status",
                    submitted_at=datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc),
                    request=matching_request,
                )
            ),
            db=self.db,
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
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
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload()),
            db=self.db,
        )

        listed = await main.list_backtest_runs(symbol="USDJPY", db=self.db)

        self.assertEqual(listed, [])

    async def test_list_returns_all_matching_runs_without_a_hard_limit(self):
        for index in range(105):
            await main.create_backtest_run(
                BacktestRunCreateIn(
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

    def test_conditional_update_rejects_succeeded_status(self):
        with self.assertRaises(ValidationError):
            BacktestRunConditionalUpdateIn(
                expected_status="running",
                new_status="succeeded",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
            )

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
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
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
                        trade_direction="long",
                        quantity=1000.0,
                        entry_timestamp_ms=1714525200000,
                        entry_price=1.0715,
                        exit_timestamp_ms=1714532400000,
                        exit_price=1.074,
                        realized_pnl=2.5,
                        fees=0.3,
                        exit_reason="stop_loss",
                        stop_loss_price=1.069,
                        take_profit_price=1.081,
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
        self.assertEqual(fetched["result_schema_version"], 3)
        self.assertEqual(fetched["metrics"], {"total_return_pct": 1.25})
        self.assertEqual(fetched["replay_descriptor"], _replay_descriptor().model_dump())
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
                "trade_direction": "long",
                "quantity": 1000.0,
                "entry_timestamp_ms": 1714525200000,
                "entry_price": 1.0715,
                "exit_timestamp_ms": 1714532400000,
                "exit_price": 1.074,
                "realized_pnl": 2.5,
                "fees": 0.3,
                "exit_reason": "stop_loss",
                "stop_loss_price": 1.069,
                "take_profit_price": 1.081,
            },
        )

    async def test_successful_completion_preserves_closed_trade_protective_prices(self):
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
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
                metrics={"trade_count": 2},
                diagnostics={"bars": 120},
                trades=[
                    BacktestClosedTradeIn(
                        trade_sequence=0,
                        trade_id="trade-no-protection",
                        symbol="EURUSD",
                        trade_direction="long",
                        quantity=1000.0,
                        entry_timestamp_ms=1714525200000,
                        entry_price=1.0715,
                        exit_timestamp_ms=1714528800000,
                        exit_price=1.073,
                        realized_pnl=1.5,
                        fees=0.3,
                        exit_reason="signal",
                        stop_loss_price=None,
                        take_profit_price=None,
                    ),
                    BacktestClosedTradeIn(
                        trade_sequence=1,
                        trade_id="trade-configured-protection",
                        symbol="EURUSD",
                        trade_direction="long",
                        quantity=1000.0,
                        entry_timestamp_ms=1714529400000,
                        entry_price=1.076,
                        exit_timestamp_ms=1714532400000,
                        exit_price=1.074,
                        realized_pnl=-2.0,
                        fees=0.3,
                        exit_reason="signal",
                        stop_loss_price=1.069,
                        take_profit_price=1.081,
                    ),
                ],
            ),
            db=self.db,
        )
        fetched_run = await main.get_backtest_run("run-queued-1", db=self.db)
        fetched_trades = await main.get_backtest_trades("run-queued-1", db=self.db)

        self.assertEqual(completed, {"updated": True})
        self.assertEqual(fetched_run["result_schema_version"], 3)
        self.assertEqual(
            [(trade["stop_loss_price"], trade["take_profit_price"]) for trade in fetched_trades],
            [(None, None), (1.069, 1.081)],
        )

    async def test_short_completion_readback_preserves_direction_metrics_and_fill_shape(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-short-acceptance",
                    status="running",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

        metrics = {
            "total_return_pct": -0.0046845,
            "max_drawdown_pct": -0.0046845,
            "trade_count": 1.0,
            "long_trade_count": 0.0,
            "short_trade_count": 1.0,
            "long_win_rate_pct": 0.0,
            "short_win_rate_pct": 0.0,
            "long_realized_pnl": 0.0,
            "short_realized_pnl": -0.46845,
        }
        completed = await main.complete_backtest_run(
            "run-short-acceptance",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
                metrics=metrics,
                diagnostics={"engine": "vectorized", "execution_duration_ms": 12},
                fills=[
                    BacktestFillIn(
                        fill_sequence=0,
                        timestamp_ms=1700000300000,
                        symbol="AAPL",
                        side="sell",
                        quantity=1.0,
                        price=9.0,
                        fees=0.009,
                        exit_reason=None,
                    ),
                    BacktestFillIn(
                        fill_sequence=1,
                        timestamp_ms=1700000300000,
                        symbol="AAPL",
                        side="buy",
                        quantity=1.0,
                        price=9.45,
                        fees=0.00945,
                        exit_reason="stop_loss",
                    ),
                ],
                trades=[
                    BacktestClosedTradeIn(
                        trade_sequence=0,
                        trade_id="AAPL-trade-1",
                        symbol="AAPL",
                        trade_direction="short",
                        quantity=1.0,
                        entry_timestamp_ms=1700000300000,
                        entry_price=9.0,
                        exit_timestamp_ms=1700000300000,
                        exit_price=9.45,
                        realized_pnl=-0.46845,
                        fees=0.01845,
                        exit_reason="stop_loss",
                        stop_loss_price=9.45,
                        take_profit_price=8.1,
                    )
                ],
            ),
            db=self.db,
        )

        fetched_run = await main.get_backtest_run("run-short-acceptance", db=self.db)
        fetched_fills = await main.get_backtest_fills("run-short-acceptance", db=self.db)
        fetched_trades = await main.get_backtest_trades("run-short-acceptance", db=self.db)

        self.assertEqual(completed, {"updated": True})
        self.assertEqual(fetched_run["request_schema_version"], 2)
        self.assertEqual(
            fetched_run["request"]["execution"]["allowed_directions"],
            "long_and_short",
        )
        self.assertNotIn("allow_short", fetched_run["request"]["execution"])
        self.assertEqual(fetched_run["result_schema_version"], 3)
        self.assertEqual(fetched_run["metrics"], metrics)
        self.assertEqual(
            [(fill["side"], fill["exit_reason"]) for fill in fetched_fills],
            [("sell", None), ("buy", "stop_loss")],
        )
        self.assertTrue(all("trade_direction" not in fill for fill in fetched_fills))
        self.assertEqual(fetched_trades[0]["trade_direction"], "short")
        self.assertEqual(fetched_trades[0]["exit_reason"], "stop_loss")
        self.assertEqual(fetched_trades[0]["fees"], 0.01845)
        self.assertEqual(fetched_trades[0]["realized_pnl"], -0.46845)
        self.assertEqual(fetched_trades[0]["stop_loss_price"], 9.45)
        self.assertEqual(fetched_trades[0]["take_profit_price"], 8.1)

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
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
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
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
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
            trade_direction="long",
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
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
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
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
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
                        "trade_direction": "long",
                        "quantity": 1000.0,
                        "entry_timestamp_ms": 1714525200000,
                        "entry_price": 1.0715,
                        "exit_timestamp_ms": 1714532400000,
                        "exit_price": 1.074,
                        "realized_pnl": 2.5,
                        "fees": 0.3,
                        "exit_reason": "signal",
                        "stop_loss_price": 1.068,
                        "take_profit_price": None,
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
        self.assertEqual(created["result_schema_version"], 3)
        self.assertEqual(fill["run_id"], "run-succeeded-1")
        self.assertEqual(fill["fill_sequence"], 0)
        self.assertEqual(fill["side"], "buy")
        self.assertEqual(trade["run_id"], "run-succeeded-1")
        self.assertEqual(trade["trade_sequence"], 0)
        self.assertEqual(trade["trade_direction"], "long")
        self.assertEqual(trade["exit_reason"], "signal")
        self.assertEqual(trade["stop_loss_price"], 1.068)
        self.assertIsNone(trade["take_profit_price"])

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
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-succeeded-logs",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
                    metrics={"trade_count": 3},
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
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-empty",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
                    metrics={"trade_count": 0},
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

    async def test_delete_backtest_run_cascades_execution_logs(self):
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-delete",
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=3,
                    replay_descriptor=_replay_descriptor(),
                    metrics={"trade_count": 1},
                    diagnostics={"bars": 10},
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
                            "trade_id": "trade-delete",
                            "symbol": "EURUSD",
                            "trade_direction": "long",
                            "quantity": 1000.0,
                            "entry_timestamp_ms": 1714525200000,
                            "entry_price": 1.0715,
                            "exit_timestamp_ms": 1714532400000,
                            "exit_price": 1.074,
                            "realized_pnl": 2.5,
                            "fees": 0.3,
                            "exit_reason": "signal",
                            "stop_loss_price": None,
                            "take_profit_price": None,
                        }
                    ],
                )
            ),
            db=self.db,
        )

        response = await main.delete_backtest_run("run-delete", db=self.db)
        run_result = await self.session.execute(select(backtest_runs))
        fill_result = await self.session.execute(select(backtest_fills))
        trade_result = await self.session.execute(select(backtest_closed_trades))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(run_result.fetchall(), [])
        self.assertEqual(fill_result.fetchall(), [])
        self.assertEqual(trade_result.fetchall(), [])

        with self.assertRaises(main.HTTPException) as ctx:
            await main.delete_backtest_run("run-delete", db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_rejects_unknown_request_schema_version(self):
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(request_schema_version=1))

    def test_new_success_requires_replay_descriptor(self):
        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(
                **_run_payload(
                    status="succeeded",
                    result_schema_version=3,
                    replay_descriptor=None,
                )
            )
        with self.assertRaises(ValidationError):
            BacktestRunCompleteIn.model_validate(
                {
                    "expected_status": "running",
                    "completed_at": datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    "result_schema_version": 3,
                    "metrics": {},
                    "diagnostics": {},
                }
            )

    def test_successful_completion_cannot_overwrite_a_terminal_descriptor(self):
        with self.assertRaises(ValidationError):
            BacktestRunCompleteIn.model_validate(
                {
                    "expected_status": "succeeded",
                    "completed_at": datetime(2026, 6, 8, 12, 36, tzinfo=timezone.utc),
                    "result_schema_version": 3,
                    "replay_descriptor": _replay_descriptor().model_dump(),
                    "metrics": {},
                    "diagnostics": {},
                }
            )

    def test_result_schema_version_accepts_v3_and_rejects_legacy_versions(self):
        BacktestRunCreateIn(**_run_payload(result_schema_version=None))
        BacktestRunCreateIn(**_run_payload(result_schema_version=3))
        BacktestRunCompleteIn(
            expected_status="running",
            completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
            result_schema_version=3,
            replay_descriptor=_replay_descriptor(),
            metrics={},
            diagnostics={},
        )

        for legacy_version in (1, 2):
            with self.subTest(result_schema_version=legacy_version):
                with self.assertRaises(ValidationError):
                    BacktestRunCreateIn(**_run_payload(result_schema_version=legacy_version))
                with self.assertRaises(ValidationError):
                    BacktestRunCompleteIn(
                        expected_status="running",
                        completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                        result_schema_version=legacy_version,
                        replay_descriptor=_replay_descriptor(),
                        metrics={},
                        diagnostics={},
                    )

        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(**_run_payload(result_schema_version=4))

    def test_succeeded_create_requires_result_schema_version_3(self):
        BacktestRunCreateIn(
            **_run_payload(
                status="succeeded",
                started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                result_schema_version=3,
                replay_descriptor=_replay_descriptor(),
                metrics={},
                diagnostics={},
            )
        )

        with self.assertRaises(ValidationError):
            BacktestRunCreateIn(
                **_run_payload(
                    status="succeeded",
                    started_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 6, 8, 12, 35, tzinfo=timezone.utc),
                    result_schema_version=None,
                    metrics={},
                    diagnostics={},
                )
            )

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
                "batch_id",
                "member_ordinal",
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

    def test_obsolete_backtest_result_schema_migrations_are_removed(self):
        init_dir = Path(__file__).resolve().parents[2] / "timescaledb-init"
        result_schema_migrations = [
            path.name for path in init_dir.glob("*backtest-result-schema*.sql")
        ]

        self.assertEqual(result_schema_migrations, [])


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
        await main.create_backtest_run(
            BacktestRunCreateIn(**_run_payload(run_id="run-a")), db=self.db
        )
        await main.create_backtest_run(
            BacktestRunCreateIn(
                **_run_payload(
                    run_id="run-b",
                    submitted_at=datetime(2026, 6, 8, 12, 31, tzinfo=timezone.utc),
                )
            ),
            db=self.db,
        )

    async def _claim(self, run_id: str, token: str):
        return await main.claim_backtest_execution(
            BacktestExecutionClaimIn(run_id=run_id, owner_token=token, started_at=self.started_at),
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

    def _legacy_completion(self) -> BacktestRunCompleteIn:
        return BacktestRunCompleteIn(
            expected_status="running",
            completed_at=self.completed_at,
            result_schema_version=3,
            metrics={"trade_count": 1},
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

    async def test_claim_requires_oldest_queue_entry_and_one_free_slot(self):
        await self._create_queue()

        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": False})
        self.assertEqual(await self._claim("run-a", "owner-a"), {"updated": True})
        self.assertEqual(await self._claim("run-b", "owner-b"), {"updated": False})
        slot = await main.get_backtest_execution_slot(db=self.db)
        self.assertEqual(slot["run_id"], "run-a")
        self.assertEqual(slot["owner_token"], "owner-a")
        self.assertEqual((await main.get_backtest_run("run-b", db=self.db))["status"], "queued")

    async def test_legacy_routes_cannot_bypass_a_migrated_slot(self):
        await self._create_queue()
        legacy_claim = await main.conditional_update_backtest_run(
            "run-a",
            BacktestRunConditionalUpdateIn(
                expected_status="queued", new_status="running", started_at=self.started_at
            ),
            db=self.db,
        )
        self.assertEqual(legacy_claim, {"updated": False})

        await self._claim("run-a", "owner-a")
        legacy_completion = await main.complete_backtest_run(
            "run-a",
            BacktestRunCompleteIn(
                expected_status="running",
                completed_at=self.completed_at,
                result_schema_version=3,
                metrics={},
                diagnostics={},
                replay_descriptor=_replay_descriptor(),
            ),
            db=self.db,
        )
        self.assertEqual(legacy_completion, {"updated": False})
        self.assertEqual((await main.get_backtest_run("run-a", db=self.db))["status"], "running")

    async def test_legacy_completion_cannot_settle_queued_run_around_an_owned_slot(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")

        completion_data = self._legacy_completion().model_dump(exclude={"expected_status"})
        completion = await crud.complete_backtest_run(
            self.db, run_id="run-b", expected_status="queued", completion=completion_data
        )

        self.assertFalse(completion)
        self.assertEqual((await main.get_backtest_run("run-b", db=self.db))["status"], "queued")
        self.assertEqual(await main.get_backtest_fills("run-b", db=self.db), [])
        self.assertEqual((await main.get_backtest_execution_slot(db=self.db))["run_id"], "run-a")

    async def test_legacy_completion_cannot_write_after_operator_clears_slot(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        self.session.connection.execute(
            backtest_execution_slot.update().values(owner_token=None, run_id=None)
        )
        self.session.connection.commit()

        completion = await main.complete_backtest_run(
            "run-a", self._legacy_completion(), db=self.db
        )

        self.assertEqual(completion, {"updated": False})
        self.assertEqual((await main.get_backtest_run("run-a", db=self.db))["status"], "running")
        self.assertEqual(await main.get_backtest_fills("run-a", db=self.db), [])
        self.assertIsNone((await main.get_backtest_execution_slot(db=self.db))["owner_token"])

    async def test_legacy_failure_cannot_write_after_slot_clear_before_reconciliation(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        self.session.connection.execute(
            backtest_execution_slot.update().values(owner_token=None, run_id=None)
        )
        self.session.connection.commit()

        late_failure = await main.conditional_update_backtest_run(
            "run-a",
            BacktestRunConditionalUpdateIn(
                expected_status="running",
                new_status="failed",
                completed_at=self.completed_at,
                error_code="stale_worker_failure",
                error_message="late failure from previous owner",
            ),
            db=self.db,
        )

        self.assertEqual(late_failure, {"updated": False})
        self.assertEqual((await main.get_backtest_run("run-a", db=self.db))["status"], "running")
        reconciliation = await main.reconcile_backtest_execution(
            BacktestExecutionReconcileIn(
                completed_at=self.completed_at,
                error_code="worker_interrupted",
                error_message="Backtest worker was interrupted before completion",
            ),
            db=self.db,
        )
        self.assertEqual(reconciliation, {"reconciled": 1})
        run = await main.get_backtest_run("run-a", db=self.db)
        self.assertEqual((run["status"], run["error_code"]), ("failed", "worker_interrupted"))
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
        settlement = self._legacy_completion().model_dump(mode="json", exclude={"expected_status"})
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

    async def test_settlement_rejects_missing_invalid_or_failed_replay_metadata(self):
        await self._create_queue()
        await self._claim("run-a", "owner-a")
        success = self._legacy_completion().model_dump(mode="json", exclude={"expected_status"})
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
                    metrics={},
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
