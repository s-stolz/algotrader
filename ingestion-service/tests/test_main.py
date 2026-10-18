from __future__ import annotations

import logging
import unittest
from unittest.mock import AsyncMock, Mock, patch

from main import IngestionService, SymbolRuntimeState


class IngestionHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_backfill_stores_only_closed_minutes_at_fixed_request_boundary(self):
        service = IngestionService.__new__(IngestionService)
        service.logger = logging.getLogger("test-history")
        service._state_by_id = {1: SymbolRuntimeState(1, "EURUSD", "FX", "unused")}
        service.db_client = Mock()
        service.broker_client = Mock()
        requests = []

        async def history(symbol, **kwargs):
            requests.append(kwargs)
            for timestamp in (60000, 120000, 180000):
                if kwargs["start_time"] <= timestamp <= kwargs["end_time"]:
                    yield {"t": timestamp, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}

        service.broker_client.stream_trendbars = history
        with patch.object(IngestionService, "_utc_now_ms", return_value=200000):
            await service._backfill_symbol(1, "EURUSD", 60000, 200000)
        self.assertEqual(requests[0]["end_time"], 179999)
        saved = service.db_client.write_candles.call_args
        self.assertEqual([bar["timestamp_ms"] for bar in saved.args[1]], [60000, 120000])

    async def test_failed_download_does_not_report_or_store_partial_success(self):
        service = IngestionService.__new__(IngestionService)
        service.logger = logging.getLogger("test-history")
        service.broker_client = Mock()
        service.write_candles_callback = AsyncMock()

        async def interrupted(*args, **kwargs):
            yield {"t": 60000, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}
            raise RuntimeError("download incomplete")

        service.broker_client.stream_trendbars = interrupted
        with self.assertRaises(RuntimeError):
            await service._backfill_symbol(1, "EURUSD", 60000, 120000)
        service.write_candles_callback.assert_not_awaited()
