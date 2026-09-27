"""Backtester-owned, read-only projection of execution queue telemetry."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping, Protocol


class QueueStateReader(Protocol):
    def get_backtest_queue_state(self) -> Mapping[str, Any]: ...


class BacktestQueueService:
    def __init__(
        self,
        reader: QueueStateReader,
        *,
        stale_after_seconds: float = 30.0,
    ) -> None:
        if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self._reader = reader
        self._threshold_ms = int(stale_after_seconds * 1000)

    def snapshot(self) -> dict[str, Any]:
        state = self._reader.get_backtest_queue_state()
        snapshot_at_ms = _timestamp_ms(state["snapshot_at"])
        slot = state["slot"]
        owner_token = slot["owner_token"]
        heartbeats = [
            heartbeat
            for heartbeat in state["heartbeats"]
            if owner_token is None or heartbeat["owner_token"] == owner_token
        ]
        heartbeat = max(
            heartbeats, key=lambda item: _timestamp_ms(item["heartbeat_at"]), default=None
        )
        last_heartbeat_ms = (
            _timestamp_ms(heartbeat["heartbeat_at"]) if heartbeat is not None else None
        )
        faults: list[dict[str, str]] = []
        if slot["fault_code"] is not None:
            faults.append(
                {
                    "code": str(slot["fault_code"]),
                    "message": str(slot["fault_message"] or "Execution is faulted"),
                }
            )
        if heartbeat is not None and heartbeat["fault_code"] is not None:
            faults.append(
                {
                    "code": str(heartbeat["fault_code"]),
                    "message": str(heartbeat["fault_message"] or "Worker is faulted"),
                }
            )
        if last_heartbeat_ms is None:
            faults.append({"code": "heartbeat_absent", "message": "Worker heartbeat is absent"})
        elif snapshot_at_ms - last_heartbeat_ms > self._threshold_ms:
            faults.append({"code": "heartbeat_stale", "message": "Worker heartbeat is stale"})

        if any(fault["code"] not in ("heartbeat_absent", "heartbeat_stale") for fault in faults):
            availability = "faulted"
        elif last_heartbeat_ms is None:
            availability = "unavailable"
        elif snapshot_at_ms - last_heartbeat_ms > self._threshold_ms:
            availability = "stale"
        else:
            availability = "healthy"

        active = state["active_run"]
        return {
            "snapshot_at_ms": snapshot_at_ms,
            "active_run": (
                {
                    "run_id": str(active["run_id"]),
                    "started_at_ms": _timestamp_ms(active["started_at"]),
                }
                if active is not None and active["started_at"] is not None
                else None
            ),
            "last_heartbeat_ms": last_heartbeat_ms,
            "availability": availability,
            "stale_after_ms": self._threshold_ms,
            "operational_faults": faults,
            "queued": [
                {
                    "run_id": str(run["run_id"]),
                    "submitted_at_ms": _timestamp_ms(run["submitted_at"]),
                    "estimated_position": position,
                }
                for position, run in enumerate(state["queued_runs"], 1)
            ],
        }


def _timestamp_ms(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Telemetry timestamps must carry a timezone")
        return int(value.timestamp() * 1000)
    raise ValueError("Invalid telemetry timestamp")
