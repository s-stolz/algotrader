"""A registration reaches the production catalog, computation and live stream path."""

import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
from app import get_engine_id, get_indicator_metadata
from app.routes.indicators import router
from app.schemas_live import LiveIndicatorStreamRequest
from app.services.candle_cache import CandleCache
from app.services.live_indicator_manager import LiveIndicatorManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from indicator_engine import BarTensor, ParamGrid, get_batch_engine
from indicator_engine.catalog import IndicatorCatalog, IndicatorRegistration
from indicator_engine.indicators.sma import SMA


class SingleRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_registration_drives_catalog_batch_and_live_stream_policy(self):
        class FixtureAverage(SMA):
            def __init__(self):
                super().__init__()
                self.spec = replace(self.spec, id="fixture_average", name="Fixture average")

        entry = IndicatorRegistration(
            public_id=42,
            implementation=FixtureAverage,
            supports_live=True,
            overlay=False,
            outputs={"sma": {"type": "line", "plotOptions": {"color": "red"}}},
        )
        catalog = IndicatorCatalog([entry])
        registry = catalog.create_registry()
        api = FastAPI()
        api.include_router(router)
        cache = CandleCache()
        candles = pd.DataFrame(
            {
                "open": [1.0, 3.0],
                "high": [1.0, 3.0],
                "low": [1.0, 3.0],
                "close": [1.0, 3.0],
                "volume": [1.0, 1.0],
            },
            index=pd.to_datetime([-60000, 0], unit="ms", utc=True),
        )
        cache.put(exchange=None, symbol="TEST", timeframe="M1", candles=candles)
        request = LiveIndicatorStreamRequest(
            account_id="123",
            symbol="TEST",
            timeframe="M1",
            indicator_id=42,
            parameters={"window": 2},
        )
        with (
            patch("app.INDICATOR_CATALOG", catalog),
            patch("app.ENGINE_REGISTRY", registry),
            patch("app.services.live_indicator_manager.ENGINE_REGISTRY", registry),
            TestClient(api) as client,
        ):
            self.assertEqual(
                client.get("/indicators").json(),
                [{"id": 42, "indicator_id": "fixture_average", "name": "Fixture average"}],
            )
            metadata = get_indicator_metadata(42)
            self.assertTrue(metadata["supports_live"])
            self.assertEqual(metadata["outputs"], entry.outputs)
            metadata["outputs"]["sma"]["plotOptions"]["color"] = "changed"
            self.assertEqual(get_indicator_metadata(42)["outputs"], entry.outputs)
            self.assertEqual(get_engine_id(42), "fixture_average")
            bars = BarTensor(
                data=candles.to_numpy()[:, None, :],
                time=candles.index.to_numpy(),
                assets=np.array(["TEST"]),
                fields=np.array(candles.columns),
            )
            result = get_batch_engine(registry).run(
                "fixture_average", bars, ParamGrid({"window": 2})
            )
            self.assertEqual(float(np.asarray(result.tensor.data).reshape(-1)[-1]), 2.0)
            manager = LiveIndicatorManager(cache)
            manager._redis = Mock(xread=AsyncMock(return_value=[]), close=AsyncMock())
            try:
                started = await manager.start_stream(request)
                self.assertIsNotNone(started)
            finally:
                await manager.shutdown()

            disabled = IndicatorCatalog([replace(entry, supports_live=False)])
            with patch("app.INDICATOR_CATALOG", disabled):
                self.assertFalse(get_indicator_metadata(42)["supports_live"])
                with self.assertRaisesRegex(ValueError, "fixture_average is not supported"):
                    await LiveIndicatorManager(cache).start_stream(request)
