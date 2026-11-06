import json
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app import get_available_indicators, get_indicator_metadata
from app.routes.indicators import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from indicator_engine import IndicatorRegistry, get_registry


class IndicatorCatalogTests(unittest.TestCase):
    def test_public_catalog_and_all_metadata_remain_compatible(self):
        expected = json.loads(
            (Path(__file__).parent / "fixtures" / "indicator_catalog.json").read_text()
        )
        actual = {
            "catalog": get_available_indicators(),
            "metadata": {
                str(item["id"]): get_indicator_metadata(item["id"])
                for item in get_available_indicators()
            },
        }
        self.assertEqual(actual, expected)

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

    def test_live_metadata_endpoint_exposes_basket_dependencies_and_unknown_ids(self):
        api = FastAPI()
        api.include_router(router)
        with TestClient(api) as client:
            response = client.get("/indicators/5")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["supports_live"])
            self.assertEqual(len(response.json()["inputs"]), 7)
            self.assertEqual(client.get("/indicators/1").json()["inputs"], [])
            self.assertEqual(client.get("/indicators/999").status_code, 404)
