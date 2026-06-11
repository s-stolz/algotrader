"""Backtester worker process entrypoint tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import worker
from app.config import BacktesterConfig


class _FakeWorker:
    def __init__(self) -> None:
        self.started = False

    def run_forever(self) -> None:
        self.started = True


class TestBacktesterWorkerEntrypoint(unittest.TestCase):
    def test_main_loads_runtime_config_and_starts_worker(self) -> None:
        runtime = _FakeWorker()
        captured_config: list[BacktesterConfig] = []

        def build_worker(config: BacktesterConfig) -> _FakeWorker:
            captured_config.append(config)
            return runtime

        with patch.dict(
            os.environ,
            {"BACKTESTER_WORKER_POLL_INTERVAL_SECONDS": "2.5"},
            clear=True,
        ):
            worker.main(worker_factory=build_worker)

        self.assertTrue(runtime.started)
        self.assertEqual(captured_config[0].worker_poll_interval_seconds, 2.5)


if __name__ == "__main__":
    unittest.main()
