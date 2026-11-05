import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from app.routes.indicators import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from indicator_engine import IndicatorRegistry, get_registry


class IndicatorCatalogTests(unittest.TestCase):
    def test_catalog_preserves_api_ids_and_uses_registered_names(self):
        exposed = [
            (1, "sma"),
            (2, "rsi"),
            (3, "bbands"),
            (4, "macd"),
            (5, "currency_strength"),
            (6, "ema"),
            (7, "opening_range"),
        ]
        registry = IndicatorRegistry()
        for _, engine_id in reversed(exposed):
            indicator = deepcopy(get_registry().get(engine_id))
            indicator.spec = replace(indicator.spec, name=f"Display {engine_id}")
            registry.register(indicator)
        extra = deepcopy(get_registry().get("sma"))
        extra.spec = replace(extra.spec, id="plugin_only")
        registry.register(extra)

        api = FastAPI()
        api.include_router(router)
        with patch("app.ENGINE_REGISTRY", registry), TestClient(api) as client:
            response = client.get("/indicators")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"id": api_id, "indicator_id": engine_id, "name": f"Display {engine_id}"}
                for api_id, engine_id in exposed
            ],
        )
