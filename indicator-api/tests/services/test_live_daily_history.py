import unittest
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
from app.services.live_daily_history import load_daily_snapshot
from app.services.live_indicator_manager import LiveStreamSpec


class DailyHistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.spec = LiveStreamSpec("123", "EURUSD", "H1", 5, None, {})
        self.storage = Mock(
            get_market=AsyncMock(return_value={"symbol_id": 1}),
            get_pending_recovery=AsyncMock(return_value=None),
            get_live_write_guard=AsyncMock(return_value=None),
        )
        client = patch("app.services.live_daily_history.AsyncDatabaseAccessorClient")
        client.start().return_value.__aenter__.return_value = self.storage
        self.addCleanup(client.stop)
        self.rows = pd.DataFrame({"close": [1.0, 1.03, 1.04]}, index=[-60000, 3540000, 3600000])
        self.fetch = patch(
            "app.services.anchored_indicator_service.get_candles", side_effect=self.get_candles
        )
        self.candles = self.fetch.start()
        self.addCleanup(self.fetch.stop)

    async def get_candles(self, *, start_ms, end_ms, limit, timeframe, **kwargs):
        self.assertEqual(timeframe, "M1")
        rows = self.rows
        if start_ms is not None:
            rows = rows.loc[rows.index >= start_ms]
        if end_ms is not None:
            rows = rows.loc[rows.index < end_ms]
        if limit is not None:
            rows = rows.tail(limit)
        rows = rows.copy()
        rows.index = pd.to_datetime(rows.index, unit="ms", utc=True)
        return rows

    async def load(self):
        return await load_daily_snapshot(self.spec, ["EURUSD"], 0, 3600000, 3600000)

    async def test_raw_snapshot_preserves_bucket_closes_without_reading_aggregates(self):
        result = await self.load()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[0].index.tolist(), [-3600000, 0])
        self.assertEqual(result[0]["close"].tolist(), [1.0, 1.03])

    async def test_recovery_finishing_during_snapshot_requires_a_fresh_retry(self):
        self.storage.get_pending_recovery.side_effect = [
            {"next_ms": 0, "target_ms": 3540000},
            None,
        ]
        self.assertIsNone(await self.load())
        self.storage.get_pending_recovery.side_effect = None
        self.assertIsNotNone(await self.load())

    async def test_recovery_starting_during_snapshot_keeps_it_pending(self):
        self.storage.get_pending_recovery.side_effect = [
            None,
            {"next_ms": 0, "target_ms": 3540000},
        ]
        self.assertIsNone(await self.load())

    async def test_unconfirmed_write_blocks_even_with_newer_rows(self):
        self.storage.get_live_write_guard.return_value = {"boundary_ms": 0}
        self.assertIsNone(await self.load())
        self.storage.get_live_write_guard.return_value = None
        self.assertIsNotNone(await self.load())

    async def test_work_outside_closed_snapshot_does_not_block_it(self):
        self.storage.get_pending_recovery.return_value = {"next_ms": 3600000, "target_ms": 3660000}
        self.storage.get_live_write_guard.return_value = {"boundary_ms": 3600000}
        self.assertIsNotNone(await self.load())

    async def test_market_closure_can_resume_after_later_raw_storage_progress(self):
        self.rows = pd.DataFrame({"close": [1.0, 1.03]}, index=[-120000, 3600000])
        result = await self.load()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[0].index.tolist(), [-3600000])

    async def test_failed_protection_read_is_not_treated_as_no_pending_work(self):
        self.storage.get_pending_recovery.side_effect = ConnectionError("storage unavailable")
        with self.assertRaises(ConnectionError):
            await self.load()
        self.candles.assert_not_awaited()

    async def test_progress_is_captured_before_reading_closes_it_validates(self):
        import asyncio

        self.rows = pd.DataFrame({"close": [1.0, 1.01]}, index=[-60000, 3480000])

        async def racing_fetch(**kwargs):
            if kwargs["start_ms"] is None and kwargs["end_ms"] is None:
                await asyncio.sleep(0)
                self.rows.loc[3540000] = 1.03
            return await self.get_candles(**kwargs)

        self.candles.side_effect = racing_fetch
        result = await self.load()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(float(result[0].loc[0, "close"]), 1.03)

    async def test_invalid_final_close_is_not_replaced_by_an_earlier_minute(self):
        self.rows.loc[3480000] = 1.02
        self.rows.loc[3540000] = float("nan")
        self.rows = self.rows.sort_index()
        result = await self.load()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(pd.isna(result[0].loc[0, "close"]))
