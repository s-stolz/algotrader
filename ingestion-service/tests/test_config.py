"""Frozen history policy validation."""

import os
import unittest
from unittest.mock import patch

from app.config import load_config


class HistoryConfigTests(unittest.TestCase):
    def test_default_and_quoted_start_date_reach_the_frozen_boundary(self):
        shared = {"INGESTION_HISTORY_LOOKBACK_DAYS": "1825", "INGESTION_HISTORY_START_DATE": ""}
        with patch.dict(os.environ, shared):
            self.assertEqual(load_config().history_start_ms(1792281780000), 1634601780000)
        shared = {
            "INGESTION_HISTORY_LOOKBACK_DAYS": "",
            "INGESTION_HISTORY_START_DATE": "2026-10-05",
        }
        with patch.dict(os.environ, shared):
            self.assertEqual(load_config().history_start_ms(1792281780000), 1791158400000)

    def test_invalid_or_conflicting_policies_fail_before_writes(self):
        with patch.dict(
            os.environ,
            {"INGESTION_HISTORY_LOOKBACK_DAYS": "1", "INGESTION_HISTORY_START_DATE": "2026-10-05"},
        ):
            with self.assertRaises(ValueError):
                load_config()
