"""Opt-in worker restart acceptance against a disposable real accessor database."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
from app.history.worker import WINDOW_MS

ACCESSOR = os.getenv("HISTORY_DOWNLOAD_PROCESS_ACCESSOR_URL")
SERVICE_ROOT = Path(__file__).resolve().parents[2]


def candle(timestamp, value=1):
    return dict(
        timestamp_ms=timestamp, open=value, high=value + 1, low=value - 1, close=value, volume=10
    )


def broker_handler(gate, blocked, requested):
    class BrokerHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            query = parse_qs(urlsplit(self.path).query)
            start, end = int(query["fromTs"][0]), int(query["toTs"][0])
            requested.append((start, end))
            if start < 2 * WINDOW_MS:
                blocked.set()
                gate.wait(180)
            records: list[dict[str, Any]] = [
                dict(t=t, o=1, h=2, l=0, c=1, v=10)
                for t in (60_000, WINDOW_MS + 60_000, 2 * WINDOW_MS + 60_000)
                if start <= t <= end
            ]
            records.append(
                dict(
                    type="complete",
                    version=1,
                    count=len(records),
                    fromTs=start,
                    toTs=end,
                    limit=None,
                )
            )
            payload = "\n".join(json.dumps(record) for record in records).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except BrokenPipeError:
                pass

    return BrokerHandler


@unittest.skipUnless(ACCESSOR, "Set HISTORY_DOWNLOAD_PROCESS_ACCESSOR_URL for process acceptance")
class HistoryProcessTests(unittest.TestCase):
    def test_killed_worker_resumes_after_lease_and_cancel_stays_terminal(self):
        assert ACCESSOR is not None
        if urlsplit(ACCESSOR).hostname not in {"localhost", "127.0.0.1"}:
            raise RuntimeError(
                "Use a disposable loopback accessor with a controlled broker verifier"
            )
        with httpx.Client(base_url=ACCESSOR, timeout=30) as client:
            existing = client.get("/markets")
            existing.raise_for_status()
            if existing.json():
                raise RuntimeError("Process acceptance requires an empty disposable database")
            self.exercise(client)

    def exercise(self, client):
        symbol = "P" + uuid4().hex[:8].upper()
        response = client.post(
            "/markets",
            json=dict(
                symbol=symbol,
                exchange="PROCESS TEST",
                market_type="Forex",
                min_move=0.00001,
                timezone="UTC",
                settlement_currency="USD",
                contract_multiplier=1,
                minimum_quantity=1,
                quantity_step=1,
                source_type="broker",
                broker_provider="ctrader",
                broker_account_id="test-account",
                broker_environment="demo",
                broker_symbol_id=17,
            ),
        )
        response.raise_for_status()
        market_id = response.json()["symbol_id"]
        anchor = 3 * WINDOW_MS
        seeded = client.post(
            "/candles",
            json={
                "symbol": symbol,
                "exchange": "PROCESS TEST",
                "candles": [candle(anchor, 9)],
            },
        )
        seeded.raise_for_status()
        gate, blocked = threading.Event(), threading.Event()
        requested = []

        server = ThreadingHTTPServer(("127.0.0.1", 0), broker_handler(gate, blocked, requested))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        broker_url = f"http://127.0.0.1:{server.server_port}"
        jobs = []
        child = None
        logs = tempfile.TemporaryFile(mode="w+")

        def accept(count):
            reply = client.post(
                "/history-download-jobs",
                json={
                    "request_id": str(uuid4()),
                    "market_id": market_id,
                    "candle_count": count,
                },
            )
            reply.raise_for_status()
            identity = reply.json()["id"]
            jobs.append(identity)
            return identity

        def snapshot(identity):
            reply = client.get(f"/history-download-jobs/{identity}")
            reply.raise_for_status()
            return reply.json()

        def launch(identity):
            assert ACCESSOR is not None
            return subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.history.worker_process",
                    ACCESSOR,
                    broker_url,
                    identity,
                ],
                cwd=SERVICE_ROOT,
                stdout=logs,
                stderr=subprocess.STDOUT,
            )

        try:
            identity = accept(2)
            child = launch(identity)
            self.assertTrue(blocked.wait(20), "Worker did not reach second page")
            before = snapshot(identity)
            self.assertEqual(before["cursor_ms"], 2 * WINDOW_MS)
            self.assertEqual(before["inserted_count"], 1)
            child.kill()
            child.wait(timeout=5)
            child = launch(identity)
            self.assertEqual(child.wait(timeout=10), 0)
            self.assertEqual(snapshot(identity)["revision"], before["revision"])
            expiry = datetime.fromisoformat(before["lease_expires_at"])
            deadline = time.monotonic() + 130
            while datetime.now(timezone.utc) <= expiry:
                self.assertLess(time.monotonic(), deadline, "Lease did not expire")
                time.sleep(0.25)
            gate.set()
            child = launch(identity)
            self.assertEqual(child.wait(timeout=20), 0)
            completed = snapshot(identity)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["inserted_count"], 2)
            self.assertEqual(completed["fetched_count"], 2)
            rows = client.get(
                f"/candles/{symbol}",
                params={
                    "exchange": "PROCESS TEST",
                    "timeframe": "M1",
                },
            ).json()
            self.assertEqual(len(rows), 3)
            self.assertEqual(next(row for row in rows if row["timestamp_ms"] == anchor)["close"], 9)

            gate.clear()
            blocked.clear()
            cancelled_id = accept(1)
            child = launch(cancelled_id)
            self.assertTrue(blocked.wait(20))
            cancelled = client.post(f"/history-download-jobs/{cancelled_id}/cancel")
            cancelled.raise_for_status()
            gate.set()
            self.assertEqual(child.wait(timeout=20), 0)
            child = launch(cancelled_id)
            self.assertEqual(child.wait(timeout=10), 0)
            self.assertEqual(snapshot(cancelled_id)["status"], "cancelled")
            self.assertEqual(snapshot(cancelled_id)["inserted_count"], 0)
            self.assertGreaterEqual(len(requested), 3)
        except Exception:
            logs.seek(0)
            print(logs.read())
            raise
        finally:
            gate.set()
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            for identity in jobs:
                client.post(f"/history-download-jobs/{identity}/cancel")
            removed = client.delete(f"/markets/{symbol}", params={"exchange": "PROCESS TEST"})
            removed.raise_for_status()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            logs.close()
