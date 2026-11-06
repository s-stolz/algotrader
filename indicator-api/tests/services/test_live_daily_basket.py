import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
from app.services.live_daily_basket import LiveDailyBasket
from app.services.live_indicator_manager import LiveStreamSpec
from indicator_engine.core.history import UTC_DAY_MS


class DailyBasketTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.basket = LiveDailyBasket(LiveStreamSpec("123", "EURUSD", "M1", 5, None, {}))
        self.redis = Mock(xadd=AsyncMock(), xrevrange=AsyncMock(return_value=[]))
        self.frames = {
            asset: pd.DataFrame({"close": [1.0, 1.01, 1.02]}, index=[-60000, 0, 60000])
            for asset in self.basket.assets
        }
        self.fetch = patch(
            "app.services.anchored_indicator_service.get_candles", side_effect=self.get_candles
        )
        self.fetch.start()
        self.addCleanup(self.fetch.stop)

    async def get_candles(self, *, symbol, start_ms, end_ms, limit, **kwargs):
        frame = self.frames[symbol]
        if start_ms is not None:
            frame = frame.loc[frame.index >= start_ms]
        if end_ms is not None:
            frame = frame.loc[frame.index < end_ms]
        if limit is not None:
            frame = frame.tail(limit)
        frame = frame.copy()
        frame.index = pd.to_datetime(frame.index, unit="ms", utc=True)
        return frame

    def ingest(self, timestamp, close=1.03, assets=None, continuity="a"):
        for asset in assets or self.basket.assets:
            self.basket.ingest(
                asset, {"t": str(timestamp), "c": str(close), "continuity": continuity}
            )

    async def start(self):
        self.ingest(120000)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)

    def output(self):
        return json.loads(self.redis.xadd.call_args.args[1]["d"])

    async def test_midday_seed_and_intrabar_revision_match_historical_calculation(self):
        await self.start()
        first = self.output()
        self.ingest(120000, 1.05, [self.basket.assets[0]])
        await self.basket.publish(self.redis, 100)
        self.assertNotEqual(first, self.output())
        incremental = self.output()
        self.basket.needs_rebuild = True
        replay = self.basket.calculate()
        self.assertEqual(replay, [])
        np.testing.assert_allclose(
            list(incremental.values()), list(self.basket.published[120000].values())
        )
        self.assertEqual(len(self.output()), 8)

    async def test_next_candle_waits_for_all_pairs_and_never_carries_forward(self):
        await self.start()
        self.ingest(180000, assets=self.basket.assets[:-1])
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, 1)
        self.ingest(180000, 1.04, [self.basket.assets[-1]])
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, 2)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], "180000")

    async def test_missing_history_pauses_until_recovered_without_restart(self):
        saved = self.frames[self.basket.assets[-1]].copy()
        self.frames[self.basket.assets[-1]] = saved.drop(0)
        self.ingest(120000)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.redis.xadd.assert_not_awaited()
        self.assertTrue(self.basket.needs_history)
        self.frames[self.basket.assets[-1]] = saved
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], "120000")
        self.assertEqual(self.redis.xadd.call_args_list[0].args[1]["replay"], "1")

    async def test_gap_recovery_replays_missing_candles_and_corrects_daily_accumulation(self):
        await self.start()
        self.ingest(300000, 1.06)
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, 1)
        for frame in self.frames.values():
            frame.loc[120000] = 1.04
            frame.loc[180000] = 1.05
            frame.loc[240000] = 1.055
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(
            [call.args[1]["t"] for call in self.redis.xadd.call_args_list],
            ["120000", "120000", "180000", "240000", "300000"],
        )

    async def test_continuity_break_requires_closed_history_not_stale_live_rows(self):
        await self.start()
        self.ingest(180000, 1.04, continuity="b")
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, 1)
        for frame in self.frames.values():
            frame.loc[120000] = 1.035
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], "180000")

    async def test_older_correction_replays_prior_points_without_rewinding_live_tail(self):
        await self.start()
        self.ingest(180000, 1.04)
        await self.basket.publish(self.redis, 100)
        self.ingest(120000, 1.06, [self.basket.assets[0]])
        await self.basket.publish(self.redis, 100)
        correction = self.redis.xadd.call_args_list[-2].args[1]
        self.assertEqual(correction["t"], "120000")
        self.assertEqual(correction["replay"], "1")
        self.assertEqual(self.basket.last_published, 180000)

    async def test_midnight_reset_and_different_predecessor_times(self):
        await self.start()
        for i, frame in enumerate(self.frames.values()):
            frame.loc[UTC_DAY_MS - (i + 1) * 60000] = 1.03
        self.ingest(UTC_DAY_MS, 1.03)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        np.testing.assert_allclose(list(self.output().values()), 0.0)
        for rows in self.basket.live.values():
            self.assertEqual([t for t in rows if t < UTC_DAY_MS], [120000])

    async def test_cursors_capture_existing_tail_before_history_fetch(self):
        self.redis.xrevrange.return_value = [("17-0", {"t": "120000", "c": "1.03"})]
        await self.basket.initialize(self.redis)
        self.assertEqual(set(self.basket.cursors.values()), {"17-0"})
        await self.basket.recover()
        self.ingest(120000, 1.05, [self.basket.assets[0]])
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.basket.live[self.basket.assets[0]][120000], 1.05)

    async def test_live_manager_reads_all_sources_recovers_and_stops_on_last_reference(self):
        import asyncio

        from app.schemas_live import LiveIndicatorStreamRequest
        from app.services.candle_cache import CandleCache
        from app.services.live_indicator_manager import LiveIndicatorManager

        queue = asyncio.Queue()

        async def read(*args, **kwargs):
            try:
                result = await asyncio.wait_for(queue.get(), timeout=0.01)
            except TimeoutError:
                return []
            if isinstance(result, Exception):
                raise result
            return result

        self.redis.xread = AsyncMock(side_effect=read)
        self.redis.close = AsyncMock()
        manager = LiveIndicatorManager(CandleCache())
        manager._redis = self.redis
        request = LiveIndicatorStreamRequest(
            account_id="123",
            symbol="EURUSD",
            timeframe="M1",
            indicator_id=5,
        )
        try:
            started = await manager.start_stream(request)
            shared = await manager.start_stream(request)
            self.assertEqual(started.stream_id, shared.stream_id)
            self.assertEqual(shared.status, "already_running")
            session = next(iter(manager._sessions_by_key.values()))
            basket = session.daily_basket
            self.assertIsNotNone(basket)
            assert basket is not None
            await queue.put(
                [(stream, [("1-0", {"t": "120000", "c": "1.03"})]) for stream in basket.streams]
            )
            async with asyncio.timeout(3):
                while not self.redis.xadd.await_count:
                    await asyncio.sleep(0.01)
            self.assertEqual(set(self.redis.xread.call_args.args[0]), set(basket.streams))
            await queue.put(ConnectionError("redis disconnected"))
            async with asyncio.timeout(3):
                while not basket.awaiting_snapshot:
                    await asyncio.sleep(0.01)
            for frame in self.frames.values():
                frame.loc[120000] = 1.035
            basket.next_recovery = 0
            await queue.put(
                [(stream, [("2-0", {"t": "180000", "c": "1.04"})]) for stream in basket.streams]
            )
            async with asyncio.timeout(3):
                while self.redis.xadd.call_args.args[1]["t"] != "180000":
                    await asyncio.sleep(0.01)
            self.assertFalse((await manager.stop_stream(request)).stopped)
            assert session.task is not None
            self.assertFalse(session.task.done())
            self.assertTrue((await manager.stop_stream(request)).stopped)
            self.assertTrue(session.task.done())
            self.assertIsNone(await manager.get_status(started.stream_id))
        finally:
            await manager.shutdown()

    async def test_current_values_match_historical_api_for_same_complete_sources(self):
        from app.services.anchored_indicator_service import calculate_anchored_indicator

        await self.start()
        self.ingest(120000, 1.05, [self.basket.assets[0]])
        await self.basket.publish(self.redis, 100)
        for asset, frame in self.frames.items():
            frame.loc[120000] = self.basket.live[asset][120000]
        historical = await calculate_anchored_indicator(
            engine_id="currency_strength",
            parameters={},
            symbol="EURUSD",
            exchange=None,
            timeframe="M1",
            start_ms=120000,
            end_ms=180000,
            limit=None,
        )
        np.testing.assert_allclose(
            list(self.output().values()),
            historical.iloc[-1].to_numpy(dtype=float),
        )

    async def test_daily_timeframe_uses_previous_available_candle(self):
        self.basket = LiveDailyBasket(LiveStreamSpec("123", "EURUSD", "D1", 5, None, {}))
        for index, asset in enumerate(self.basket.assets):
            self.frames[asset] = pd.DataFrame({"close": [1.03]}, index=[-(index + 1) * UTC_DAY_MS])
        self.ingest(0, 1.03)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        np.testing.assert_allclose(list(self.output().values()), 0.0)

    async def test_same_candle_reconnect_recovers_its_authoritative_close_after_rollover(self):
        from app.services.anchored_indicator_service import calculate_anchored_indicator

        await self.start()
        self.ingest(120000, 1.031, continuity="b")
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        published = self.redis.xadd.await_count
        self.ingest(180000, 1.04, continuity="b")
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, published)

        self.ingest(120000, 1.034, continuity="b")
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, published)

        for frame in self.frames.values():
            frame.loc[120000] = 1.035
            frame.loc[180000] = 1.04
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], "180000")
        historical = await calculate_anchored_indicator(
            engine_id="currency_strength",
            parameters={},
            symbol="EURUSD",
            exchange=None,
            timeframe="M1",
            start_ms=180000,
            end_ms=240000,
            limit=None,
        )
        np.testing.assert_allclose(list(self.output().values()), historical.iloc[-1].to_numpy())
        self.assertFalse(self.basket.needs_history)

    async def test_reconnect_protects_the_newest_inflight_candle_of_a_partial_basket(self):
        await self.start()
        self.ingest(180000, 1.04, [self.basket.assets[0]])
        self.basket.require_recovery()
        for frame in self.frames.values():
            frame.loc[120000] = 1.035
        self.ingest(180000, 1.04, self.basket.assets[1:])
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        published = self.redis.xadd.await_count
        self.ingest(240000, 1.05)
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, published)
        for frame in self.frames.values():
            frame.loc[180000] = 1.045
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], "240000")

    async def test_midnight_waits_for_known_predecessors_to_reach_storage(self):
        from app.services.anchored_indicator_service import calculate_anchored_indicator

        times = np.arange(-60000, UTC_DAY_MS - 60000, 60000)
        for asset in self.basket.assets:
            self.frames[asset] = pd.DataFrame({"close": np.ones(len(times))}, index=times)
        prior = UTC_DAY_MS - 60000
        self.ingest(prior, 1.03)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        published = self.redis.xadd.await_count
        self.ingest(UTC_DAY_MS, 1.04)
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.await_count, published)

        for frame in self.frames.values():
            frame.loc[prior] = 1.035
            frame.loc[UTC_DAY_MS] = 1.04
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.assertEqual(self.redis.xadd.call_args.args[1]["t"], str(UTC_DAY_MS))
        historical = await calculate_anchored_indicator(
            engine_id="currency_strength",
            parameters={},
            symbol="EURUSD",
            exchange=None,
            timeframe="M1",
            start_ms=UTC_DAY_MS,
            end_ms=UTC_DAY_MS + 60000,
            limit=None,
        )
        np.testing.assert_allclose(list(self.output().values()), historical.iloc[-1].to_numpy())
        self.assertFalse(self.basket.needs_history)

    async def test_late_previous_day_source_prevents_an_older_predecessor_from_being_used(self):
        prior = UTC_DAY_MS - 60000
        for asset in self.basket.assets:
            self.frames[asset] = pd.DataFrame({"close": [1.0]}, index=[prior - 60000])
        self.ingest(prior, 1.03, self.basket.assets[:-1])
        self.ingest(UTC_DAY_MS, 1.04, self.basket.assets[:-1])
        await self.basket.recover()
        self.ingest(prior, 1.03, [self.basket.assets[-1]])
        self.ingest(UTC_DAY_MS, 1.04, [self.basket.assets[-1]])
        for asset in self.basket.assets[:-1]:
            self.frames[asset].loc[prior] = 1.03
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.redis.xadd.assert_not_awaited()

        self.frames[self.basket.assets[-1]].loc[prior] = 1.03
        await self.basket.recover()
        await self.basket.publish(self.redis, 100)
        self.redis.xadd.assert_awaited_once()
