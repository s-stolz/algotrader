from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.dependencies import get_account_service, get_container, get_market_data_service
from app.api.routers import setup
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.api.routers.fakes import FakeAccountService, FakeMarketDataService


class SetupCatalogueTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(setup.router)
        app.dependency_overrides[get_account_service] = FakeAccountService
        app.dependency_overrides[get_market_data_service] = FakeMarketDataService
        app.dependency_overrides[get_container] = lambda: SimpleNamespace(
            credentials=SimpleNamespace(host_type="demo")
        )
        self.client = TestClient(app)
        self.environment = patch.dict("os.environ", {"ACCOUNT_ID": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_connection_uses_configured_authorized_account(self) -> None:
        response = self.client.get("/connection")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "provider": "ctrader",
                "account_id": "1",
                "environment": "demo",
                "broker_name": "demo",
            },
        )

    def test_verified_instrument_keeps_uncertain_valuation_fields_unresolved(self) -> None:
        response = self.client.get("/setup/instruments/1?account_id=1")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["broker_account_id"], "1")
        self.assertEqual(body["broker_symbol_id"], 1)
        self.assertEqual(body["symbol"], "EURUSD")
        self.assertIsNone(body["min_move"])
        self.assertIsNone(body["contract_multiplier"])
        self.assertEqual(body["suggested_min_move"], 0.00001)

    def test_other_account_and_unknown_instrument_rejected(self) -> None:
        self.assertEqual(self.client.get("/setup/instruments/1?account_id=2").status_code, 409)
        self.assertEqual(self.client.get("/setup/instruments/999").status_code, 404)

    def test_unauthorized_configured_account_rejected(self) -> None:
        with patch.dict("os.environ", {"ACCOUNT_ID": "2"}):
            self.assertEqual(self.client.get("/connection").status_code, 503)
