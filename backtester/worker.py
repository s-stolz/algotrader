"""Long-lived backtester worker process entrypoint."""

from __future__ import annotations

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
    return BacktestWorker(
        repository=DatabaseAccessorBacktestRunRepository(),
        lifecycle=BacktestRunLifecyclePersistenceAdapter(),
        poll_interval_seconds=config.worker_poll_interval_seconds,
    )


def main(*, worker_factory: WorkerFactory = build_worker) -> None:
    _configure_logging()
    worker_factory(BacktesterConfig.from_env()).run_forever()


def _configure_logging() -> None:
    level = os.getenv("BACKTESTER_LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("BACKTESTER_LOG_FORMAT", "pretty").lower()
    if log_format == "json":
        format_string = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(level=level, format=format_string)


if __name__ == "__main__":
    main()
