"""Long-lived backtester worker process entrypoint."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Callable, Protocol

_SRC_PATH = Path(__file__).resolve().parent / "src"
_SRC_PATH_TEXT = str(_SRC_PATH)
if _SRC_PATH_TEXT not in sys.path:
    sys.path.insert(0, _SRC_PATH_TEXT)

from adapters.persistence import (  # noqa: E402
    BacktestRunLifecyclePersistenceAdapter,
    DatabaseAccessorBacktestRunRepository,
)
from app.backtest_worker import BacktestWorker  # noqa: E402
from app.config import BacktesterConfig  # noqa: E402


class WorkerRuntime(Protocol):
    def run_forever(self) -> None: ...


WorkerFactory = Callable[[BacktesterConfig], WorkerRuntime]


def build_worker(config: BacktesterConfig) -> BacktestWorker:
    lifecycle = BacktestRunLifecyclePersistenceAdapter()
    return BacktestWorker(
        repository=DatabaseAccessorBacktestRunRepository(),
        lifecycle=lifecycle,
        poll_interval_seconds=config.worker_poll_interval_seconds,
        heartbeat_interval_seconds=config.worker_heartbeat_interval_seconds,
        heartbeat_publisher=lifecycle.record_worker_heartbeat,
    )


def main(*, worker_factory: WorkerFactory = build_worker) -> None:
    _configure_logging()
    worker_factory(BacktesterConfig.from_env()).run_forever()


def _configure_logging() -> None:
    level = os.getenv("BACKTESTER_LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("BACKTESTER_LOG_FORMAT", "pretty").lower()
    if log_format == "json":
        logging.basicConfig(level=level, format="%(message)s")
        logging.getLogger().handlers[0].setFormatter(_JsonLogFormatter())
    else:
        logging.basicConfig(
            level=level, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )


class _JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "worker_id", "fault_code", "error_code", "count"):
            value = getattr(record, key, None)
            if value is not None:
                event[key] = value
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, separators=(",", ":"))


if __name__ == "__main__":
    main()
