import unittest
from unittest.mock import patch

import pandas as pd
from app.services.candle_cache import CandleCache


def frame(last_ms):
    return pd.DataFrame({"close": [100.0]}, index=pd.to_datetime([last_ms], unit="ms", utc=True))


class CurrentCandleCacheTests(unittest.TestCase):
    def put(
        self, cache, last_ms=60_000, end_ms: int | None = 120_000, started=125.0, timeframe="M1"
    ):
        cache.put_current(
            exchange=None,
            symbol="TEST",
            timeframe=timeframe,
            candles=frame(last_ms),
            end_ms=end_ms,
            read_started_at=started,
        )

    def test_current_bounded_snapshot_expires_at_next_minute(self):
        cache = CandleCache()
        with patch("app.services.candle_cache.time.time", return_value=125.0) as clock:
            self.put(cache)
            self.assertIsNotNone(
                cache.get_tail(exchange=None, symbol="TEST", timeframe="M1", bars=1)
            )
            clock.return_value = 180.0
            self.assertIsNone(cache.get_tail(exchange=None, symbol="TEST", timeframe="M1", bars=1))

    def test_old_future_and_calendar_bounded_snapshots_are_not_admitted(self):
        with patch("app.services.candle_cache.time.time", return_value=125.0):
            for last, end, timeframe in (
                (0, 120_000, "M1"),
                (60_000, 60_000, "M1"),
                (180_000, 240_000, "M1"),
                (60_000, 120_000, "W1"),
            ):
                with self.subTest(last=last, end=end, timeframe=timeframe):
                    cache = CandleCache()
                    self.put(cache, last, end, timeframe=timeframe)
                    self.assertIsNone(
                        cache.get_tail(exchange=None, symbol="TEST", timeframe=timeframe, bars=1)
                    )

    def test_read_crossing_a_minute_boundary_cannot_prime_live_warmup(self):
        cache = CandleCache()
        with patch("app.services.candle_cache.time.time", return_value=180.0):
            self.put(cache, end_ms=None, started=179.0)
            self.assertIsNone(cache.get_tail(exchange=None, symbol="TEST", timeframe="M1", bars=1))

    def test_authoritative_latest_read_can_cache_a_closed_market(self):
        cache = CandleCache()
        with patch("app.services.candle_cache.time.time", return_value=125.0):
            self.put(cache, last_ms=0, end_ms=None)
            self.assertIsNotNone(
                cache.get_tail(exchange=None, symbol="TEST", timeframe="M1", bars=1)
            )
