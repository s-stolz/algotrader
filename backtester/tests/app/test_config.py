"""Backtester runtime configuration tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import BacktesterConfig


class TestBacktesterConfig(unittest.TestCase):
    def test_worker_poll_interval_can_be_loaded_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"BACKTESTER_WORKER_POLL_INTERVAL_SECONDS": "2.5"},
            clear=True,
        ):
            config = BacktesterConfig.from_env()

        self.assertEqual(config.worker_poll_interval_seconds, 2.5)

    def test_worker_poll_interval_defaults_to_one_second(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = BacktesterConfig.from_env()

        self.assertEqual(config.worker_poll_interval_seconds, 1.0)
        self.assertEqual(config.worker_heartbeat_interval_seconds, 5.0)
        self.assertEqual(config.worker_stale_after_seconds, 30.0)
        self.assertEqual(config.max_sweep_candidate_count, 1000)

    def test_sweep_limit_is_configurable_and_positive(self) -> None:
        with patch.dict(os.environ, {"BACKTESTER_MAX_SWEEP_CANDIDATE_COUNT": "25"}, clear=True):
            config = BacktesterConfig.from_env()
        self.assertEqual(config.max_sweep_candidate_count, 25)
        with self.assertRaises(ValueError):
            BacktesterConfig(max_sweep_candidate_count=0)

    def test_heartbeat_and_staleness_are_configurable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS": "2",
                "BACKTESTER_WORKER_STALE_AFTER_SECONDS": "10",
            },
            clear=True,
        ):
            config = BacktesterConfig.from_env()
        self.assertEqual(config.worker_heartbeat_interval_seconds, 2)
        self.assertEqual(config.worker_stale_after_seconds, 10)
        with self.assertRaises(ValueError):
            BacktesterConfig(worker_heartbeat_interval_seconds=30)


if __name__ == "__main__":
    unittest.main()
