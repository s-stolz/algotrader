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


if __name__ == "__main__":
    unittest.main()
