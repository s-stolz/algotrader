"""Redis delivery and recovery for backtest invalidations and progress.

Messages request authoritative reads, never lifecycle transitions. Each worker
instance has its own durable group so an idle worker cannot steal cancellation
from the owner. Reuse its group identity after restart, never concurrently.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from threading import Event, Lock, Thread
from typing import Any

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import ResponseError
from redis.retry import Retry

CONTROL_STREAM = "backtests:control:v1"
EVENT_STREAM = "backtests:events:v1"
PROGRESS_KEY = "backtests:progress:v1"
_LOGGER = logging.getLogger(__name__)


def redis_client() -> Redis:
    return Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
        protocol=2,
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=15,
        retry=Retry(NoBackoff(), 0),
    )


class BacktestEventPublisher:
    """Coalesce invalidations and retry failed publication without blocking commands."""

    def __init__(self, client: Any = None) -> None:
        self._client: Any = client if client is not None else redis_client()
        self._lock = Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._ready = Event()
        self._stop = Event()
        self._thread = Thread(target=self._run, daemon=True, name="backtest-publication")

    def start(self) -> None:
        # A crash may have happened after a database commit and before XADD.
        # Wake every worker to reconcile durable state and every browser to reload.
        if self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, daemon=True, name="backtest-publication")
        self.changed()
        self._thread.start()

    def changed(self) -> None:
        self._enqueue("control", {"type": "reconcile"})
        self._enqueue("changed", {"type": "backtestChanged"})

    def health(self, payload: dict[str, Any]) -> None:
        self._enqueue("health", {"type": "backtestHealth", **payload})

    def progress(
        self, run_id: str, stage: str, *, processed: int | None = None, total: int | None = None
    ) -> None:
        payload: dict[str, Any] = {"type": "backtestProgress", "run_id": run_id, "stage": stage}
        if processed is not None and total is not None:
            payload.update(processed_candles=processed, total_candles=total)
        self._enqueue("progress", payload)

    def _enqueue(self, key: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._pending[key] = payload
            self._ready.set()

    def flush(self) -> None:
        with self._lock:
            pending = dict(self._pending)
        for key, payload in pending.items():
            stream = CONTROL_STREAM if key == "control" else EVENT_STREAM
            if key == "progress":
                # The verified execution slot permits one active run. Retain its
                # latest stage separately from the bounded notification stream.
                with self._client.pipeline(transaction=True) as transaction:
                    transaction.set(PROGRESS_KEY, json.dumps(payload))
                    transaction.xadd(stream, {"payload": json.dumps(payload)}, maxlen=10000)
                    transaction.execute()
            else:
                self._client.xadd(stream, {"payload": json.dumps(payload)}, maxlen=10000)
            with self._lock:
                if self._pending.get(key) is payload:
                    del self._pending[key]
        with self._lock:
            if not self._pending:
                self._ready.clear()

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._ready.wait(0.5):
                continue
            try:
                self.flush()
            except Exception:
                _LOGGER.exception("Backtest publication failed; retrying")
                self._stop.wait(1)

    def close(self) -> None:
        self._stop.set()
        self._ready.set()
        self._thread.join(timeout=10)
        if not self._thread.is_alive():
            try:
                self.flush()
            except Exception:
                _LOGGER.warning("Unpublished backtest changes will reconcile on publisher restart")
        self._client.close()


class BacktestControlInbox:
    """Blocking stream listener with explicit pending recovery and delayed ACKs."""

    def __init__(self, client: Any = None, *, group: str | None = None) -> None:
        self._client: Any = client if client is not None else redis_client()
        self._group = group or os.getenv("BACKTESTER_WORKER_GROUP", socket.gethostname())
        self._consumer = "worker"
        self._lock = Lock()
        self._ids: set[str] = set()
        self._acks: set[str] = set()
        self.ready = Event()
        self._stop = Event()
        self._thread = Thread(target=self._run, daemon=True, name="backtest-control")

    def start(self) -> None:
        self._thread.start()

    def take(self) -> set[str]:
        with self._lock:
            ids, self._ids = self._ids, set()
            self.ready.clear()
            return ids

    def acknowledge(self, ids: set[str]) -> None:
        with self._lock:
            self._acks.update(ids)

    def _receive(self, rows: Any) -> None:
        with self._lock:
            for _, messages in rows:
                self._ids.update(str(message_id) for message_id, _ in messages)
            if self._ids:
                self.ready.set()

    def _connect(self) -> None:
        try:
            self._client.xgroup_create(CONTROL_STREAM, self._group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        cursor = "0"
        while True:
            rows = self._client.xreadgroup(
                self._group, self._consumer, {CONTROL_STREAM: cursor}, count=100
            )
            if not rows or not rows[0][1]:
                break
            self._receive(rows)
            cursor = rows[0][1][-1][0]
        # Also repair state if entries were trimmed or Redis was restored.
        self.ready.set()

    def _read(self) -> None:
        with self._lock:
            acks = set(self._acks)
        if acks:
            self._client.xack(CONTROL_STREAM, self._group, *acks)
            with self._lock:
                self._acks.difference_update(acks)
        self._receive(
            self._client.xreadgroup(
                self._group, self._consumer, {CONTROL_STREAM: ">"}, count=100, block=1000
            )
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._connect()
                while not self._stop.is_set():
                    self._read()
            except Exception:
                _LOGGER.exception("Backtest control disconnected; recovering on reconnect")
                self._stop.wait(1)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=6)
        self._client.close()
