import unittest
from unittest.mock import AsyncMock

from app.historical_candles import write_historical_candles
from app.schemas import HistoricalCandleBatchIn
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql


def candle(timestamp=60000, close=2):
    return dict(timestamp_ms=timestamp, open=1, high=3, low=0, close=close, volume=9)


class HistoricalCandleTests(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_changes_only_ohlcv_and_collapses_duplicate_timestamps(self):
        session = AsyncMock()
        session.execute.return_value.rowcount = 1
        count = await write_historical_candles(session, 1, [candle(), candle(close=3)])
        statement = session.execute.call_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.assertIn("ON CONFLICT (symbol_id, timestamp_utc) DO UPDATE", sql)
        self.assertNotIn("timestamp_utc = excluded", sql)
        self.assertEqual(compiled.params["close_m0"], 3)
        self.assertEqual(count, 1)
        session.commit.assert_awaited_once()

    async def test_failed_persistence_rolls_back_and_propagates(self):
        session = AsyncMock()
        session.commit.side_effect = RuntimeError("uncertain commit")
        with self.assertRaises(RuntimeError):
            await write_historical_candles(session, 1, [candle()])
        session.rollback.assert_awaited_once()

    def test_request_rejects_outside_interval_and_unaligned_candles(self):
        for timestamp in (0, 120000, 60001):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValidationError):
                HistoricalCandleBatchIn.model_validate(
                    {
                        "symbol": "EURUSD",
                        "start_ms": 60000,
                        "end_ms": 119999,
                        "candles": [candle(timestamp)],
                    }
                )
