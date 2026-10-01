from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.config import load_config
from main import IngestionService


class BackfillRangeTests(unittest.TestCase):
    NOW = int(datetime(2026, 10, 1, 12, tzinfo=timezone.utc).timestamp() * 1000)

    def test_default_history_is_ninety_days(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            config = load_config()
        self.assertEqual(config.history_start_ms(self.NOW), self.NOW - 90 * 86_400_000)

    def test_fixed_date_starts_at_midnight_utc(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "INGESTION_HISTORY_LOOKBACK_DAYS": "",
                "INGESTION_HISTORY_START_DATE": "2024-01-01",
            },
            clear=True,
        ):
            config = load_config()
        self.assertEqual(config.history_start_ms(self.NOW), 1_704_067_200_000)

    def test_invalid_runtime_history_is_rejected(self) -> None:
        for days, start in [
            ("", ""),
            ("90", "2024-01-01"),
            ("0", ""),
            ("-1", ""),
            ("1000000000000", ""),
            ("x", ""),
            ("", "2024-02-30"),
            ("", "2999-01-01"),
            ("", "20240101"),
        ]:
            with self.subTest(days=days, start=start), patch.dict(
                "os.environ",
                {
                    "INGESTION_HISTORY_LOOKBACK_DAYS": days,
                    "INGESTION_HISTORY_START_DATE": start,
                },
                clear=True,
            ), self.assertRaises(ValueError):
                load_config()

    def test_empty_and_existing_markets_respect_inclusive_history_boundary(self) -> None:
        service = object.__new__(IngestionService)
        service.history_start_ms = self.NOW - 90 * 86_400_000
        service.db_client = Mock()
        service.logger = Mock()
        for latest, expected in [
            (None, service.history_start_ms),
            ({"timestamp_ms": service.history_start_ms - 86400000}, service.history_start_ms),
            ({"timestamp_ms": self.NOW - 120000}, self.NOW - 60000),
        ]:
            with self.subTest(latest=latest):
                service.db_client.get_latest_m1_candle.return_value = latest
                watermark = service._get_frozen_watermark("EURUSD", "")
                self.assertEqual(service._next_candle_ts_ms(watermark, 1), expected)

    def test_next_candle_ts_advances_by_timeframe(self) -> None:
        latest_ts = 1_778_878_560_000

        next_ts = IngestionService._next_candle_ts_ms(latest_ts, timeframe_minutes=1)

        self.assertEqual(next_ts, latest_ts + 60_000)

    def test_redis_socket_timeout_exceeds_block_window(self) -> None:
        timeout = IngestionService._redis_socket_timeout_seconds(block_ms=5000)

        self.assertEqual(timeout, 6.0)

    def test_redis_socket_timeout_allows_indefinite_block(self) -> None:
        timeout = IngestionService._redis_socket_timeout_seconds(block_ms=0)

        self.assertIsNone(timeout)


if __name__ == "__main__":
    unittest.main()
