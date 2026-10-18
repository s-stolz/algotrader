"""Startup/restart behavior through controlled broker, Redis, and storage adapters."""

import asyncio
import copy
import logging
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

from app.config import load_config
from main import IngestionService

BOUNDARY = 1791158400000  # October 5, 2026 UTC
RESUMED = 1792281600000  # October 18, 2026 UTC
NOW = RESUMED + 180000


def candle(timestamp, value=1, session="a"):
    return dict(
        t=timestamp, o=value, h=value, l=value, c=value, v=value, continuity="v1:" + session * 32
    )


async def eventually(predicate):
    async with asyncio.timeout(4):
        while not predicate():
            await asyncio.sleep(0.01)


class Storage:
    def __init__(self, symbols=("BTC",)):
        self.markets = [
            dict(symbol_id=i + 1, symbol=s, exchange="TEST") for i, s in enumerate(symbols)
        ]
        self.rows = {s: {BOUNDARY: dict(timestamp_ms=BOUNDARY, close=1)} for s in symbols}
        self.pending = {}
        self.guards = {}
        self.protected = set()
        self.lock = threading.Lock()
        self.fail_read = set()
        self.fail_save = set()
        self.fail_progress = False
        self.fail_history_write = 0
        self.history_writes = 0
        self.live_writes = 0
        self.fail_live_write = 0
        self.on_live_failure = lambda: None
        self.fail_pending_read = False

    def get_markets(self):
        return self.markets

    def get_latest_m1_candle(self, symbol, exchange=None):
        if symbol in self.fail_read:
            raise RuntimeError("latest unavailable")
        return self.rows[symbol][max(self.rows[symbol])] if self.rows[symbol] else None

    def get_pending_recovery(self, symbol_id, account):
        if self.fail_pending_read:
            raise RuntimeError("pending unavailable")
        with self.lock:
            return copy.deepcopy(self.pending.get((symbol_id, account)))

    def begin_recovery(self, symbol_id, account_id, start_ms, target_ms, trigger):
        if symbol_id in self.fail_save:
            raise RuntimeError("save unavailable")
        with self.lock:
            key = (symbol_id, account_id)
            prior = self.pending.get(key)
            item = dict(
                symbol_id=symbol_id,
                account_id=account_id,
                recovery_id=prior["recovery_id"] if prior else str(uuid4()),
                revision=prior["revision"] + 1 if prior else 1,
                next_ms=min(prior["next_ms"], start_ms) if prior else start_ms,
                target_ms=max(prior["target_ms"], target_ms) if prior else target_ms,
                trigger=trigger,
            )
            self.pending[key] = item
            self.protected.add(symbol_id)
            return copy.deepcopy(item)

    def advance_recovery(self, pending, next_ms):
        if self.fail_progress:
            raise RuntimeError("progress receipt lost")
        with self.lock:
            key = (pending["symbol_id"], pending["account_id"])
            if self.pending.get(key) != pending:
                return False
            if next_ms > pending["target_ms"]:
                del self.pending[key]
            else:
                self.pending[key]["next_ms"] = next_ms
            return True

    def get_live_write_guard(self, symbol_id, account):
        with self.lock:
            return copy.deepcopy(self.guards.get((symbol_id, account)))

    def begin_live_write(self, symbol_id, account_id, boundary_ms):
        with self.lock:
            key = (symbol_id, account_id)
            prior = self.guards.get(key)
            guard = dict(
                symbol_id=symbol_id,
                account_id=account_id,
                write_id=str(uuid4()),
                boundary_ms=min(prior["boundary_ms"], boundary_ms) if prior else boundary_ms,
            )
            self.guards[key] = guard
            return copy.deepcopy(guard)

    def finish_live_write(self, guard):
        with self.lock:
            key = (guard["symbol_id"], guard["account_id"])
            if self.guards.get(key) != guard:
                return False
            del self.guards[key]
            return True

    def write_candles(self, symbol, candles, exchange=None):
        self.live_writes += 1
        if self.live_writes == self.fail_live_write:
            self.on_live_failure()
            raise RuntimeError("live write unavailable")
        # Writes are observable only after pending protection on this source.
        assert next(m["symbol_id"] for m in self.markets if m["symbol"] == symbol) in self.protected
        for item in candles:
            self.rows[symbol].setdefault(item["timestamp_ms"], item)

    def write_historical_candles(self, symbol, candles, start_ms, end_ms, exchange=None):
        self.history_writes += 1
        if self.history_writes == self.fail_history_write:
            raise RuntimeError("partial multi-batch write")
        for item in candles:
            self.rows[symbol][item["timestamp_ms"]] = item

    def close(self):
        pass


class RedisInput:
    def __init__(self):
        self.queues = {}
        self.next_id = 2

    async def ping(self):
        return True

    async def xrevrange(self, stream, count):
        return [(b"1-0", {})]

    async def xread(self, streams, **kwargs):
        stream = next(iter(streams))
        result = await self.queues.setdefault(stream, asyncio.Queue()).get()
        if isinstance(result, Exception):
            raise result
        return result

    async def publish(self, symbol, bars):
        stream = f"candles:12345:{symbol}:M1"
        entries = [
            (
                f"{i + self.next_id}-0".encode(),
                {key.encode(): str(value).encode() for key, value in bar.items()},
            )
            for i, bar in enumerate(bars)
        ]
        self.next_id += len(bars)
        await self.queues.setdefault(stream, asyncio.Queue()).put([(stream.encode(), entries)])

    async def close(self):
        pass


class Broker:
    def __init__(self):
        self.allow_history = asyncio.Event()
        self.requests = []
        self.fail = set()
        self.empty = set()
        self.on_start = lambda: None

    async def start_trendbar_stream(self, symbol, **kwargs):
        self.on_start()

    async def stream_trendbars(self, symbol, start_time, end_time, **kwargs):
        self.requests.append((symbol, start_time, end_time))
        await self.allow_history.wait()
        if symbol in self.fail:
            raise RuntimeError("history unavailable")
        if symbol in self.empty:
            return
        for timestamp in (BOUNDARY, BOUNDARY + 60000, BOUNDARY + 86400000, RESUMED):
            if start_time <= timestamp <= end_time:
                yield candle(timestamp, 8)

    async def aclose(self):
        pass

    async def get_meta_health(self):
        return {"components": {"ctrader": {"status": "up"}}}


class DurableRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.services = []
        logging.disable(logging.CRITICAL)

    async def asyncTearDown(self):
        for service in self.services:
            await service.shutdown()
        logging.disable(logging.NOTSET)

    async def start(self, storage, broker, *, lookback=365 * 5, now=lambda: NOW, redis=None):
        redis = redis or RedisInput()
        config = replace(
            load_config(),
            history_lookback_days=lookback,
            history_start_date=None,
            startup_backfill_concurrency=1,
            recovery_backoff_initial_seconds=1,
            recovery_backoff_max_seconds=1,
        )
        with patch("main.load_config", return_value=config), patch.object(
            IngestionService, "_utc_now_ms", side_effect=now
        ):
            service = IngestionService()
        service._utc_now_ms = now
        service.db_client.close()
        service.db_client = storage
        await service.broker_client.aclose()
        service.broker_client.close()
        service.broker_client = broker
        self.services.append(service)
        with patch("main.Redis.from_url", return_value=redis):
            await service.startup()
        await service.start_consumers()
        return service, redis

    async def test_brief_reconnect_and_broker_restart_recover_after_startup_completed(self):
        for session in ("b", "c"):
            storage, broker = Storage(), Broker()
            broker.allow_history.set()
            clock = [BOUNDARY + 120000]
            service, redis = await self.start(storage, broker, now=lambda: clock[0])
            await eventually(lambda: not storage.pending and bool(broker.requests))
            await redis.publish("BTC", [candle(BOUNDARY + 60000), candle(BOUNDARY + 120000)])
            await eventually(lambda: service._state_by_id[1].continuity is not None)
            await eventually(lambda: not storage.pending)
            broker.allow_history.clear()
            clock[0] = NOW
            # Health remains up throughout: only the published identity changes.
            self.assertTrue(await service._is_broker_connected())
            await redis.publish(
                "BTC", [candle(RESUMED, session=session), candle(RESUMED + 60000, session=session)]
            )
            await eventually(lambda: RESUMED in storage.rows["BTC"])
            pending = next(iter(storage.pending.values()))
            self.assertLessEqual(pending["next_ms"], BOUNDARY + 120000)
            self.assertEqual(pending["target_ms"], NOW - 1)
            broker.allow_history.set()
            await eventually(lambda: not storage.pending)
            self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)
            self.assertEqual(storage.rows["BTC"][BOUNDARY + 86400000]["close"], 8)
            self.assertEqual(storage.rows["BTC"][BOUNDARY + 60000]["close"], 8)
            await service.shutdown()

    async def test_mixed_session_batch_and_another_reconnect_retain_earliest_pending(self):
        storage, broker = Storage(), Broker()
        clock = [NOW]
        service, redis = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: bool(broker.requests))
        await redis.publish(
            "BTC",
            [
                candle(RESUMED),
                candle(RESUMED + 60000),
                candle(RESUMED + 60000, session="b"),
                candle(RESUMED + 120000, session="b"),
            ],
        )
        await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"])
        before = next(iter(storage.pending.values())).copy()
        self.assertEqual(before["next_ms"], BOUNDARY)
        clock[0] += 120000
        await redis.publish(
            "BTC", [candle(RESUMED + 180000, session="c"), candle(RESUMED + 240000, session="c")]
        )
        await eventually(lambda: RESUMED + 180000 in storage.rows["BTC"])
        after = next(iter(storage.pending.values()))
        self.assertEqual(after["next_ms"], BOUNDARY)
        self.assertGreater(after["revision"], before["revision"])
        self.assertEqual(after["target_ms"], NOW + 120000 - 1)
        await service.shutdown()
        storage.fail_read.add("BTC")
        await self.start(storage, broker, lookback=1, now=lambda: clock[0])
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 60000]["close"], 8)
        self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)

    async def test_invalid_and_retained_legacy_rows_are_recovered_without_live_commit(self):
        for invalid in (None, "", "v1:bad", "v2:" + "a" * 32):
            storage, broker = Storage(), Broker()
            service, redis = await self.start(storage, broker)
            await eventually(lambda: bool(broker.requests))
            bars = [candle(RESUMED), candle(RESUMED + 60000)]
            for bar in bars:
                if invalid is None:
                    del bar["continuity"]
                else:
                    bar["continuity"] = invalid
            await redis.publish("BTC", bars)
            await eventually(
                lambda: next(iter(storage.pending.values()))["trigger"] == "invalid-continuity"
            )
            self.assertNotIn(RESUMED, storage.rows["BTC"])
            broker.allow_history.set()
            await eventually(lambda: not storage.pending)
            self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)
            await service.shutdown()

    async def test_new_session_save_failure_cannot_write_or_acknowledge_its_batch(self):
        storage, broker = Storage(), Broker()
        service, redis = await self.start(storage, broker)
        await eventually(lambda: bool(broker.requests))
        storage.fail_save.add(1)
        await redis.publish(
            "BTC", [candle(RESUMED, session="b"), candle(RESUMED + 60000, session="b")]
        )
        await eventually(lambda: not service._state_by_id[1].live_ready.is_set())
        self.assertNotIn(RESUMED, storage.rows["BTC"])
        assert service.consumer is not None
        self.assertNotIn(service._state_by_id[1].stream_key, service.consumer._last_ids)
        # Cancel during retry, then protected startup must recover the same old interval.
        await service.shutdown()
        storage.fail_save.clear()
        await self.start(storage, broker, lookback=1)
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 60000]["close"], 8)

    async def test_failed_later_session_in_mixed_batch_replays_only_unacknowledged_run(self):
        storage, broker = Storage(), Broker()
        service, redis = await self.start(storage, broker)
        await eventually(lambda: bool(broker.requests))
        writes = []
        original = storage.write_candles

        def write(symbol, candles, exchange=None):
            writes.extend(c["timestamp_ms"] for c in candles)
            original(symbol, candles, exchange)
            if any(c["timestamp_ms"] == RESUMED for c in candles):
                storage.fail_save.add(1)

        storage.write_candles = write
        await redis.publish(
            "BTC",
            [
                candle(RESUMED),
                candle(RESUMED + 60000),
                candle(RESUMED + 60000, session="b"),
                candle(RESUMED + 120000, session="b"),
            ],
        )
        await eventually(
            lambda: RESUMED in storage.rows["BTC"]
            and not service._state_by_id[1].live_ready.is_set()
        )
        self.assertNotIn(RESUMED + 60000, storage.rows["BTC"])
        storage.fail_save.clear()
        async with asyncio.timeout(7):
            while RESUMED + 60000 not in storage.rows["BTC"]:
                await asyncio.sleep(0.01)
        self.assertEqual(writes.count(RESUMED), 1)
        self.assertEqual(writes.count(RESUMED + 60000), 1)
        self.assertEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY)
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 86400000]["close"], 8)

    async def test_old_open_candle_is_recovered_instead_of_committing_partial_values(self):
        storage, broker = Storage(), Broker()
        service, redis = await self.start(storage, broker)
        await eventually(lambda: bool(broker.requests))
        await redis.publish("BTC", [candle(RESUMED, 99)])
        await eventually(lambda: service._state_by_id[1].continuity is not None)
        await redis.publish(
            "BTC", [candle(RESUMED + 60000, session="b"), candle(RESUMED + 120000, session="b")]
        )
        await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"])
        self.assertNotIn(RESUMED, storage.rows["BTC"])
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)

    async def test_silent_weekend_does_not_change_session_or_schedule_more_history(self):
        storage, broker = Storage(), Broker()
        broker.empty.add("BTC")
        broker.allow_history.set()
        clock = [NOW]
        service, redis = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: not storage.pending and bool(broker.requests))
        await redis.publish("BTC", [candle(RESUMED)])
        await eventually(lambda: service._state_by_id[1].continuity is not None)
        await eventually(lambda: not storage.pending)
        count = len(broker.requests)
        session = service._state_by_id[1].continuity
        clock[0] += 7 * 86400000
        await asyncio.sleep(0.05)
        self.assertEqual(len(broker.requests), count)
        self.assertEqual(service._state_by_id[1].continuity, session)
        self.assertFalse(storage.pending)

    async def test_old_boundary_survives_live_writes_shutdown_and_rolling_restart(self):
        storage, broker = Storage(), Broker()
        service, redis = await self.start(storage, broker)
        await eventually(lambda: bool(broker.requests))
        self.assertEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY)
        await redis.publish("BTC", [candle(RESUMED), candle(RESUMED + 60000)])
        await eventually(lambda: RESUMED in storage.rows["BTC"])
        await service.shutdown()
        storage.fail_read.add("BTC")  # Existing pending work must precede latest lookup.
        restarted, _ = await self.start(storage, broker, lookback=1)
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][BOUNDARY]["close"], 8)
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 60000]["close"], 8)
        self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)
        self.assertTrue(all(end < NOW for _, _, end in broker.requests))
        self.assertLessEqual(max(end - start for _, start, end in broker.requests), 86400000)
        await restarted.shutdown()

    async def test_read_or_save_failure_protects_market_while_other_market_progresses(self):
        for failure in ("read", "save"):
            storage, broker = Storage(("BAD", "GOOD")), Broker()
            if failure == "read":
                storage.fail_read.add("BAD")
            else:
                storage.fail_save.add(1)
            broker.allow_history.set()
            service, redis = await self.start(storage, broker)
            await eventually(lambda: storage.rows["GOOD"][BOUNDARY]["close"] == 8)
            await redis.publish("BAD", [candle(RESUMED), candle(RESUMED + 60000)])
            await asyncio.sleep(0.02)
            self.assertNotIn(RESUMED, storage.rows["BAD"])
            self.assertFalse(service._state_by_id[1].live_ready.is_set())
            await service.shutdown()

    async def test_failed_market_releases_global_capacity_and_empty_history_completes(self):
        storage, broker = Storage(("BAD", "GOOD")), Broker()
        broker.fail.add("BAD")
        broker.empty.add("GOOD")
        storage.rows["GOOD"].clear()
        broker.allow_history.set()
        service, _ = await self.start(storage, broker, lookback=1)
        await eventually(
            lambda: any(k[0] == 1 for k in storage.pending)
            and not any(k[0] == 2 for k in storage.pending)
            and any(s == "GOOD" for s, _, _ in broker.requests)
        )
        self.assertFalse(storage.rows["GOOD"])  # No synthetic candles during inactivity.
        await service.shutdown()

    async def test_partial_writes_or_lost_progress_replay_original_window_on_restart(self):
        for failure in ("write", "progress"):
            storage, broker = Storage(), Broker()
            storage.fail_history_write = 2 if failure == "write" else 0
            storage.fail_progress = failure == "progress"
            broker.allow_history.set()
            service, _ = await self.start(storage, broker)
            service.CHUNK_SIZE = 1
            await eventually(lambda: storage.history_writes >= (2 if failure == "write" else 1))
            await service.shutdown()
            self.assertEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY)
            storage.fail_history_write = 0
            storage.fail_progress = False
            await self.start(storage, broker, lookback=1)
            await eventually(lambda: not storage.pending)
            self.assertEqual(storage.rows["BTC"][BOUNDARY + 60000]["close"], 8)
            self.assertGreaterEqual(sum(start == BOUNDARY for _, start, _ in broker.requests), 2)

    async def test_subscription_setup_interval_is_included_and_new_revision_survives(self):
        storage, broker = Storage(), Broker()
        clock = [RESUMED]
        broker.on_start = lambda: clock.__setitem__(0, NOW)
        service, _ = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: bool(broker.requests))
        first = next(iter(storage.pending.values())).copy()
        self.assertEqual(first["target_ms"], NOW - 1)
        clock[0] += 60000
        await service.request_recovery(service._state_by_id[1], "test-interruption")
        self.assertEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY)
        self.assertGreater(next(iter(storage.pending.values()))["revision"], first["revision"])
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertTrue(any(end == NOW + 59999 for _, _, end in broker.requests))

    async def test_first_closed_live_batch_protects_open_minute_at_subscription_handoff(self):
        storage, broker = Storage(), Broker()
        clock = [RESUMED + 30000]
        service, redis = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: bool(broker.requests))
        self.assertEqual(next(iter(storage.pending.values()))["target_ms"], RESUMED - 1)
        # No additional message updates the subscription's open minute. Its
        # exclusive Redis tail therefore cannot supply that missing Candle.
        clock[0] = NOW
        await redis.publish("BTC", [candle(RESUMED + 60000), candle(RESUMED + 120000)])
        await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"])
        self.assertEqual(next(iter(storage.pending.values()))["target_ms"], NOW - 1)
        broker.allow_history.set()
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)

    async def test_queued_closed_callbacks_cannot_retire_the_open_handoff_minute(self):
        storage, broker = Storage(), Broker()
        broker.allow_history.set()
        clock = [RESUMED + 30000]
        service, redis = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: not storage.pending and bool(broker.requests))
        # These queued bars close a live Candle before the excluded subscription
        # minute has closed. They cannot establish coverage of that minute.
        await redis.publish("BTC", [candle(RESUMED - 120000), candle(RESUMED - 60000)])
        await eventually(lambda: storage.live_writes > 0 and not storage.pending)
        self.assertNotIn(RESUMED, storage.rows["BTC"])
        self.assertTrue(all(end < RESUMED for _, _, end in broker.requests))

        clock[0] = NOW
        await redis.publish("BTC", [candle(RESUMED + 60000), candle(RESUMED + 120000)])
        await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"] and not storage.pending)
        self.assertIn(RESUMED, storage.rows["BTC"])
        self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)

    async def test_late_handoff_is_durable_through_old_sessions_and_restart(self):
        for session in ("a", "b"):
            with self.subTest(resumed_session=session):
                storage, broker = Storage(), Broker()
                broker.allow_history.set()
                clock = [RESUMED + 30000]
                service, redis = await self.start(storage, broker, now=lambda: clock[0])
                await eventually(lambda: not storage.pending and bool(broker.requests))
                await redis.publish("BTC", [candle(RESUMED - 120000), candle(RESUMED - 60000)])
                await eventually(lambda: storage.live_writes > 0 and not storage.pending)
                # A late old-session run can itself cause a new interruption.
                # Neither that run nor out-of-order bars can replace the earlier
                # handoff with a newer latest-Candle boundary.
                clock[0] = NOW
                broker.allow_history.clear()
                await redis.publish(
                    "BTC",
                    [
                        candle(RESUMED - 180000, session=session),
                        candle(RESUMED - 120000, session=session),
                        candle(RESUMED + 60000, session=session),
                        candle(RESUMED + 120000, session=session),
                    ],
                )
                await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"])
                self.assertTrue(storage.pending)
                self.assertLessEqual(next(iter(storage.pending.values()))["next_ms"], RESUMED)
                self.assertNotIn(RESUMED, storage.rows["BTC"])
                await service.shutdown()

                # Durable work takes priority over a fresh latest lookup and a
                # newer rolling lookback after an abrupt recovery interruption.
                storage.fail_read.add("BTC")
                restarted, _ = await self.start(storage, broker, lookback=1, now=lambda: clock[0])
                broker.allow_history.set()
                await eventually(lambda: not storage.pending)
                self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)
                await restarted.shutdown()

    async def test_minute_crossing_save_preserves_session_and_dependency_handoffs(self):
        for trigger in ("continuity-change", "redis-read-failure"):
            with self.subTest(trigger=trigger):
                storage, broker = Storage(), Broker()
                broker.allow_history.set()
                clock = [RESUMED + 30000]
                service, redis = await self.start(storage, broker, now=lambda: clock[0])
                await eventually(lambda: not storage.pending and bool(broker.requests))
                await redis.publish("BTC", [candle(RESUMED - 120000), candle(RESUMED - 60000)])
                await eventually(lambda: storage.live_writes > 0 and not storage.pending)
                original_begin = storage.begin_recovery
                saved_targets = []

                expected_trigger = trigger

                def cross_minute_during_save(symbol_id, account_id, start_ms, target_ms, trigger):
                    saved = original_begin(symbol_id, account_id, start_ms, target_ms, trigger)
                    if trigger == expected_trigger and not saved_targets:
                        saved_targets.append(saved["target_ms"])
                        clock[0] = RESUMED + 60010
                    return saved

                storage.begin_recovery = cross_minute_during_save
                clock[0] = RESUMED + 59990
                if trigger == "continuity-change":
                    session = "b"
                    await redis.publish(
                        "BTC",
                        [
                            candle(RESUMED - 120000, session=session),
                            candle(RESUMED + 60000, session=session),
                        ],
                    )
                else:
                    session = "a"
                    stream = "candles:12345:BTC:M1"
                    await redis.queues[stream].put(OSError("controlled Redis read interruption"))
                    await redis.publish("BTC", [candle(RESUMED + 60000)])
                await eventually(lambda: storage.live_writes > 1 and not storage.pending)
                self.assertEqual(saved_targets, [RESUMED - 1])

                clock[0] = NOW
                await redis.publish("BTC", [candle(RESUMED + 120000, session=session)])
                await eventually(
                    lambda: RESUMED + 60000 in storage.rows["BTC"] and not storage.pending
                )
                await service.shutdown()
                before_restart = len(broker.requests)
                await self.start(storage, broker, lookback=1, now=lambda: clock[0])
                await eventually(
                    lambda: len(broker.requests) > before_restart and not storage.pending
                )
                self.assertIn(RESUMED, storage.rows["BTC"])
                self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)

    async def test_shutdown_drains_inflight_write_before_closing_storage(self):
        for fails in (False, True):
            storage, broker = Storage(), Broker()
            entered, release = threading.Event(), threading.Event()
            original = storage.write_historical_candles
            closed = []

            def blocked_write(symbol, candles, start_ms, end_ms, exchange=None):
                entered.set()
                release.wait(3)
                self.assertFalse(closed)
                if fails:
                    raise RuntimeError("in-flight write failed during shutdown")
                return original(symbol, candles, start_ms, end_ms, exchange)

            storage.write_historical_candles = blocked_write
            storage.close = lambda: closed.append(True)
            broker.allow_history.set()
            service, _ = await self.start(storage, broker)
            await eventually(entered.is_set)
            first = asyncio.create_task(service.shutdown())
            second = asyncio.create_task(service.shutdown())
            await asyncio.sleep(0.02)
            self.assertFalse(closed)
            release.set()
            await asyncio.wait_for(asyncio.gather(first, second), 0.5)
            self.assertEqual(closed, [True])
            self.assertEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY)

    async def test_empty_start_date_today_can_complete_without_open_minute(self):
        storage, broker = Storage(), Broker()
        storage.rows["BTC"].clear()
        broker.allow_history.set()
        service, _ = await self.start(storage, broker, lookback=1)
        await eventually(lambda: bool(broker.requests))
        await eventually(lambda: not storage.pending)
        self.assertTrue(all(start >= NOW - 86400000 for _, start, _ in broker.requests))
        self.assertEqual(load_config().history_start_ms(NOW), NOW - 90 * 86400000)
        configured = replace(
            load_config(), history_start_date="2026-10-18", history_lookback_days=None
        )
        self.assertEqual(configured.history_start_ms(NOW), RESUMED)
        await service.shutdown()

    async def test_redis_failure_with_unchanged_session_protects_failed_lookup_and_save(self):
        for failure in ("read", "save", "pending"):
            with self.subTest(failure=failure):
                storage, broker = Storage(), Broker()
                clock = [BOUNDARY + 120000]
                broker.allow_history.set()
                service, redis = await self.start(storage, broker, now=lambda: clock[0])
                await eventually(lambda: not storage.pending and bool(broker.requests))
                await redis.publish("BTC", [candle(BOUNDARY + 60000), candle(BOUNDARY + 120000)])
                await eventually(lambda: service._state_by_id[1].continuity is not None)
                await eventually(lambda: not storage.pending)
                session = service._state_by_id[1].continuity
                broker.allow_history.clear()
                clock[0] = NOW
                if failure == "read":
                    storage.fail_read.add("BTC")
                elif failure == "save":
                    storage.fail_save.add(1)
                else:
                    storage.fail_pending_read = True
                stream = service._state_by_id[1].stream_key
                await redis.queues[stream].put(OSError("Redis read unavailable"))
                await redis.publish("BTC", [candle(RESUMED), candle(RESUMED + 60000)])
                await eventually(lambda: not service._state_by_id[1].live_ready.is_set())
                self.assertNotIn(RESUMED, storage.rows["BTC"])
                storage.fail_read.clear()
                storage.fail_save.clear()
                storage.fail_pending_read = False
                await eventually(lambda: RESUMED in storage.rows["BTC"])
                pending = next(iter(storage.pending.values()))
                self.assertLessEqual(pending["next_ms"], BOUNDARY + 120000)
                self.assertEqual(service._state_by_id[1].continuity, session)
                broker.allow_history.set()
                await eventually(lambda: not storage.pending)
                self.assertEqual(storage.rows["BTC"][BOUNDARY + 86400000]["close"], 8)
                self.assertEqual(storage.rows["BTC"][RESUMED]["close"], 8)
                await service.shutdown()

    async def test_live_database_failure_preserves_failed_batch_and_boundary_on_restart(self):
        storage, broker = Storage(), Broker()
        clock = [BOUNDARY + 120000]
        broker.allow_history.set()
        service, redis = await self.start(storage, broker, now=lambda: clock[0])
        await eventually(lambda: not storage.pending and bool(broker.requests))
        await redis.publish("BTC", [candle(BOUNDARY + 60000), candle(BOUNDARY + 120000)])
        await eventually(lambda: storage.live_writes == 1 and not storage.pending)
        # Startup/continuity work is complete; health and metadata stay unchanged.
        clock[0] = NOW
        broker.allow_history.clear()
        service.CHUNK_SIZE = 1
        storage.fail_live_write = storage.live_writes + 3
        storage.on_live_failure = lambda: storage.fail_save.add(1)
        await redis.publish(
            "BTC", [candle(RESUMED), candle(RESUMED + 60000), candle(RESUMED + 120000)]
        )
        await eventually(lambda: not service._state_by_id[1].live_ready.is_set())
        self.assertIn(RESUMED, storage.rows["BTC"])
        self.assertNotIn(RESUMED + 60000, storage.rows["BTC"])
        # Retry cannot choose the now-newer latest row or skip the failed chunk.
        storage.fail_save.clear()
        await eventually(lambda: RESUMED + 60000 in storage.rows["BTC"])
        pending = next(iter(storage.pending.values()))
        self.assertLessEqual(pending["next_ms"], BOUNDARY + 120000)
        await service.shutdown()
        storage.fail_live_write = 0
        storage.fail_progress = True
        broker.allow_history.set()
        restarted, resumed = await self.start(storage, broker, lookback=1, now=lambda: clock[0])
        await eventually(lambda: storage.rows["BTC"][BOUNDARY + 60000]["close"] == 8)
        self.assertLessEqual(next(iter(storage.pending.values()))["next_ms"], BOUNDARY + 120000)
        storage.fail_progress = False
        await eventually(lambda: not storage.pending)
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 86400000]["close"], 8)
        await resumed.publish("BTC", [candle(RESUMED + 120000), candle(RESUMED + 180000)])
        await eventually(lambda: RESUMED + 120000 in storage.rows["BTC"])
        await restarted.shutdown()

    async def test_dependency_outage_in_one_market_does_not_block_healthy_market(self):
        storage, broker = Storage(("BAD", "GOOD")), Broker()
        broker.allow_history.set()
        service, redis = await self.start(storage, broker)
        await eventually(lambda: not storage.pending and len(broker.requests) >= 2)
        await redis.publish("BAD", [candle(RESUMED), candle(RESUMED + 60000)])
        await eventually(lambda: service._state_by_id[1].continuity is not None)
        storage.fail_save.add(1)
        await redis.queues[service._state_by_id[1].stream_key].put(OSError("read lost"))
        await eventually(lambda: not service._state_by_id[1].live_ready.is_set())
        await redis.publish("GOOD", [candle(RESUMED + 60000), candle(RESUMED + 120000)])
        await eventually(lambda: RESUMED + 60000 in storage.rows["GOOD"])
        self.assertFalse(service._state_by_id[1].live_ready.is_set())

    async def test_initial_dependency_outages_retry_before_any_live_consumption(self):
        storage, broker = Storage(), Broker()
        broker.allow_history.set()
        redis = RedisInput()
        attempts = []
        original_markets = storage.get_markets

        async def ping():
            attempts.append("redis")
            if len(attempts) == 1:
                raise OSError("initial Redis unavailable")
            return True

        def markets():
            attempts.append("database")
            if attempts.count("database") == 1:
                raise OSError("initial database unavailable")
            return original_markets()

        redis.ping = ping
        storage.get_markets = markets
        service, _ = await self.start(storage, broker, redis=redis)
        await eventually(lambda: not storage.pending and bool(broker.requests))
        self.assertEqual(storage.rows["BTC"][BOUNDARY + 86400000]["close"], 8)
        self.assertGreaterEqual(attempts.count("redis"), 3)
        await service.shutdown()

    async def test_successful_live_batches_retire_guard_without_scheduling_history(self):
        storage, broker = Storage(), Broker()
        broker.allow_history.set()
        service, redis = await self.start(storage, broker, now=lambda: BOUNDARY + 300000)
        await eventually(lambda: not storage.pending and bool(broker.requests))
        await redis.publish("BTC", [candle(BOUNDARY + 60000), candle(BOUNDARY + 120000)])
        await eventually(lambda: storage.live_writes == 1 and not storage.pending)
        before = len(broker.requests)
        await redis.publish("BTC", [candle(BOUNDARY + 180000), candle(BOUNDARY + 240000)])
        await eventually(lambda: BOUNDARY + 180000 in storage.rows["BTC"])
        await eventually(lambda: not storage.guards)
        self.assertFalse(storage.pending)
        self.assertEqual(len(broker.requests), before)
        await service.shutdown()
