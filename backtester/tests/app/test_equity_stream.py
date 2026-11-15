import unittest

from app.equity_replay import ReplayUnavailableError, descriptor, replay, sample
from app.equity_stream import EquityReplayStream, stream_equity
from domain.enums import OrderSide
from tests.app.test_equity_replay import _fill, _request


class EquityStreamTests(unittest.TestCase):
    def test_batches_match_existing_replay_and_sampling(self):
        request = _request()
        closes = [(request.start_ms + i * 60_000, float(100 + i % 17)) for i in range(4097)]
        fills = [
            _fill(0, closes[1023][0], OrderSide.BUY, 2, 102, 0.5),
            _fill(1, closes[2048][0], OrderSide.SELL, 3, 105, 0.7),
        ]
        saved = descriptor(request, closes)
        stream = EquityReplayStream(request, saved, fills, 100)
        for start in range(0, len(closes), 1024):
            stream.append([dict(timestamp_ms=t, close=c) for t, c in closes[start : start + 1024]])
            self.assertLessEqual(len(stream.preview()["equity_curve"]), 100)
        self.assertEqual(
            stream.finish()["result"]["equity_curve"],
            sample(replay(request, saved, closes, fills), 100),
        )

    def test_changed_candles_never_complete_exact(self):
        request = _request()
        saved = descriptor(request, [(request.start_ms, 1.0)])
        stream = EquityReplayStream(request, saved, [], 100)
        stream.append([dict(timestamp_ms=request.start_ms, close=2.0)])
        self.assertTrue(stream.preview()["equity_curve"])
        with self.assertRaisesRegex(ReplayUnavailableError, "fingerprint_mismatch"):
            stream.finish()

    def test_duplicate_at_chunk_boundary_is_rejected(self):
        request = _request()
        saved = descriptor(request, [(request.start_ms, 1.0)])
        stream = EquityReplayStream(request, saved, [], 100)
        batch = [dict(timestamp_ms=request.start_ms, close=1.0)]
        stream.append(batch)
        with self.assertRaises(ReplayUnavailableError):
            stream.append(batch)


class StreamCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_closing_replay_closes_downstream_before_next_batch(self):
        from types import SimpleNamespace

        request = _request()
        closed = []
        fetched = []

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                closed.append("client")

            async def stream_candles(self, **kwargs):
                try:
                    for i in range(5):
                        fetched.append(i)
                        yield [dict(timestamp_ms=request.start_ms + i * 60_000, close=1.0)]
                finally:
                    closed.append("stream")

        run = SimpleNamespace(
            replay_descriptor=descriptor(request, [(request.start_ms, 1.0)]),
            request_snapshot=SimpleNamespace(to_request=lambda: request),
        )
        events = stream_equity(run, [], 100, Client)
        self.assertEqual((await anext(events))["type"], "preview")
        await events.aclose()
        self.assertEqual(fetched, [0])
        self.assertEqual(closed, ["stream", "client"])


class ReplayStreamBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_market_identity_and_multiplier_survive_streaming(self):
        from dataclasses import replace
        from types import SimpleNamespace

        from domain.risk import InstrumentSpec

        request = _request()
        start = request.start_ms // 60_000 * 60_000
        request = replace(
            request,
            start_ms=start,
            end_ms=start + 120_000,
            instrument=InstrumentSpec(123, "USD", 100, 1, 1, 0.01),
            execution=replace(request.execution, execution_mode="orders", candle_quote="bid"),
        )
        closes = [(start, 10.0), (start + 60_000, 12.0)]
        fills = [_fill(0, start, OrderSide.BUY, 1, 10)]
        saved = descriptor(request, closes)
        calls = []

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def stream_candles(self, **kwargs):
                calls.append(kwargs)
                for timestamp, close in closes:
                    yield [dict(timestamp_ms=timestamp, close=close)]

        run = SimpleNamespace(
            replay_descriptor=saved, request_snapshot=SimpleNamespace(to_request=lambda: request)
        )
        events = [event async for event in stream_equity(run, fills, 100, Client)]
        self.assertEqual(calls[0]["market_id"], 123)
        self.assertEqual(calls[0]["timeframe"], "M1")
        self.assertEqual(
            events[-1]["result"]["equity_curve"], replay(request, saved, closes, fills)
        )

    async def test_failed_source_cannot_complete_a_preview(self):
        from types import SimpleNamespace

        request = _request()

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def stream_candles(self, **kwargs):
                yield [dict(timestamp_ms=request.start_ms, close=1.0)]
                raise OSError("Disconnected")

        run = SimpleNamespace(
            replay_descriptor=descriptor(request, [(request.start_ms, 1.0)]),
            request_snapshot=SimpleNamespace(to_request=lambda: request),
        )
        events = [event async for event in stream_equity(run, [], 100, Client)]
        self.assertEqual([event["type"] for event in events], ["preview", "error"])
