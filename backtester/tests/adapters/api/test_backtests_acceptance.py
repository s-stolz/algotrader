from __future__ import annotations

import unittest
from datetime import datetime, timezone
from itertools import count
from unittest.mock import patch

from adapters.api.app import create_app
from app.backtest_definitions import BacktestPreviewService
from app.backtest_runs import BacktestRunService
from app.backtests import BacktestService
from db_accessor_client import DatabaseAccessorClientError
from fastapi.testclient import TestClient

from .test_backtests_preview import _definition
from .test_backtests_routes import _FakeRunRepository


class BacktestClient:
    def __init__(self) -> None:
        self.backtests: dict[str, dict] = {}
        self.members: dict[str, list[dict]] = {}

    def create_backtest(self, backtest: dict) -> dict:
        existing = self.backtests.get(backtest["submission_id"])
        if existing is not None:
            if existing["accepted_definition"] != backtest["accepted_definition"]:
                raise DatabaseAccessorClientError("conflict", status_code=409)
            return existing
        stored = {key: value for key, value in backtest.items() if key != "members"}
        stored.update(status="queued", lifecycle_revision=0)
        self.backtests[backtest["submission_id"]] = stored
        self.members[stored["backtest_id"]] = [
            {
                **member,
                "backtest_id": stored["backtest_id"],
                "status": "queued",
                "submitted_at": stored["accepted_at"],
            }
            for member in backtest["members"]
        ]
        return stored

    def rename_backtest(self, backtest_id: str, name: str | None) -> dict:
        saved = self.get_backtest(backtest_id)
        saved["name"] = name
        return saved

    def list_backtests(self) -> list[dict]:
        return list(self.backtests.values())

    def get_backtest(self, backtest_id: str) -> dict:
        backtest = next(
            (
                backtest
                for backtest in self.backtests.values()
                if backtest["backtest_id"] == backtest_id
            ),
            None,
        )
        if backtest is None:
            raise DatabaseAccessorClientError("Backtest not found", status_code=404)
        return backtest

    def list_backtest_members(self, backtest_id: str) -> list[dict]:
        return self.members[backtest_id]

    def list_backtest_events(self, backtest_id: str) -> list[dict]:
        return [
            {
                "backtest_id": backtest_id,
                "revision": 0,
                "event_type": "accepted",
                "prior_status": None,
                "status": "queued",
                "occurred_at": "2026-09-26T00:00:00+00:00",
                "reason": None,
            }
        ]

    def delete_backtest(self, backtest_id: str) -> None:
        backtest = self.get_backtest(backtest_id)
        if backtest["status"] not in {"completed", "cancelled"}:
            raise DatabaseAccessorClientError("Cancel and settle this backtest", status_code=409)
        self.backtests.pop(backtest["submission_id"])
        self.members.pop(backtest_id)

    def control_backtest(
        self, backtest_id: str, command: str, command_id: str, policy: dict
    ) -> dict:
        backtest = self.get_backtest(backtest_id)
        if backtest["status"] == "completed":
            raise DatabaseAccessorClientError("terminal", status_code=409)
        if command == "cancel":
            backtest["status"] = "cancelled"
            backtest["cancel_requested_at"] = "2026-09-26T00:00:01+00:00"
            backtest["cancellation_source"] = "user"
            backtest["cancellation_reason"] = "user_requested"
            backtest["completed_at"] = "2026-09-26T00:00:01+00:00"
            for member in self.members[backtest_id]:
                member["status"] = "cancelled"
        else:
            backtest["status"] = "paused" if command == "pause" else "running"
        backtest["lifecycle_revision"] += 1
        result = {
            "backtest_id": backtest_id,
            "status": backtest["status"],
            "lifecycle_revision": backtest["lifecycle_revision"],
        }
        if command == "cancel":
            result["command_id"] = command_id
        return result


class BacktestAcceptanceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ids = count()
        self.client_store = BacktestClient()
        preview = BacktestPreviewService(
            markets=lambda: [
                {"symbol_id": 1, "symbol": "EURUSD", "exchange": "FX"},
                {"symbol_id": 2, "symbol": "USDJPY", "exchange": "FX"},
            ],
            max_candidate_count=200,
        )
        self.backtest_service = BacktestService(
            preview=preview,
            client=self.client_store,
            new_id=lambda: f"id-{next(self._ids)}",
            now=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc),
        )
        self.client = TestClient(
            create_app(
                service=BacktestRunService(repository=_FakeRunRepository()),
                preview_service=preview,
                backtest_service=self.backtest_service,
            )
        )

    def tearDown(self) -> None:
        self.client.close()

    def test_rename_and_clear_preserve_backtest_and_members_in_every_state(self) -> None:
        import copy

        response = self.client.post("/backtests", json={**_definition(), "submission_id": "rename"})
        backtest_id = response.json()["backtest_id"]
        for status in [
            "queued",
            "running",
            "pausing",
            "paused",
            "cancelling",
            "cancelled",
            "completed",
        ]:
            backtest = self.client_store.get_backtest(backtest_id)
            backtest["status"] = status
            before = copy.deepcopy(backtest)
            members = copy.deepcopy(self.client_store.members[backtest_id])
            events = self.client.get(f"/backtests/{backtest_id}/events").json()
            for name, expected in [
                ("  Duplicate  ", "Duplicate"),
                (" ", None),
                ("😀" * 120, "😀" * 120),
            ]:
                renamed = self.client.patch(f"/backtests/{backtest_id}/name", json={"name": name})
                self.assertEqual(renamed.status_code, 200, renamed.text)
                self.assertEqual(renamed.json()["name"], expected)
                self.assertEqual(backtest, {**before, "name": expected})
                self.assertEqual(self.client_store.members[backtest_id], members)
                self.assertEqual(self.client.get(f"/backtests/{backtest_id}/events").json(), events)
                self.assertEqual(
                    self.client.get(f"/backtests/{backtest_id}").json()["name"], expected
                )
        for payload in [
            {},
            {"name": 123},
            {"name": "a\nb"},
            {"name": "x" * 121},
            {"name": "x", "lifecycle_revision": 2},
        ]:
            self.assertEqual(
                self.client.patch(f"/backtests/{backtest_id}/name", json=payload).status_code,
                422,
            )
        self.assertEqual(
            self.client.patch("/backtests/missing/name", json={"name": None}).status_code,
            404,
        )
        with patch.object(
            self.client_store,
            "rename_backtest",
            side_effect=DatabaseAccessorClientError("private", status_code=500),
        ):
            failed = self.client.patch(f"/backtests/{backtest_id}/name", json={"name": "x"})
            self.assertEqual(failed.status_code, 503)
            self.assertNotIn("private", failed.text)

    def test_named_and_unnamed_acceptance_keep_preview_and_members_name_free(self) -> None:
        for index, (name, expected) in enumerate(
            [
                (None, None),
                (" \t ", None),
                ("  Same experiment  ", "Same experiment"),
                ("Same experiment", "Same experiment"),
                ("😀" * 120, "😀" * 120),
            ]
        ):
            payload = {**_definition(), "submission_id": f"name-{index}", "name": name}
            response = self.client.post("/backtests", json=payload)
            self.assertEqual(response.status_code, 202, response.text)
            backtest_id = response.json()["backtest_id"]
            detail = self.client.get(f"/backtests/{backtest_id}").json()
            self.assertEqual(detail["name"], expected)
            self.assertNotIn("name", detail["accepted_definition"])
            self.assertNotIn("name", detail["accepted_definition"]["shared_request"])
            members = self.client.get(f"/backtests/{backtest_id}/runs").json()
            self.assertTrue(all("name" not in member["request"] for member in members))
            self.assertEqual(self.client.post("/backtests", json=payload).json(), response.json())
        self.assertEqual(
            [row["name"] for row in self.client.get("/backtests").json()],
            [None, None, "Same experiment", "Same experiment", "😀" * 120],
        )
        for name in ["x" * 121, "a\nb", "a\rb", "\ntrimmed", "a\u2029b", 123]:
            response = self.client.post(
                "/backtests",
                json={**_definition(), "submission_id": "invalid", "name": name},
            )
            self.assertEqual(response.status_code, 422)
        response = self.client.post("/backtests/preview", json={**_definition(), "name": "Preview"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.client_store.backtests), 5)

    def test_copied_names_create_fresh_backtests_and_members_without_changing_sources(self) -> None:
        for index, (source_name, chosen, expected) in enumerate(
            [
                ("Baseline", "Baseline (copy)", "Baseline (copy)"),
                (None, "", None),
                ("😀" * 120, "😀" * 113 + " (copy)", "😀" * 113 + " (copy)"),
                ("Baseline", "  Revised copy  ", "Revised copy"),
            ]
        ):
            with self.subTest(source_name=source_name, chosen=chosen):
                definition = _definition()
                source_submission = f"source-{index}"
                accepted = self.client.post(
                    "/backtests",
                    json={**definition, "submission_id": source_submission, "name": source_name},
                )
                self.assertEqual(accepted.status_code, 202, accepted.text)
                source_id = accepted.json()["backtest_id"]
                source = self.client.get(f"/backtests/{source_id}").json()
                source_members = self.client.get(f"/backtests/{source_id}/runs").json()
                copied = self.client.post(
                    "/backtests",
                    json={**definition, "submission_id": f"copy-{index}", "name": chosen},
                )
                self.assertEqual(copied.status_code, 202, copied.text)
                copy_id = copied.json()["backtest_id"]
                self.assertNotEqual(copy_id, source_id)
                detail = self.client.get(f"/backtests/{copy_id}").json()
                self.assertEqual(detail["name"], expected)
                self.assertNotEqual(detail["submission_id"], source_submission)
                self.assertEqual(detail["accepted_definition"], source["accepted_definition"])
                self.assertNotIn("name", detail["accepted_definition"])
                members = self.client.get(f"/backtests/{copy_id}/runs").json()
                self.assertEqual(len(members), len(source_members))
                self.assertTrue(
                    {member["run_id"] for member in members}.isdisjoint(
                        member["run_id"] for member in source_members
                    )
                )
                self.assertTrue(all(member["backtest_id"] == copy_id for member in members))
                self.assertEqual(self.client.get(f"/backtests/{source_id}").json(), source)
                self.assertEqual(
                    self.client.get(f"/backtests/{source_id}/runs").json(),
                    source_members,
                )
                names_by_id = {
                    row["backtest_id"]: row["name"] for row in self.client.get("/backtests").json()
                }
                self.assertEqual(names_by_id[copy_id], expected)
                self.assertEqual(names_by_id[source_id], source_name)

    def test_public_launch_is_released_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/backtests",
                json={
                    **_definition(),
                    "submission_id": "submit-1",
                },
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(self.client_store.backtests), 1)

    def test_pause_resume_public_commands_and_conflict(self) -> None:
        created = self.client.post(
            "/backtests", json={**_definition(), "submission_id": "control-submit"}
        )
        backtest_id = created.json()["backtest_id"]
        paused = self.client.post(
            f"/backtests/{backtest_id}/pause", json={"command_id": "pause-one"}
        )
        self.assertEqual((paused.status_code, paused.json()["status"]), (200, "paused"))
        self.assertEqual(self.client.get(f"/backtests/{backtest_id}").json()["status"], "paused")
        resumed = self.client.post(
            f"/backtests/{backtest_id}/resume", json={"command_id": "resume-one"}
        )
        self.assertEqual((resumed.status_code, resumed.json()["status"]), (200, "running"))
        self.assertEqual(
            self.client.post(
                f"/backtests/{backtest_id}/pause", json={"command_id": ""}
            ).status_code,
            422,
        )
        self.client_store.get_backtest(backtest_id)["status"] = "completed"
        self.assertEqual(
            self.client.post(
                f"/backtests/{backtest_id}/pause", json={"command_id": "pause-two"}
            ).status_code,
            409,
        )

    def test_cancel_public_command_exposes_identity_and_durable_backtest_detail(self) -> None:
        created = self.client.post(
            "/backtests", json={**_definition(), "submission_id": "cancel-submit"}
        )
        backtest_id = created.json()["backtest_id"]
        response = self.client.post(
            f"/backtests/{backtest_id}/cancel", json={"command_id": "cancel-one"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "backtest_id": backtest_id,
                "command_id": "cancel-one",
                "status": "cancelled",
                "lifecycle_revision": 1,
            },
        )
        detail = self.client.get(f"/backtests/{backtest_id}").json()
        self.assertEqual(detail["status"], "cancelled")
        self.assertEqual(detail["cancel_requested_at_ms"], detail["completed_at_ms"])
        self.assertEqual(detail["outcome_counts"]["cancelled"], detail["member_count"])

    def test_accept_retry_and_inspect_actual_members(self) -> None:
        with patch.dict("os.environ", {"BACKTESTER_BACKTEST_ACCEPTANCE_ENABLED": "1"}):
            request = {**_definition(), "submission_id": "submit-1"}
            first = self.client.post("/backtests", json=request)
            repeated = self.client.post("/backtests", json=request)
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(first.headers["location"], f"/backtests/{first.json()['backtest_id']}")
        self.assertEqual(repeated.json(), first.json())
        backtest_id = first.json()["backtest_id"]
        detail = self.client.get(f"/backtests/{backtest_id}").json()
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
        members = self.client.get(f"/backtests/{backtest_id}/runs").json()
        self.assertEqual([run["run_ordinal"] for run in members], list(range(96)))
        self.assertEqual({run["status"] for run in members}, {"queued"})
        self.assertEqual({run["backtest_id"] for run in members}, {backtest_id})
        self.assertEqual(len(self.client.get("/backtests").json()), 1)
        self.assertEqual(len(self.client.get("/backtests", params={"symbol": "EURUSD"}).json()), 1)
        self.assertEqual(self.client.get("/backtests", params={"symbol": "MISSING"}).json(), [])
        self.assertEqual(
            self.client.get("/backtests", params={"with_failed_members": "true"}).json(), []
        )
        self.client_store.members[backtest_id][0]["status"] = "failed"
        failed = self.client.get("/backtests", params={"with_failed_members": "true"}).json()
        self.assertEqual([backtest["backtest_id"] for backtest in failed], [backtest_id])
        self.assertEqual(failed[0]["has_failed_members"], True)
        self.assertEqual(
            self.client.get(f"/backtests/{backtest_id}/events").json()[0]["revision"], 0
        )
        self.assertIsNone(
            self.client.get(f"/backtests/{backtest_id}/events").json()[0]["prior_status"]
        )
        with patch.object(
            self.client_store,
            "list_backtest_events",
            return_value=[
                {
                    "backtest_id": backtest_id,
                    "revision": 1,
                    "event_type": "started",
                    "prior_status": "queued",
                    "status": "running",
                    "occurred_at": "2026-09-26T00:00:01+00:00",
                    "trigger_run_id": "member-0",
                    "reason": None,
                },
            ],
        ):
            event = self.client.get(f"/backtests/{backtest_id}/events").json()[0]
        self.assertEqual((event["prior_status"], event["status"]), ("queued", "running"))
        self.assertEqual(event["trigger_run_id"], "member-0")
        self.assertEqual(event["occurred_at_ms"], 1790380801000)
        self.assertNotIn("occurred_at", event)

    def test_rejection_creates_no_backtest_and_identity_conflict(self) -> None:
        with patch.dict("os.environ", {"BACKTESTER_BACKTEST_ACCEPTANCE_ENABLED": "1"}):
            invalid = _definition()
            invalid["parameter_axes"]["fast_window"] = {"mode": "values", "values": [True]}
            response = self.client.post(
                "/backtests",
                json={
                    **invalid,
                    "submission_id": "submit-1",
                },
            )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client_store.backtests, {})
            accepted = self.client.post(
                "/backtests",
                json={
                    **_definition(),
                    "submission_id": "submit-1",
                },
            )
            self.assertEqual(accepted.status_code, 202)
            changed = _definition()
            changed["timeframes"] = ["M1"]
            conflict = self.client.post(
                "/backtests",
                json={
                    **changed,
                    "submission_id": "submit-1",
                },
            )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(len(self.client_store.backtests), 1)

    def test_delete_requires_terminal_backtest_and_removes_whole_history(self) -> None:
        with patch.dict("os.environ", {"BACKTESTER_BACKTEST_ACCEPTANCE_ENABLED": "1"}):
            accepted = self.client.post(
                "/backtests", json={**_definition(), "submission_id": "delete-1"}
            )
        self.assertEqual(accepted.status_code, 202)
        backtest_id = accepted.json()["backtest_id"]
        self.assertEqual(self.client.delete(f"/backtests/{backtest_id}").status_code, 409)
        self.client_store.get_backtest(backtest_id)["status"] = "completed"
        self.assertEqual(self.client.delete(f"/backtests/{backtest_id}").status_code, 204)
        self.assertEqual(self.client_store.backtests, {})
        self.assertEqual(self.client_store.members, {})
        self.assertEqual(self.client.delete(f"/backtests/{backtest_id}").status_code, 404)
