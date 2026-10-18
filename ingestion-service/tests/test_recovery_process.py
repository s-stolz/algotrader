"""Opt-in abrupt process restart acceptance using real HTTP, Redis and Timescale.

The accessor and Redis must be disposable loopback instances, with no real Markets.
The controlled upstream supplies broker completion records and dependency faults.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
from redis import Redis

ACCESSOR = os.getenv("RECOVERY_TEST_ACCESSOR_URL")
REDIS = os.getenv("RECOVERY_TEST_REDIS_URL")
BOUNDARY = 1791158400000
RESUMED = 1792281600000
NOW = RESUMED + 180000
ROOT = Path(__file__).resolve().parents[2]


def bar(timestamp, value=1, session="a"):
    return dict(
        t=timestamp,
        o=value,
        h=value + 2,
        l=value - 1,
        c=value + 1,
        v=value * 10,
        continuity="v1:" + session * 32,
    )


@unittest.skipUnless(
    ACCESSOR and REDIS, "Set RECOVERY_TEST_ACCESSOR_URL and RECOVERY_TEST_REDIS_URL"
)
class ProcessRecoveryTests(unittest.TestCase):
    def test_abrupt_restart_at_save_live_write_and_progress_transitions(self):
        assert ACCESSOR is not None and REDIS is not None
        for address in (ACCESSOR, REDIS):
            if urlsplit(address).hostname not in ("localhost", "127.0.0.1"):
                raise RuntimeError("Acceptance requires disposable loopback services")
        with httpx.Client(base_url=ACCESSOR) as http, Redis.from_url(REDIS) as redis:
            if http.get("/markets").json():
                raise RuntimeError("Process acceptance requires an empty disposable database")
            for phase in ("before-save", "protected-live", "after-data", "sessions"):
                with self.subTest(phase=phase):
                    self.exercise_phase(http, redis, phase)

    def exercise_phase(self, http, redis, phase):
        accessor_url = str(ACCESSOR)
        redis_url = str(REDIS)
        symbol = "R" + uuid4().hex[:9].upper()
        account = "vibe10-" + uuid4().hex
        response = http.post(
            "/markets",
            json=dict(symbol=symbol, exchange="VIBE10", market_type="test", min_move=0.01),
        )
        response.raise_for_status()
        symbol_id = response.json()["symbol_id"]
        response = http.post(
            "/candles",
            json=dict(
                symbol=symbol,
                exchange="VIBE10",
                candles=[dict(timestamp_ms=BOUNDARY, open=1, high=1, low=1, close=1, volume=1)],
            ),
        )
        response.raise_for_status()
        source = {"account_id": account}
        stream = f"candles:{account}:{symbol}:M1"
        faults = dict(
            save=phase == "before-save",
            history=phase not in ("after-data", "sessions"),
            progress=phase != "sessions",
        )
        attempted = threading.Event()
        history_requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, content):
                payload = content if isinstance(content, bytes) else json.dumps(content).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path == "/meta/health":
                    return self.reply(200, {"components": {"ctrader": {"status": "up"}}})
                if parsed.path.endswith("/trendbar-stream/start"):
                    return self.reply(200, {"status": "started"})
                if parsed.path.endswith("/trendbars/stream"):
                    if faults["history"]:
                        return self.reply(503, {"detail": "controlled unavailable history"})
                    query = parse_qs(parsed.query)
                    start, end = int(query["fromTs"][0]), int(query["toTs"][0])
                    history_requests.append((start, end))
                    records: list[dict[str, Any]] = [
                        bar(t, 8)
                        for t in (
                            BOUNDARY,
                            BOUNDARY + 60000,
                            RESUMED,
                            *([BOUNDARY + 86400000] if phase == "sessions" else []),
                        )
                        if start <= t <= end
                    ]
                    records.append(
                        dict(
                            type="complete",
                            version=1,
                            count=len(records),
                            limit=None,
                            fromTs=start,
                            toTs=end,
                        )
                    )
                    return self.reply(200, "\n".join(json.dumps(r) for r in records).encode())
                with httpx.Client(base_url=accessor_url) as client:
                    result = client.get(self.path)
                return self.reply(result.status_code, result.content)

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/recoveries/begin" and faults["save"]:
                    attempted.set()
                    return self.reply(503, {"detail": "controlled boundary save failure"})
                if self.path == "/recoveries/advance" and faults["progress"]:
                    attempted.set()
                    return self.reply(503, {"detail": "controlled progress persistence failure"})
                with httpx.Client(base_url=accessor_url) as client:
                    result = client.post(
                        self.path, content=body, headers={"Content-Type": "application/json"}
                    )
                return self.reply(result.status_code, result.content)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        environment = dict(
            os.environ,
            PYTHONPATH=os.pathsep.join(
                str(ROOT / p)
                for p in ("ingestion-service", "libs/db_accessor_client", "libs/algotrader_logger")
            ),
            DATABASE_ACCESSOR_HOST="127.0.0.1",
            DATABASE_ACCESSOR_PORT=str(port),
            BROKER_SERVICE_HOST="127.0.0.1",
            BROKER_SERVICE_PORT=str(port),
            ACCOUNT_ID=account,
            REDIS_URL=redis_url,
            HISTORY_LOOKBACK_DAYS="1825",
            HISTORY_START_DATE="",
            RECOVERY_BACKOFF_INITIAL_SECONDS="1",
            RECOVERY_BACKOFF_MAX_SECONDS="1",
            CONSUMER_BLOCK_MS="100",
            INGESTION_LOG_LEVEL="WARNING",
        )
        child = None
        logs = tempfile.TemporaryFile(mode="w+")
        clock = tempfile.NamedTemporaryFile(mode="w", delete=False)
        clock_path = Path(clock.name)
        clock.write(str(BOUNDARY + 120000 if phase == "sessions" else NOW))
        clock.close()

        def launch():
            return subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import asyncio, main; from pathlib import Path; "
                    "main.IngestionService._utc_now_ms = staticmethod(lambda: "
                    f"int(Path({str(clock_path)!r}).read_text())); asyncio.run(main.main())",
                ],
                cwd=ROOT,
                env=environment,
                stdout=logs,
                stderr=subprocess.STDOUT,
            )

        def wait_for(check):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if check():
                    return
                if child is not None and child.poll() is not None:
                    break
                time.sleep(0.05)
            logs.seek(0)
            self.fail("Process acceptance timed out: " + logs.read()[-10000:])

        def pending():
            response = http.get(f"/recoveries/{symbol_id}", params=source)
            response.raise_for_status()
            return response.json()["pending"]

        def stored():
            response = http.get(
                f"/candles/{symbol}", params={"exchange": "VIBE10", "timeframe": "M1"}
            )
            response.raise_for_status()
            return response.json()

        try:
            child = launch()
            if phase == "sessions":
                wait_for(lambda: pending() is None and len(stored()) == 2)
                redis.xadd(stream, bar(BOUNDARY + 60000))
                redis.xadd(stream, bar(BOUNDARY + 120000))
                wait_for(lambda: redis.xlen(stream) >= 2)
                time.sleep(0.2)
                wait_for(lambda: pending() is None)
                # No health-down result exists. A brief reconnect followed by
                # another session (broker restart) must protect both intervals.
                faults["history"] = True
                clock_path.write_text(str(NOW))
                with redis.pipeline() as batch:
                    batch.xadd(stream, bar(RESUMED, session="b"))
                    batch.xadd(stream, bar(RESUMED + 60000, session="b"))
                    batch.execute()
                wait_for(lambda: any(r["timestamp_ms"] == RESUMED for r in stored()))
                first = pending()
                self.assertIsNotNone(first)
                self.assertLessEqual(first["next_ms"], BOUNDARY + 120000)
                self.assertEqual(first["target_ms"], NOW - 1)
                clock_path.write_text(str(NOW + 60000))
                with redis.pipeline() as batch:
                    batch.xadd(stream, bar(RESUMED + 120000, session="c"))
                    batch.xadd(stream, bar(RESUMED + 180000, session="c"))
                    batch.execute()
                wait_for(lambda: any(r["timestamp_ms"] == RESUMED + 120000 for r in stored()))
                second = pending()
                self.assertEqual(second["next_ms"], first["next_ms"])
                self.assertGreater(second["revision"], first["revision"])
                self.assertEqual(second["target_ms"], NOW + 59999)
                child.kill()
                child.wait(timeout=5)
                faults.update(history=False, progress=False)
                environment["HISTORY_LOOKBACK_DAYS"] = "1"
                child = launch()
                wait_for(lambda: pending() is None)
                rows = {r["timestamp_ms"]: r for r in stored()}
                self.assertEqual(rows[BOUNDARY + 60000]["close"], 9)
                self.assertEqual(rows[RESUMED]["close"], 9)
                self.assertEqual(rows[BOUNDARY + 86400000]["close"], 9)
                self.assertTrue(any(start < RESUMED for start, _ in history_requests))
                # A further live update proves delivery after the pending restart.
                redis.xadd(stream, bar(RESUMED + 180000, session="c"))
                redis.xadd(stream, bar(RESUMED + 240000, session="c"))
                wait_for(lambda: any(r["timestamp_ms"] == RESUMED + 180000 for r in stored()))
                child.terminate()
                self.assertEqual(child.wait(timeout=5), 0)
                return
            if phase == "before-save":
                wait_for(attempted.is_set)
                self.assertIsNone(pending())
                redis.xadd(stream, bar(RESUMED))
                redis.xadd(stream, bar(RESUMED + 60000))
                time.sleep(0.15)
                self.assertEqual([r["timestamp_ms"] for r in stored()], [BOUNDARY])
            elif phase == "protected-live":
                wait_for(lambda: pending() is not None)
                self.assertEqual(pending()["next_ms"], BOUNDARY)
                redis.xadd(stream, bar(RESUMED))
                redis.xadd(stream, bar(RESUMED + 60000))
                wait_for(lambda: len(stored()) == 2)
                self.assertEqual(pending()["next_ms"], BOUNDARY)
            else:
                wait_for(attempted.is_set)
                self.assertEqual(pending()["next_ms"], BOUNDARY)
                self.assertEqual([r["close"] for r in stored()], [9, 9])
            child.kill()
            child.wait(timeout=5)
            faults.update(save=False, history=False, progress=False)
            if phase != "before-save":
                environment["HISTORY_LOOKBACK_DAYS"] = "1"
            child = launch()
            wait_for(lambda: pending() is None and len(stored()) == 3)
            self.assertEqual(
                [r["timestamp_ms"] for r in stored()], [BOUNDARY, BOUNDARY + 60000, RESUMED]
            )
            self.assertEqual([r["close"] for r in stored()], [9, 9, 9])
            self.assertTrue(any(start == BOUNDARY for start, _ in history_requests))
            self.assertTrue(
                all(end < NOW and end - start < 86400000 for start, end in history_requests)
            )
            # Real Redis delivery continues after recovery completion in the new process.
            redis.xadd(stream, bar(RESUMED + 60000))
            redis.xadd(stream, bar(RESUMED + 120000))
            wait_for(lambda: any(r["timestamp_ms"] == RESUMED + 60000 for r in stored()))
            child.terminate()
            self.assertEqual(child.wait(timeout=5), 0)
        finally:
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            logs.close()
            clock_path.unlink(missing_ok=True)
            redis.delete(stream)
            response = http.delete(f"/markets/{symbol}", params={"exchange": "VIBE10"})
            response.raise_for_status()
