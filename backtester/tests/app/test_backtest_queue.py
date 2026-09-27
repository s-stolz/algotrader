"""Queue telemetry is a read-only projection, even when the owner disappears."""

from __future__ import annotations

import unittest

from adapters.api.app import create_app
from app.backtest_queue import BacktestQueueService
from fastapi.testclient import TestClient


class _QueueReader:
    def __init__(self, state):
        self.state: dict | Exception = state

    def get_backtest_queue_state(self):
        if isinstance(self.state, Exception):
            raise self.state
        return self.state


def _state():
    return {
        "snapshot_at": 50_000,
        "slot": {
            "owner_token": "owner-a",
            "run_id": "active",
            "fault_code": None,
            "fault_message": None,
        },
        "active_run": {"run_id": "active", "started_at": 10_000},
        "heartbeats": [
            {
                "worker_id": "worker-a",
                "owner_token": "owner-a",
                "heartbeat_at": 45_000,
                "fault_code": None,
                "fault_message": None,
            }
        ],
        "queued_runs": [
            {"run_id": "queued-a", "submitted_at": 11_000},
            {"run_id": "queued-b", "submitted_at": 12_000},
        ],
    }


class BacktestQueueTests(unittest.TestCase):
    def test_healthy_long_run_and_advisory_queue_are_read_only(self):
        state = _state()
        snapshot = BacktestQueueService(_QueueReader(state)).snapshot()
        self.assertEqual(snapshot["availability"], "healthy")
        self.assertEqual(snapshot["active_run"], {"run_id": "active", "started_at_ms": 10_000})
        self.assertEqual(snapshot["last_heartbeat_ms"], 45_000)
        self.assertEqual([entry["estimated_position"] for entry in snapshot["queued"]], [1, 2])
        self.assertEqual(state, _state())

    def test_stale_or_absent_owner_is_not_hidden_by_an_idle_competitor(self):
        state = _state()
        state["heartbeats"].append(
            {
                "worker_id": "worker-b",
                "owner_token": None,
                "heartbeat_at": 49_000,
                "fault_code": None,
                "fault_message": None,
            }
        )
        state["heartbeats"][0]["heartbeat_at"] = 19_000
        snapshot = BacktestQueueService(_QueueReader(state)).snapshot()
        self.assertEqual(snapshot["availability"], "stale")
        self.assertEqual(snapshot["operational_faults"][0]["code"], "heartbeat_stale")
        state["heartbeats"] = state["heartbeats"][1:]
        absent = BacktestQueueService(_QueueReader(state)).snapshot()
        self.assertEqual(absent["availability"], "unavailable")
        self.assertEqual(absent["last_heartbeat_ms"], None)
        self.assertEqual(absent["active_run"]["run_id"], "active")

    def test_slot_fault_remains_visible_with_fresh_heartbeat(self):
        state = _state()
        state["slot"].update(
            fault_code="terminal_persistence_failed",
            fault_message="Completion could not be persisted",
        )
        snapshot = BacktestQueueService(_QueueReader(state)).snapshot()
        self.assertEqual(snapshot["availability"], "faulted")
        self.assertEqual(snapshot["operational_faults"][0]["code"], "terminal_persistence_failed")
        self.assertEqual(state["slot"]["owner_token"], "owner-a")

    def test_public_route_health_and_failed_read(self):
        reader = _QueueReader(_state())
        with TestClient(create_app(queue_service=BacktestQueueService(reader))) as client:
            response = client.get("/backtests/queue")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["queued"][0]["run_id"], "queued-a")
            self.assertEqual(client.get("/backtests/queue/health").status_code, 200)
            state = reader.state
            assert isinstance(state, dict)
            state["heartbeats"] = []
            self.assertEqual(client.get("/backtests/queue/health").status_code, 503)
            reader.state = ValueError("secret database credentials")
            unknown = client.get("/backtests/queue")
            self.assertEqual(unknown.status_code, 503)
            self.assertNotIn("secret", unknown.text)


if __name__ == "__main__":
    unittest.main()
