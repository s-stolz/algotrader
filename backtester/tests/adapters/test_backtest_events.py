"""Delivery tests use a private Redis socket, never the running stack."""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from adapters.backtest_events import (
    CONTROL_STREAM,
    EVENT_STREAM,
    BacktestControlInbox,
    BacktestEventPublisher,
)
from redis import Redis


@unittest.skipUnless(
    os.getenv("RUN_BACKTEST_REDIS_TESTS") == "1" and shutil.which("redis-server"),
    "Set RUN_BACKTEST_REDIS_TESTS=1 with redis-server installed",
)
class RedisDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="backtest-redis-", dir="/tmp")
        cls.socket = str(Path(cls.directory.name) / "redis.sock")
        cls.process = subprocess.Popen(
            [
                "redis-server",
                "--port",
                "0",
                "--unixsocket",
                cls.socket,
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.redis = Redis(unix_socket_path=cls.socket, decode_responses=True)
        deadline = time.monotonic() + 5
        while True:
            try:
                cls.redis.ping()
                break
            except Exception:
                if cls.process.poll() is not None or time.monotonic() > deadline:
                    cls.process.terminate()
                    cls.process.wait()
                    cls.directory.cleanup()
                    raise RuntimeError("Private test Redis could not start") from None
                time.sleep(0.02)

    @classmethod
    def tearDownClass(cls):
        cls.redis.close()
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.directory.cleanup()

    def setUp(self):
        self.redis.flushdb()

    def test_offline_worker_reads_retained_message_and_recovers_it_until_ack(self):
        publisher = BacktestEventPublisher(self.redis)
        publisher.changed()
        publisher.flush()
        worker = BacktestControlInbox(self.redis, group="instance-a")
        worker._connect()
        worker.take()
        worker._read()
        received = worker.take()
        self.assertEqual(len(received), 1)
        self.assertEqual(self.redis.xpending(CONTROL_STREAM, "instance-a")["pending"], 1)

        restarted = BacktestControlInbox(self.redis, group="instance-a")
        restarted._connect()
        self.assertEqual(restarted.take(), received)
        restarted.acknowledge(received)
        restarted._read()
        self.assertEqual(self.redis.xpending(CONTROL_STREAM, "instance-a")["pending"], 0)
        again = BacktestControlInbox(self.redis, group="instance-a")
        again._connect()
        self.assertEqual(again.take(), set())
        self.assertTrue(self.redis.xlen(EVENT_STREAM))

    def test_each_worker_gets_wakeup_so_idle_worker_cannot_steal_cancellation(self):
        publisher = BacktestEventPublisher(self.redis)
        publisher.changed()
        publisher.flush()
        deliveries = []
        for identity in ("owner", "idle"):
            inbox = BacktestControlInbox(self.redis, group=identity)
            inbox._connect()
            inbox.take()
            inbox._read()
            deliveries.append(inbox.take())
        self.assertEqual(deliveries[0], deliveries[1])
        self.assertEqual(len(deliveries[0]), 1)

    def test_reconnect_requests_reconciliation_even_after_stream_loss(self):
        inbox = BacktestControlInbox(self.redis, group="owner")
        inbox._connect()
        inbox.take()
        self.redis.flushdb()
        inbox._connect()
        self.assertTrue(inbox.ready.is_set())


class PublisherRetryTests(unittest.TestCase):
    def test_failed_publication_is_retained_and_retry_coalesces_changes(self):
        redis = Mock()
        redis.xadd.side_effect = [ConnectionError("offline"), "1-0", "2-0"]
        publisher = BacktestEventPublisher(redis)
        publisher.changed()
        with self.assertRaises(ConnectionError):
            publisher.flush()
        publisher.changed()
        publisher.flush()
        self.assertEqual(redis.xadd.call_count, 3)
        publisher.flush()
        self.assertEqual(redis.xadd.call_count, 3)

    def test_change_arriving_during_publication_is_not_dropped(self):
        redis = Mock()
        publisher = BacktestEventPublisher(redis)
        publisher.changed()

        def publish(stream, *args, **kwargs):
            if stream == CONTROL_STREAM:
                publisher.changed()
            return "1-0"

        redis.xadd.side_effect = publish
        publisher.flush()
        redis.xadd.side_effect = None
        publisher.flush()
        self.assertEqual(redis.xadd.call_count, 4)
