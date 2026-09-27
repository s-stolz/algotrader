from __future__ import annotations

import unittest
from datetime import datetime, timezone
from itertools import count
from unittest.mock import patch

from adapters.api.app import create_app
from app.backtest_batches import BacktestBatchService
from app.backtest_runs import BacktestRunService
from app.sweeps import SweepPreviewService
from db_accessor_client import DatabaseAccessorClientError
from fastapi.testclient import TestClient

from .test_backtests_routes import _FakeRunRepository
from .test_sweep_preview_routes import _definition


class BatchClient:
    def __init__(self) -> None:
        self.batches: dict[str, dict] = {}
        self.members: dict[str, list[dict]] = {}

    def create_backtest_batch(self, batch: dict) -> dict:
        existing = self.batches.get(batch["submission_id"])
        if existing is not None:
            if existing["accepted_definition"] != batch["accepted_definition"]:
                raise DatabaseAccessorClientError("conflict", status_code=409)
            return existing
        stored = {key: value for key, value in batch.items() if key != "members"}
        stored.update(status="queued", lifecycle_revision=0)
        self.batches[batch["submission_id"]] = stored
        self.members[stored["batch_id"]] = [
            {
                **member,
                "batch_id": stored["batch_id"],
                "status": "queued",
                "submitted_at": stored["accepted_at"],
            }
            for member in batch["members"]
        ]
        return stored

    def list_backtest_batches(self) -> list[dict]:
        return list(self.batches.values())

    def get_backtest_batch(self, batch_id: str) -> dict:
        return next(batch for batch in self.batches.values() if batch["batch_id"] == batch_id)

    def list_backtest_batch_members(self, batch_id: str) -> list[dict]:
        return self.members[batch_id]

    def list_backtest_batch_events(self, batch_id: str) -> list[dict]:
        return [
            {
                "batch_id": batch_id,
                "revision": 0,
                "event_type": "accepted",
                "status": "queued",
                "occurred_at": "2026-09-26T00:00:00+00:00",
                "reason": None,
            }
        ]


class BatchAcceptanceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ids = count()
        self.client_store = BatchClient()
        preview = SweepPreviewService(
            markets=lambda: [
                {"symbol_id": 1, "symbol": "EURUSD", "exchange": "FX"},
                {"symbol_id": 2, "symbol": "USDJPY", "exchange": "FX"},
            ],
            max_candidate_count=200,
        )
        self.batch_service = BacktestBatchService(
            preview=preview,
            client=self.client_store,
            new_id=lambda: f"id-{next(self._ids)}",
            now=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc),
        )
        self.client = TestClient(
            create_app(
                service=BacktestRunService(repository=_FakeRunRepository()),
                preview_service=preview,
                batch_service=self.batch_service,
            )
        )

    def tearDown(self) -> None:
        self.client.close()

    def test_gate_blocks_public_launch_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/backtests/batches",
                json={
                    **_definition(),
                    "submission_id": "submit-1",
                },
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client_store.batches, {})

    def test_accept_retry_and_inspect_actual_members(self) -> None:
        with patch.dict("os.environ", {"BACKTESTER_BATCH_ACCEPTANCE_ENABLED": "1"}):
            request = {**_definition(), "submission_id": "submit-1"}
            first = self.client.post("/backtests/batches", json=request)
            repeated = self.client.post("/backtests/batches", json=request)
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(
            first.headers["location"], f"/backtests/batches/{first.json()['batch_id']}"
        )
        self.assertEqual(repeated.json(), first.json())
        batch_id = first.json()["batch_id"]
        detail = self.client.get(f"/backtests/batches/{batch_id}").json()
        self.assertEqual(
            (detail["raw_count"], detail["member_count"], detail["excluded_count"]), (144, 96, 48)
        )
        self.assertEqual(detail["lifecycle_revision"], 0)
        self.assertEqual(
            (detail["settled_count"], detail["executed_count"], detail["total_count"]), (0, 0, 96)
        )
        self.assertEqual(detail["outcome_counts"]["queued"], 96)
        self.assertEqual(
            detail["accepted_definition"]["normalized_selections"]["timeframes"], ["M5", "M1"]
        )
        self.assertEqual(
            detail["strategy_metadata"]["strategy_version"], request["strategy"]["strategy_version"]
        )
        members = self.client.get(f"/backtests/batches/{batch_id}/members").json()
        self.assertEqual([run["member_ordinal"] for run in members], list(range(96)))
        self.assertEqual({run["status"] for run in members}, {"queued"})
        self.assertEqual({run["batch_id"] for run in members}, {batch_id})
        self.assertEqual(len(self.client.get("/backtests/batches").json()), 1)
        self.assertEqual(
            self.client.get(f"/backtests/batches/{batch_id}/events").json()[0]["revision"], 0
        )

    def test_rejection_creates_no_batch_and_identity_conflict(self) -> None:
        with patch.dict("os.environ", {"BACKTESTER_BATCH_ACCEPTANCE_ENABLED": "1"}):
            invalid = _definition()
            invalid["parameter_axes"]["fast_window"] = {"mode": "values", "values": [True]}
            response = self.client.post(
                "/backtests/batches",
                json={
                    **invalid,
                    "submission_id": "submit-1",
                },
            )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client_store.batches, {})
            accepted = self.client.post(
                "/backtests/batches",
                json={
                    **_definition(),
                    "submission_id": "submit-1",
                },
            )
            self.assertEqual(accepted.status_code, 202)
            changed = _definition()
            changed["timeframes"] = ["M1"]
            conflict = self.client.post(
                "/backtests/batches",
                json={
                    **changed,
                    "submission_id": "submit-1",
                },
            )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(len(self.client_store.batches), 1)
