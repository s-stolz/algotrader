from __future__ import annotations

import asyncio
import logging
import unittest
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from app.config import load_config
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
        saved = service.db_client.write_historical_candles.call_args
        self.assertEqual([bar["timestamp_ms"] for bar in saved.args[1]], [60000, 120000])

    async def test_failed_download_does_not_report_or_store_partial_success(self):
        service = IngestionService.__new__(IngestionService)
        service.logger = logging.getLogger("test-history")
        service.broker_client = Mock()
        service.db_client = Mock()

        async def interrupted(*args, **kwargs):
            yield {"t": 60000, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}
            raise RuntimeError("download incomplete")

        service.broker_client.stream_trendbars = interrupted
        with self.assertRaises(RuntimeError):
            await service._backfill_symbol(1, "EURUSD", 60000, 120000)
        service.db_client.write_historical_candles.assert_not_called()

    async def test_startup_refetches_recent_boundary_and_bounds_pre_activation_history(self):
        service = IngestionService.__new__(IngestionService)
        service.logger = logging.getLogger("test-history")
        service.db_client = Mock()
        service.config = load_config()
        service.runtime_states = [
            SymbolRuntimeState(1, "EURUSD", "FX", "unused", live_start_ms=60000)
        ]
        service._backfill_symbol = AsyncMock()
        for latest, expected in [
            (None, 60000),
            ({"timestamp_ms": 0}, 60000),
            ({"timestamp_ms": 120000}, 120000),
        ]:
            service.db_client.get_latest_m1_candle.return_value = latest
            with patch.object(IngestionService, "_utc_now_ms", return_value=200000):
                watermark = service._get_frozen_watermark("EURUSD", "FX")
                await service._backfill_symbol(1, "EURUSD", watermark, 200000)
            self.assertEqual(watermark, expected)
            self.assertEqual(service._backfill_symbol.call_args.args[2], expected)

    async def test_invalid_broker_candle_prevents_historical_writes(self):
        service = IngestionService.__new__(IngestionService)
        service.logger = logging.getLogger("test-history")
        service.db_client = Mock()
        service.broker_client = Mock()

        async def invalid(*args, **kwargs):
            for timestamp in (60000, 180000):
                yield {"t": timestamp, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}

        service.broker_client.stream_trendbars = invalid
        with patch.object(IngestionService, "_utc_now_ms", return_value=200000):
            with self.assertRaises(ValueError):
                await service._backfill_symbol(1, "EURUSD", 60000, 200000)
        service.db_client.write_historical_candles.assert_not_called()


class MarketSourceTests(unittest.IsolatedAsyncioTestCase):
    def service(self) -> Any:
        service = IngestionService.__new__(IngestionService)
        service.config = load_config()
        service.config.broker_account_id = "12345"
        service.config.broker_environment = "demo"
        service.logger = Mock()
        service.consumer = Mock()
        service.consumer.get_stream_key.side_effect = lambda symbol, timeframe: symbol
        service.runtime_states = []
        service._state_by_id = {}
        service._owned_tasks = set()
        service.db_client = Mock()
        service.broker_client = Mock()
        service.broker_client.stop_trendbar_stream = AsyncMock()
        service._start_market = AsyncMock()
        return service

    def market(self, **changes):
        return (
            dict(
                symbol_id=1,
                symbol="EURUSD",
                exchange="Broker",
                source_type="broker",
                broker_provider="ctrader",
                broker_account_id="12345",
                broker_environment="demo",
                broker_symbol_id=11,
                live_start_ms=120000,
            )
            | changes
        )

    async def test_only_matching_broker_markets_activate(self):
        service = self.service()
        markets = [
            self.market(),
            self.market(symbol_id=2, source_type="custom"),
            self.market(symbol_id=3, broker_account_id="other"),
            self.market(symbol_id=4, broker_environment="live"),
        ]
        service._install_market_states(markets)
        self.assertEqual([state.symbol_id for state in service.runtime_states], [1])
        service.db_client.get_latest_m1_candle.return_value = None
        self.assertEqual(service._get_frozen_watermark("EURUSD", "Broker"), 120000)

    async def test_new_market_is_discovered_without_restart_and_only_started_once(self):
        service = self.service()
        service.db_client.get_markets.return_value = [self.market()]
        await service.reconcile_markets()
        await asyncio.sleep(0)
        await service.reconcile_markets()
        self.assertEqual(service._start_market.await_count, 1)

    async def test_removed_market_tasks_are_drained_before_source_is_removed(self):
        service = self.service()
        service._install_market_states([self.market()])
        state = service.runtime_states[0]
        finished = asyncio.Event()

        async def in_flight():
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

        service._own_market_task(state, in_flight())
        await asyncio.sleep(0)
        service.db_client.get_markets.return_value = []
        await service.reconcile_markets()
        self.assertTrue(finished.is_set())
        self.assertFalse(service.runtime_states)
        service.broker_client.stop_trendbar_stream.assert_awaited_once()

    async def test_restart_before_first_candle_preserves_original_activation_boundary(self):
        for _ in range(2):
            service = self.service()
            service._install_market_states([self.market()])
            service.db_client.get_latest_m1_candle.return_value = None
            with patch.object(IngestionService, "_utc_now_ms", return_value=900000):
                self.assertEqual(service._get_frozen_watermark("EURUSD", "Broker"), 120000)
